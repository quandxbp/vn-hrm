import os
from dataclasses import dataclass
from pathlib import Path


def _env(name, default=''):
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    token: str
    retention_hours: int
    max_attempts: int
    threads: int
    window_seconds: int
    frame_interval: int
    whisper_model: str
    whisper_dir: str
    whisper_language: str
    whisper_beam: int
    ocr_langs: str
    synth_backend: str
    llm_model_path: str
    llm_ctx: int
    api_base: str
    api_key: str
    api_model: str
    run_window: str
    ffmpeg: str
    ffprobe: str
    tesseract: str
    bind: str
    port: int


def load():
    return Settings(
        data_dir=Path(_env('WORKER_DATA_DIR', '/data')),
        token=_env('WORKER_TOKEN'),
        retention_hours=int(_env('WORKER_RETENTION_HOURS', '72')),
        max_attempts=int(_env('WORKER_MAX_ATTEMPTS', '3')),
        threads=int(_env('WORKER_THREADS', '4')),
        window_seconds=int(_env('WORKER_WINDOW_SECONDS', '60')),
        frame_interval=int(_env('WORKER_FRAME_INTERVAL', '10')),
        whisper_model=_env('WHISPER_MODEL', 'small'),
        whisper_dir=_env('WHISPER_DIR', '/models/whisper'),
        whisper_language=_env('WHISPER_LANGUAGE', 'en'),
        whisper_beam=int(_env('WHISPER_BEAM', '1')),
        ocr_langs=_env('OCR_LANGS', 'eng+vie'),
        synth_backend=_env('SYNTH_BACKEND', 'local'),
        llm_model_path=_env('LLM_MODEL_PATH', '/models/llm/Qwen2.5-7B-Instruct-Q4_K_M.gguf'),
        llm_ctx=int(_env('LLM_CTX', '12288')),
        api_base=_env('SYNTH_API_BASE'),
        api_key=_env('SYNTH_API_KEY'),
        api_model=_env('SYNTH_API_MODEL'),
        run_window=_env('WORKER_RUN_WINDOW'),  # '' = always, or 'HH:MM-HH:MM' local time
        ffmpeg=_env('FFMPEG_BIN', 'ffmpeg'),
        ffprobe=_env('FFPROBE_BIN', 'ffprobe'),
        tesseract=_env('TESSERACT_BIN', 'tesseract'),
        bind=_env('WORKER_BIND', '127.0.0.1'),
        port=int(_env('WORKER_PORT', '8090')),
    )
