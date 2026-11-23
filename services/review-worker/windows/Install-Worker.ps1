<#
Installs the Kim review worker natively under E:\KimReview on a Windows Server host.
Idempotent: each step is skipped when its output already exists. Does not touch other services.
Run as Administrator. Never prints the worker token.
#>
param(
    [string]$Root = 'E:\KimReview',
    [string]$OdooIp = '10.77.160.128',
    [string]$BindIp = '10.77.160.36',
    [int]$Port = 8090,
    [int]$Threads = 6
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Dirs = 'downloads', 'tools', 'models\llm', 'models\whisper', 'data', 'logs', 'samples', 'app'
foreach ($d in $Dirs) { New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null }
$Dl = Join-Path $Root 'downloads'

function Get-File($Url, $Out, $MinBytes = 1) {
    if ((Test-Path $Out) -and (Get-Item $Out).Length -ge $MinBytes) { "skip $Out"; return }
    "download $Url"
    $tmp = "$Out.part"
    # BITS needs an interactive logon (fails over SSH); curl.exe ships with Server 2019 and resumes (-C -).
    & "$env:SystemRoot\System32\curl.exe" -fsSL --retry 5 --retry-delay 10 -C - -o $tmp $Url
    if ($LASTEXITCODE -ne 0) { throw "download failed ($LASTEXITCODE): $Url" }
    if ((Get-Item $tmp).Length -lt $MinBytes) { throw "download too small: $Url" }
    Move-Item -Force $tmp $Out
}

# 1. Python 3.11 (private install, not on PATH, no file associations)
$Py = Join-Path $Root 'tools\python\python.exe'
if (-not (Test-Path $Py)) {
    $exe = Join-Path $Dl 'python-3.11.9-amd64.exe'
    Get-File 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' $exe 20MB
    Start-Process $exe -Wait -ArgumentList @('/quiet', 'InstallAllUsers=0', "TargetDir=$Root\tools\python",
        'PrependPath=0', 'Include_test=0', 'Include_launcher=0', 'AssociateFiles=0', 'Shortcuts=0')
}
& $Py --version

# 2. ffmpeg (portable zip)
$Ff = Join-Path $Root 'tools\ffmpeg\bin\ffmpeg.exe'
if (-not (Test-Path $Ff)) {
    $zip = Join-Path $Dl 'ffmpeg-essentials.zip'
    Get-File 'https://github.com/GyanD/codexffmpeg/releases/download/9.1/ffmpeg-9.1-essentials_build.zip' $zip 50MB
    $x = Join-Path $Dl 'ffmpeg-x'; Remove-Item -Recurse -Force $x -ErrorAction SilentlyContinue
    Expand-Archive $zip $x
    Move-Item (Get-ChildItem $x -Directory | Select-Object -First 1).FullName (Join-Path $Root 'tools\ffmpeg')
}
& $Ff -hide_banner -version | Select-Object -First 1

# 3. Tesseract (silent NSIS install into our folder) + Vietnamese data
# The UB-Mannheim NSIS installer ignores /D when run over SSH and installs to Program Files.
$TessCandidates = @((Join-Path $Root 'tools\tesseract\tesseract.exe'), 'C:\Program Files\Tesseract-OCR\tesseract.exe')
$Tess = $TessCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Tess) {
    $exe = Join-Path $Dl 'tesseract-setup.exe'
    Get-File 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe' $exe 20MB
    Start-Process $exe -Wait -ArgumentList @('/S', "/D=$Root\tools\tesseract")
    $Tess = $TessCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Tess) { throw 'tesseract install not found' }
}
"tesseract at $Tess"
$Vie = Join-Path (Split-Path $Tess) 'tessdata\vie.traineddata'
Get-File 'https://github.com/tesseract-ocr/tessdata_fast/raw/main/vie.traineddata' $Vie 100KB
& $Tess --list-langs 2>&1 | Select-Object -First 5

# 4. Python virtualenv + packages (CPU wheels; llama.cpp prebuilt for Windows)
$Venv = Join-Path $Root 'venv'
if (-not (Test-Path "$Venv\Scripts\python.exe")) { & $Py -m venv $Venv }
$VPy = "$Venv\Scripts\python.exe"
& $VPy -m pip install --disable-pip-version-check -q --upgrade pip
& $VPy -m pip install --disable-pip-version-check -q -r (Join-Path $Root 'app\requirements-windows.txt') `
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
& $VPy -c "import faster_whisper, llama_cpp, fastapi, psutil, pytesseract; print('imports ok', llama_cpp.__version__)"

# 5. Models
$Gguf = Join-Path $Root 'models\llm\Qwen2.5-7B-Instruct-Q4_K_M.gguf'
Get-File 'https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf' $Gguf 4GB
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$ErrorActionPreference = 'Continue'   # huggingface_hub writes harmless warnings to stderr
& $VPy -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root=r'$Root\models\whisper'); print('whisper ok')" 2>&1 | Where-Object { "$_" -notmatch 'unauthenticated requests' }
if ($LASTEXITCODE -ne 0) { throw 'whisper download failed' }
$ErrorActionPreference = 'Stop'

# 6. Config (.env.worker) with a fresh token; ACL Administrators + SYSTEM only
$Env = Join-Path $Root 'app\.env.worker'
if (-not (Test-Path $Env)) {
    $bytes = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $token = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    @(
        "WORKER_TOKEN=$token", "WORKER_BIND=$BindIp", "WORKER_PORT=$Port",
        "WORKER_DATA_DIR=$Root\data", 'WORKER_RETENTION_HOURS=72', 'WORKER_RUN_WINDOW=',
        "WORKER_THREADS=$Threads", "OMP_NUM_THREADS=$Threads",
        'WHISPER_MODEL=small', "WHISPER_DIR=$Root\models\whisper", 'WHISPER_LANGUAGE=en',
        "FFMPEG_BIN=$Root\tools\ffmpeg\bin\ffmpeg.exe", "FFPROBE_BIN=$Root\tools\ffmpeg\bin\ffprobe.exe",
        "TESSERACT_BIN=$Tess", 'OCR_LANGS=eng+vie',
        'SYNTH_BACKEND=local', "LLM_MODEL_PATH=$Gguf", 'LLM_CTX=12288',
        'HF_HUB_OFFLINE=1', 'HF_HUB_DISABLE_TELEMETRY=1'
    ) | Set-Content -Path $Env -Encoding ascii
    'created .env.worker (token not shown)'
}
foreach ($p in $Env, (Join-Path $Root 'data')) {
    icacls $p /inheritance:r /grant '*S-1-5-32-544:(OI)(CI)F' /grant '*S-1-5-18:(OI)(CI)F' | Out-Null
}
icacls $Env /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null

# 7. Firewall: only Odoo production may reach the API port
if (-not (Get-NetFirewallRule -Name KimReview-API -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name KimReview-API -DisplayName 'KimReview worker API' -Direction Inbound -Protocol TCP `
        -LocalPort $Port -RemoteAddress $OdooIp -Action Allow | Out-Null
}

# 8. Scheduled task at startup as SYSTEM, BelowNormal priority, restart on failure
$Run = Join-Path $Root 'app\Run-Worker.ps1'
@"
`$ErrorActionPreference = 'Continue'
Set-Location '$Root\app'
`$env:WORKER_ENV_FILE = '$Env'
& '$VPy' -m review_worker.serve *>> '$Root\logs\worker.log'
"@ | Set-Content -Path $Run -Encoding utf8
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Run`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) -Priority 7 -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'KimReviewWorker' -Action $action -Trigger $trigger -Settings $settings `
    -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
'task registered (not started)'
