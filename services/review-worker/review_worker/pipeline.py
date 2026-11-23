"""Sequential job pipeline with a checkpoint file after every stage.

Heavy stages (ASR, OCR, LLM) run in a spawned child process so their memory is returned to
the OS before the next model loads. A restart resumes from the last checkpoint file.
"""
import logging
import multiprocessing
import threading
import time

from . import PIPELINE_VERSION, media
from .roster import Matcher

_logger = logging.getLogger('review_worker')
CHUNK_WINDOWS = 10
LLM_FILE = 'llm-v5.json'  # bump when synthesis logic changes; ASR/visual/map caches stay valid


class Cancelled(Exception):
    pass


def _child(fn, args, queue):
    try:
        queue.put(('ok', fn(*args)))
    except BaseException as exc:  # report type only; messages may contain transcript text
        queue.put(('error', '%s:%s' % (type(exc).__name__, str(exc)[:120] if type(exc).__name__ == 'LLMError' else '')))


PEAK = {'mb': 0.0}


def _sample(pid, stop):
    """Sample child RSS (process + its ffmpeg/tesseract children). Works on Windows and Linux."""
    import psutil

    try:
        proc = psutil.Process(pid)
        while not stop.is_set():
            try:
                total = proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True))
                PEAK['mb'] = max(PEAK['mb'], round(total / 1024 ** 2, 1))
            except psutil.Error:
                pass
            stop.wait(1)
    except psutil.Error:
        pass


def isolated(fn, *args):
    ctx = multiprocessing.get_context('spawn')
    queue = ctx.Queue()
    proc = ctx.Process(target=_child, args=(fn, args, queue))
    proc.start()
    stop = threading.Event()
    sampler = threading.Thread(target=_sample, args=(proc.pid, stop), daemon=True)
    sampler.start()
    import queue as queue_module
    try:
        while True:
            try:
                status, value = queue.get(timeout=5)
                break
            except queue_module.Empty:
                # A native crash (access violation) kills the child without a message.
                if not proc.is_alive():
                    status, value = 'error', 'ChildCrashed:exit=%s' % proc.exitcode
                    break
    finally:
        proc.join(timeout=30)
        stop.set()
        sampler.join(timeout=5)
    if status != 'ok':
        raise RuntimeError(value)
    return value


def peak_rss_mb():
    return PEAK['mb']


# ----------------------------------------------------------------- stage functions (child processes)
def _asr(wav, out, settings):
    from .asr import transcribe
    media.atomic_json(out, transcribe(wav, settings))
    return True


def _visual(video, folder, out, settings):
    from .visual import analyse_frames
    frames = media.extract_frames(video, folder, settings.frame_interval)
    media.atomic_json(out, analyse_frames(frames, settings.frame_interval, settings))
    return True


def _llm_stage(job_dir, spec, parts, visuals, settings):
    from . import llm, synth

    matcher = Matcher(spec.get('roster'))
    model = llm.backend(settings)
    labels, notes, timeline, segments_by_part, rows_by_part = {}, [], {}, {}, {}
    usage = {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0}
    pseudo = {n: dict(p, segments=[dict(s, text=matcher.pseudonymize(s['text'])) for s in p['segments']])
              for n, p in parts.items()}
    for number in sorted(parts):
        part = pseudo[number]
        rows = synth.windows(number, part, visuals.get(number), settings.window_seconds, matcher)
        rows_by_part[number] = rows
        part_labels = {}
        for index, chunk in enumerate(synth.chunks(rows, CHUNK_WINDOWS)):
            path = job_dir / ('map-%02d-%03d.json' % (number, index))
            if path.exists():
                result = media.read_json(path)
            else:
                if not any(w['speech'] for w in chunk):
                    result = {'windows': [], 'topics': [], 'notes': []}  # silent chunk: no LLM call
                else:
                    result, used = model.complete(synth.SYSTEM, synth.map_prompt(number, part, chunk),
                                                  synth.map_schema(chunk), max_tokens=1200)
                    usage['calls'] += 1
                    for k in ('prompt_tokens', 'completion_tokens'):
                        usage[k] += int(used.get(k) or 0)
                media.atomic_json(path, result)
            part_labels.update(synth.labels_from_map(chunk, result))
            for topic in result.get('topics') or []:
                if isinstance(topic, dict) and topic.get('text'):
                    notes.append({'kind': 'topic', 'text': str(topic['text'])[:400],
                                  'evidence': [str(e) for e in topic.get('evidence') or []][:3]})
            for note in result.get('notes') or []:
                if isinstance(note, dict) and note.get('text'):
                    notes.append({'kind': str(note.get('kind', 'note')), 'text': str(note['text'])[:400],
                                  'evidence': [str(e) for e in note.get('evidence') or []][:3]})
        labels[number] = part_labels
    # Lesson start/end from a dedicated call: a 7B model labeling 10 windows at once tends to
    # repeat one label ("setup" for 9 minutes of continuous teaching in the first benchmark).
    path = job_dir / 'boundary.json'
    if path.exists():
        bound = media.read_json(path)
    elif any(p['segments'] for p in pseudo.values()):
        bound, used = model.complete(synth.SYSTEM, synth.boundary_prompt(pseudo), synth.boundary_schema(pseudo),
                                     max_tokens=300)
        usage['calls'] += 1
        for k in ('prompt_tokens', 'completion_tokens'):
            usage[k] += int(used.get(k) or 0)
        media.atomic_json(path, bound)
    else:
        bound = {}
    start, end = synth.boundary_seconds(parts, bound)
    start = synth.earliest_start(start, synth.cue_start(parts))
    clips = synth.apply_boundaries(rows_by_part, labels, start, end)
    for number in sorted(parts):
        timeline[number] = synth.timeline_text(rows_by_part[number], labels[number])
        segments_by_part[number] = synth.teaching_segments(rows_by_part[number], labels[number],
                                                           clip_start=clips[number][0], clip_end=clips[number][1])
    teaching = sum(e - s for spans in segments_by_part.values() for s, e in spans)
    boundary = {'start': start, 'end': end, 'start_reason': str(bound.get('start_reason', ''))[:300],
                'end_reason': str(bound.get('end_reason', ''))[:300]}
    path = job_dir / 'reduce-v4.json'
    if path.exists():
        reduced = media.read_json(path)
    else:
        reduced, used = model.complete(synth.SYSTEM, synth.reduce_prompt(spec, parts, timeline, notes, teaching, boundary),
                                       synth.reduce_schema(), max_tokens=2500)
        usage['calls'] += 1
        for k in ('prompt_tokens', 'completion_tokens'):
            usage[k] += int(used.get(k) or 0)
        media.atomic_json(path, reduced)
    media.atomic_json(job_dir / LLM_FILE, {'reduced': reduced, 'segments': {str(k): v for k, v in segments_by_part.items()},
                                           'boundary': boundary, 'usage': usage})
    return True


# ----------------------------------------------------------------- orchestration
class Pipeline:
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings

    def _check(self, key):
        if self.store.row(key)['state'] != 'running':
            raise Cancelled()

    def _stage(self, key, stage, progress, timings, fn, *args):
        self._check(key)
        self.store.update(key, stage=stage, progress=progress)
        started = time.monotonic()
        result = isolated(fn, *args) if fn in (_asr, _visual, _llm_stage) else fn(*args)
        timings[stage] = round(timings.get(stage, 0) + time.monotonic() - started, 1)
        return result

    def run(self, key):
        from . import synth

        spec = self.store.spec(key)
        job_dir = self.store.job_dir(key)
        timings = {}
        started = time.monotonic()
        PEAK['mb'] = 0.0
        numbers = sorted(p['number'] for p in spec['parts'])
        parts, visuals, probes = {}, {}, {}
        steps = len(numbers) * 3 + 2
        done = 0
        for number in numbers:
            video = self.store.part_path(key, number)
            probe_path = job_dir / ('probe-%02d.json' % number)
            if not probe_path.exists():
                media.atomic_json(probe_path, self._stage(key, 'probe', done / steps, timings, media.probe, video))
            probes[number] = media.read_json(probe_path)
            asr_path = job_dir / ('asr-%02d.json' % number)
            if not asr_path.exists():
                if probes[number]['has_audio']:
                    wav = job_dir / ('part-%02d.wav' % number)
                    if not wav.exists():
                        self._stage(key, 'audio', done / steps, timings, media.extract_audio, video, wav)
                    self._stage(key, 'asr', (done + 0.5) / steps, timings, _asr, wav, asr_path, self.settings)
                    wav.unlink(missing_ok=True)
                else:
                    media.atomic_json(asr_path, {'language': None, 'segments': []})
            done += 1
            visual_path = job_dir / ('visual-%02d.json' % number)
            if not visual_path.exists():
                self._stage(key, 'visual', done / steps, timings, _visual, video,
                            job_dir / ('frames-%02d' % number), visual_path, self.settings)
            done += 2
            parts[number] = {'duration': probes[number]['duration'],
                             'segments': media.read_json(asr_path)['segments']}
            visuals[number] = media.read_json(visual_path)
        durations = {str(n): probes[n]['duration'] for n in numbers}
        self.store.update(key, durations=durations)
        if not (job_dir / LLM_FILE).exists():
            self._stage(key, 'synthesis', done / steps, timings, _llm_stage, job_dir, spec, parts, visuals, self.settings)
        llm_out = media.read_json(job_dir / LLM_FILE)
        self._check(key)
        matcher = Matcher(spec.get('roster'))
        evidence = synth.Evidence(parts, self.settings.window_seconds)
        segments_by_part = {int(k): [tuple(s) for s in v] for k, v in llm_out['segments'].items()}
        spoken = synth.spoken_counts(spec.get('roster') or [], parts, matcher)
        students = synth.student_observations(spec.get('roster') or [], parts, visuals, matcher,
                                              self.settings.frame_interval, spoken)
        total = sum(p['duration'] for p in parts.values())
        speech = sum(min(s['end'], p['duration']) - s['start'] for p in parts.values() for s in p['segments'])
        result = synth.assemble(llm_out['reduced'], evidence, parts, segments_by_part, students,
                                speech / total if total else 0, any(p['has_audio'] for p in probes.values()))
        metrics = {'pipeline_version': PIPELINE_VERSION, 'backend': self.settings.synth_backend,
                   'whisper_model': self.settings.whisper_model, 'wall_seconds': round(time.monotonic() - started, 1),
                   'video_seconds': round(total, 1), 'stage_seconds': timings, 'peak_child_rss_mb': peak_rss_mb(),
                   'llm_usage': llm_out.get('usage')}
        self.store.update(key, state='done', stage='done', progress=1, result=result, metrics=metrics,
                          error=None, finished=time.time())
        self.store.drop_media(key)  # video/audio/frames go right away; transcript stays until ack or expiry
        _logger.info('job %s done in %ss', key, metrics['wall_seconds'])
        return result
