#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [switch]$Plan,
    [switch]$RetryFailed
)
$ErrorActionPreference = 'Stop'
$env:GIT_TERMINAL_PROMPT = '0'
$env:GCM_INTERACTIVE = 'Never'
$lock = $null
$logging = $false
$maintenance = $false

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
function Get-Git {
    param([string[]]$Arguments)
    $result = & git -C $script:repo @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git failed: $($Arguments -join ' ')" }
    return ($result -join "`n").Trim()
}
function Invoke-Compose {
    param([string[]]$Arguments)
    Invoke-Checked -Program 'docker' -Arguments (@('compose', '--project-directory', $script:repo, '-f',
        (Join-Path $script:repo 'docker-compose.yml')) + $Arguments)
}

try {
    $config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($key in @('RepoPath', 'Branch', 'Database', 'Modules', 'PostgresUser', 'StatePath', 'BackupPath', 'HealthUrl', 'HealthTimeoutSeconds')) {
        if (-not $config.$key) { throw "Missing configuration: $key" }
    }
    if ($config.Database -notmatch '^[a-zA-Z0-9_][a-zA-Z0-9_.-]*$' -or $config.Database -like 'REPLACE*') {
        throw 'Set Database to the real server database name.'
    }
    if ($config.PostgresUser -notmatch '^\w+$') { throw 'Invalid PostgresUser.' }
    $modules = @($config.Modules)
    foreach ($module in $modules) {
        if ($module -notmatch '^[a-zA-Z0-9_]+$') { throw "Invalid module name: $module" }
    }
    if ([int]$config.HealthTimeoutSeconds -lt 10) { throw 'HealthTimeoutSeconds must be at least 10.' }
    $repo = (Resolve-Path -LiteralPath $config.RepoPath).Path
    foreach ($path in @($config.StatePath, $config.BackupPath)) {
        if (-not [IO.Path]::IsPathRooted($path)) { throw 'StatePath and BackupPath must be absolute.' }
        $fullPath = [IO.Path]::GetFullPath($path).TrimEnd('\')
        if ($fullPath -eq $repo -or $fullPath.StartsWith($repo.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'State and backups must be outside the Git checkout.'
        }
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
    try {
        $lock = [IO.File]::Open((Join-Path $config.StatePath 'deploy.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch [IO.IOException] {
        Write-Host 'Another deployment is running; skipping.'
        exit 0
    }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    Start-Transcript -Path (Join-Path $config.StatePath "deploy-$stamp.log") | Out-Null
    $logging = $true
    $pending = Join-Path $config.StatePath 'pending.json'
    if ((Test-Path -LiteralPath $pending) -and -not $RetryFailed -and -not $Plan) {
        throw 'Previous deployment did not finish. Inspect pending.json/logs/backups before using -RetryFailed.'
    }
    if ((Get-Git -Arguments @('branch', '--show-current')) -ne $config.Branch) { throw 'Checkout is on the wrong branch.' }
    if (Get-Git -Arguments @('status', '--porcelain')) { throw 'Checkout has local changes. Commit or move them before deployment.' }
    Invoke-Checked -Program 'git' -Arguments @('-C', $repo, 'check-ref-format', '--branch', $config.Branch)
    Invoke-Checked -Program 'git' -Arguments @('-C', $repo, 'fetch', '--no-tags', 'origin', "refs/heads/$($config.Branch):refs/remotes/origin/$($config.Branch)")
    $old = Get-Git -Arguments @('rev-parse', 'HEAD')
    $target = Get-Git -Arguments @('rev-parse', "refs/remotes/origin/$($config.Branch)")
    Invoke-Checked -Program 'git' -Arguments @('-C', $repo, 'merge-base', '--is-ancestor', $old, $target)
    $successFile = Join-Path $config.StatePath 'success.json'
    if ((Test-Path -LiteralPath $successFile) -and -not (Test-Path -LiteralPath $pending)) {
        $success = Get-Content -LiteralPath $successFile -Raw | ConvertFrom-Json
        $signature = "$($config.Database)|$($modules -join ',')|$($config.HealthUrl)"
        if ($success.Commit -eq $target -and $success.Signature -eq $signature -and $old -eq $target) {
            Write-Host "Already deployed: $target"
            exit 0
        }
    }
    Write-Host "Deploy $old -> $target; DB=$($config.Database); modules=$($modules -join ',')"
    if ($Plan) { Write-Host 'Plan only: no services or database changed.'; exit 0 }
    $osType = & docker info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0 -or ($osType -join '').Trim() -ne 'linux') { throw 'A reachable Linux Docker engine is required.' }
    Invoke-Compose -Arguments @('config', '--quiet')
    # Require an existing installation. Never create a fresh empty production database.
    Invoke-Compose -Arguments @('exec', '-T', 'db', 'pg_isready', '-U', $config.PostgresUser)
    $moduleList = ($modules | ForEach-Object { "'$_'" }) -join ','
    $sql = "SELECT count(*) FROM ir_module_module WHERE state='installed' AND name IN ($moduleList)"
    $installed = & docker compose --project-directory $repo -f (Join-Path $repo 'docker-compose.yml') `
        exec -T db psql -U $config.PostgresUser -d $config.Database -tAc $sql
    if ($LASTEXITCODE -ne 0 -or ($installed -join '').Trim() -ne [string]$modules.Count) {
        throw 'Database must already exist with every configured module installed. Auto deploy only upgrades modules.'
    }
    $backup = Join-Path $config.BackupPath "$stamp-$($old.Substring(0, 12))"
    New-Item -ItemType Directory -Path $backup | Out-Null
    @{ PreviousCommit = $old; TargetCommit = $target; Database = $config.Database; Backup = $backup } |
        ConvertTo-Json | Set-Content -LiteralPath $pending -Encoding UTF8
    Copy-Item -LiteralPath $pending -Destination (Join-Path $backup 'deployment.json')
    $maintenance = $true
    Invoke-Compose -Arguments @('stop', 'web')
    # Back up while Odoo is stopped so database and attachment files are consistent.
    $dump = "/tmp/kim-deploy-$stamp.dump"
    Invoke-Compose -Arguments @('exec', '-T', 'db', 'pg_dump', '-U', $config.PostgresUser, '-Fc', '-f', $dump, $config.Database)
    Invoke-Compose -Arguments @('cp', "db:$dump", (Join-Path $backup 'database.dump'))
    Invoke-Compose -Arguments @('exec', '-T', 'db', 'rm', '--', $dump)
    $archive = "/var/lib/odoo/kim-deploy-$stamp.tgz"
    Invoke-Compose -Arguments @('run', '--rm', '--no-deps', '--user', 'root', 'web', 'tar', '-czf', $archive,
        '-C', '/var/lib/odoo/.local/share/Odoo/filestore', '--', $config.Database)
    Invoke-Compose -Arguments @('cp', "web:$archive", (Join-Path $backup 'filestore.tgz'))
    Invoke-Compose -Arguments @('run', '--rm', '--no-deps', '--user', 'root', 'web', 'rm', '--', $archive)
    Invoke-Checked -Program 'git' -Arguments @('-C', $repo, 'merge', '--ff-only', $target)
    Invoke-Compose -Arguments @('config', '--quiet')
    # Isolated process; the serving Odoo must remain stopped throughout migration.
    Invoke-Compose -Arguments @('run', '--rm', '--no-deps', 'web', 'odoo', '-d', $config.Database,
        '-u', ($modules -join ','), '--stop-after-init', '--no-http', '--max-cron-threads=0')
    Invoke-Compose -Arguments @('up', '-d', '--no-deps', '--force-recreate', 'web')
    $deadline = (Get-Date).AddSeconds([int]$config.HealthTimeoutSeconds)
    $healthy = $false
    do {
        try {
            $response = Invoke-WebRequest -Uri $config.HealthUrl -UseBasicParsing -TimeoutSec 10
            $healthy = $response.StatusCode -eq 200 -and $response.Content -match 'name=["'']login["'']'
        } catch { $healthy = $false }
        if (-not $healthy) { Start-Sleep -Seconds 3 }
    } while (-not $healthy -and (Get-Date) -lt $deadline)
    if (-not $healthy) { throw 'Odoo login health check failed.' }
    @{ Commit = $target; Database = $config.Database; Signature = "$($config.Database)|$($modules -join ',')|$($config.HealthUrl)";
        DeployedAt = (Get-Date).ToString('o'); Backup = $backup } |
        ConvertTo-Json | Set-Content -LiteralPath $successFile -Encoding UTF8
    Remove-Item -LiteralPath $pending
    $maintenance = $false
    Write-Host "Deployment succeeded: $target"
} catch {
    if ($maintenance) {
        # A migration may have changed schema. Do not automatically run old code against it.
        try { Invoke-Compose -Arguments @('stop', 'web') } catch { Write-Warning 'Could not stop web; check Docker manually.' }
        Write-Warning 'Deployment stopped. Web is left stopped; inspect backup and logs. No automatic database rollback.'
    }
    Write-Error -Message $_ -ErrorAction Continue
    exit 1
} finally {
    if ($logging) { Stop-Transcript | Out-Null }
    if ($null -ne $lock) { $lock.Dispose() }
}
