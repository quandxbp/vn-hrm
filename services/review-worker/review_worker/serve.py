"""Windows/Linux entry point: load .env (no override), lower priority, then run uvicorn."""
import os
import sys
from pathlib import Path


def load_env(path):
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        os.environ.setdefault(name.strip(), value.strip())


def lower_priority():
    try:
        import psutil
        proc = psutil.Process()
        if sys.platform == 'win32':
            proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            proc.nice(10)
    except Exception:  # noqa: BLE001 - priority is best effort
        pass


def main():
    load_env(os.environ.get('WORKER_ENV_FILE', Path(__file__).resolve().parents[1] / '.env.worker'))
    lower_priority()  # children (spawned stages, ffmpeg, tesseract) inherit the priority class
    import uvicorn
    from .config import load
    settings = load()
    uvicorn.run('review_worker.app:app', host=settings.bind, port=settings.port, workers=1, log_level='info')


if __name__ == '__main__':
    main()
