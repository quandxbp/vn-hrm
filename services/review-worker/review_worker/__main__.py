"""Benchmark CLI: run the pipeline on local files without Odoo or network uploads.

python -m review_worker bench --roster roster.json --planned 60 part1.mp4 [part2.mp4 ...]
Prints metrics; writes result.json next to the job folder for manual review.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import uuid

from .config import load
from .pipeline import Pipeline
from .store import Store


def md5(path):
    digest = hashlib.md5()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(8 * 1024 ** 2), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    from .serve import load_env, lower_priority
    load_env(os.environ.get('WORKER_ENV_FILE', os.path.join(os.path.dirname(__file__), '..', '.env.worker')))
    lower_priority()
    parser = argparse.ArgumentParser(prog='review_worker')
    sub = parser.add_subparsers(dest='cmd', required=True)
    bench = sub.add_parser('bench')
    bench.add_argument('videos', nargs='+')
    bench.add_argument('--roster', help='JSON list of {key,label,aliases}')
    bench.add_argument('--planned', type=float, default=0)
    bench.add_argument('--out', default='result.json')
    args = parser.parse_args()

    settings = load()
    store = Store(settings.data_dir)
    roster = json.load(open(args.roster, encoding='utf-8')) if args.roster else []
    parts = [{'number': i + 1, 'size': os.path.getsize(v), 'md5': md5(v)} for i, v in enumerate(args.videos)]
    key = 'bench-' + uuid.uuid4().hex[:12]
    store.create(key, {'roster': roster, 'planned_minutes': args.planned, 'parts': parts, 'prompt_version': '2.1'})
    for part, video in zip(parts, args.videos):
        shutil.copyfile(video, store.part_path(key, part['number']))
        store.mark_verified(key, part['number'])
    store.start(key)
    store.claim_next()
    Pipeline(store, settings).run(key)
    job = store.get(key)
    with open(args.out, 'w', encoding='utf-8') as output:
        json.dump({'durations': job['durations'], 'result': job['result'], 'metrics': job['metrics']},
                  output, ensure_ascii=False, indent=2)
    json.dump(job['metrics'], sys.stdout, indent=2)
    print('\njob', key, '->', args.out)


if __name__ == '__main__':
    main()
