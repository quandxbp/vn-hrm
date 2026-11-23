"""ffprobe/ffmpeg helpers. Every output is written atomically so a crash never leaves a half file."""
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

BIN = {'ffmpeg': os.environ.get('FFMPEG_BIN', 'ffmpeg'), 'ffprobe': os.environ.get('FFPROBE_BIN', 'ffprobe')}


def atomic_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def probe(video):
    out = subprocess.run([BIN['ffprobe'], '-v', 'error', '-show_entries', 'format=duration:stream=codec_type',
                          '-of', 'json', str(video)], capture_output=True, text=True, timeout=120, check=True)
    info = json.loads(out.stdout)
    duration = float(info.get('format', {}).get('duration') or 0)
    kinds = {s.get('codec_type') for s in info.get('streams', [])}
    if not math.isfinite(duration) or duration <= 0 or 'video' not in kinds:
        raise RuntimeError('probe')
    return {'duration': round(duration, 3), 'has_audio': 'audio' in kinds}


def extract_audio(video, wav):
    tmp = Path(str(wav) + '.tmp.wav')
    subprocess.run([BIN['ffmpeg'], '-nostdin', '-v', 'error', '-y', '-i', str(video), '-vn', '-ac', '1', '-ar', '16000',
                    '-c:a', 'pcm_s16le', str(tmp)], timeout=3600, check=True)
    os.replace(tmp, wav)


def extract_frames(video, folder, interval, width=1280):
    """One JPEG every `interval` seconds, starting at 00:00. File n is at n*interval seconds."""
    folder = Path(folder)
    tmp = folder.with_name(folder.name + '.tmp')
    if tmp.exists():
        for item in tmp.iterdir():
            item.unlink()
    tmp.mkdir(exist_ok=True)
    subprocess.run([BIN['ffmpeg'], '-nostdin', '-v', 'error', '-y', '-i', str(video),
                    '-vf', 'fps=1/%d,scale=%d:-2' % (interval, width), '-q:v', '4',
                    '-start_number', '0', str(tmp / '%05d.jpg')], timeout=3600, check=True)
    if folder.exists():
        # A restart after extraction but before OCR finished; Windows cannot replace a directory.
        shutil.rmtree(folder)
    os.replace(tmp, folder)
    return sorted(folder.glob('*.jpg'))
