"""Worker output must pass the real Odoo validator (custom-addons/edu_session_review/models/report.py)."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

odoo = types.ModuleType('odoo')
exceptions = types.ModuleType('odoo.exceptions')
exceptions.UserError = type('UserError', (Exception,), {})
odoo.exceptions = exceptions
sys.modules.setdefault('odoo', odoo)
sys.modules.setdefault('odoo.exceptions', exceptions)
spec = importlib.util.spec_from_file_location('report', ROOT / 'custom-addons/edu_session_review/models/report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

from review_worker import synth  # noqa: E402
from review_worker.roster import Matcher  # noqa: E402
from review_worker.store import Conflict, Store  # noqa: E402

ROSTER = [{'key': 'student_11', 'label': 'NGUYỄN AN', 'aliases': ['NGUYỄN AN', 'An Nguyen']},
          {'key': 'student_12', 'label': 'TRẦN BÌNH', 'aliases': ['TRẦN BÌNH']},
          {'key': 'student_13', 'label': 'LÊ CHI', 'aliases': ['LÊ CHI']}]


def segs(start, end, step=20, text='Repeat after me: I usually go to school by bus.'):
    return [{'start': t, 'end': min(t + step - 2, end), 'text': text} for t in range(start, end, step)]


def frames(duration, names_at):
    """names_at(t) -> visible tile names at second t."""
    return {'interval': 10, 'frames': [{'t': t, 'brightness': 90.0, 'change': 1.0, 'text': ' '.join(names_at(t))}
                                       for t in range(0, int(duration), 10)]}


def build(parts, visuals, llm_out, labels_fn):
    matcher = Matcher(ROSTER)
    seg_by_part = {}
    for n, p in parts.items():
        rows = synth.windows(n, p, visuals.get(n), 60, matcher)
        labels = {w['id']: labels_fn(n, w) for w in rows}
        seg_by_part[n] = synth.teaching_segments(rows, labels)
    students = synth.student_observations(ROSTER, parts, visuals, matcher, 10)
    evidence = synth.Evidence(parts, 60)
    total = sum(p['duration'] for p in parts.values())
    speech = sum(s['end'] - s['start'] for p in parts.values() for s in p['segments'])
    return synth.assemble(llm_out, evidence, parts, seg_by_part, students, speech / total, True)


GOOD = {'summary': 'Buổi học luyện mẫu câu về phương tiện đi học.', 'sufficient_data': True, 'quality_note': '',
        'interaction_level': 'good', 'interaction_comment': 'Học sinh được gọi trả lời nhiều lượt.',
        'lesson_content': [{'comment': 'Mẫu câu "I usually go to school by ..."', 'evidence': ['S1.3', 'W1.2']}],
        'strengths': [{'comment': 'Làm mẫu rõ trước khi cho học sinh lặp lại.', 'evidence': ['S1.4']}],
        'improvements': [{'comment': 'Nên cho học sinh tự đặt câu.', 'evidence': ['S2.1', 'X9.9']}],
        'timing_note': 'Bắt đầu dạy sau phần chào hỏi.',
        'rubric': {k: {'score': 2.04, 'reason': 'Có căn cứ.', 'evidence': ['S1.5']}
                   for k in ('content', 'instruction', 'interaction', 'management')}}


class Contract(unittest.TestCase):
    def two_parts(self):
        parts = {1: {'duration': 1500.4, 'segments': segs(0, 1500)}, 2: {'duration': 1200.0, 'segments': segs(0, 1200)}}
        # student_11 and 12 visible from the start; 13 joins at 05:00 of part 1 after the list was readable.
        visuals = {1: frames(1500.4, lambda t: ['NGUYỄN AN', 'TRẦN BÌNH'] + (['LÊ CHI'] if t >= 300 else [])),
                   2: frames(1200, lambda t: ['NGUYỄN AN', 'TRẦN BÌNH', 'LÊ CHI'])}
        return parts, visuals

    def labels(self, n, w):
        return 'greeting' if n == 1 and w['k'] < 2 else 'teaching'

    def validate(self, data, parts):
        durations = {n: p['duration'] for n, p in parts.items()}
        return report.validate_report(data, durations, require_v2=True, require_students=True,
                                      roster=ROSTER, planned_minutes=60)

    def test_full_report_passes_odoo_validator(self):
        parts, visuals = self.two_parts()
        data = build(parts, visuals, GOOD, self.labels)
        values = self.validate(data, parts)
        self.assertTrue(values['score_available'])
        self.assertEqual(values['score_total'], 8.0)
        self.assertEqual(values['teaching_started_at'], 'Phần 1 · 02:00')
        self.assertIn('Vào trễ', values['student_report'])          # LÊ CHI joined 03:00 after teaching start
        self.assertNotIn('X9.9', str(data))                         # unknown evidence id dropped
        self.assertNotIn('student_', data['summary'])

    def test_timestamps_never_exceed_floor_of_duration(self):
        parts, visuals = self.two_parts()
        data = build(parts, visuals, GOOD, lambda n, w: 'teaching')
        last = data['parts'][0]['teaching_segments'][-1]['end']
        self.assertLessEqual(report.timestamp(last), 1500)
        self.validate(data, parts)

    def test_silent_video_is_insufficient_with_null_scores(self):
        parts = {1: {'duration': 1800.0, 'segments': segs(0, 60)}}
        visuals = {1: frames(1800, lambda t: [])}
        data = build(parts, visuals, GOOD, lambda n, w: 'no_data')
        values = self.validate(data, parts)
        self.assertFalse(data['sufficient_data'])
        self.assertFalse(values['score_available'])
        self.assertEqual(data['interaction_level'], 'insufficient')

    def test_unreadable_screen_never_claims_absence(self):
        parts, _ = self.two_parts()
        visuals = {1: frames(1500.4, lambda t: []), 2: frames(1200, lambda t: [])}
        data = build(parts, visuals, GOOD, self.labels)
        self.assertTrue(all(s['attendance'] == 'uncertain' for s in data['student_observations']))
        values = self.validate(data, parts)
        self.assertNotIn('CẢNH BÁO: Chưa thấy', values['student_report'])

    def test_absence_needs_every_part_readable(self):
        parts, _ = self.two_parts()
        visuals = {1: frames(1500.4, lambda t: ['NGUYỄN AN', 'TRẦN BÌNH']), 2: frames(1200, lambda t: ['NGUYỄN AN'])}
        data = build(parts, visuals, GOOD, self.labels)
        chi = next(s for s in data['student_observations'] if s['student_key'] == 'student_13')
        self.assertEqual(chi['attendance'], 'not_observed')
        self.assertIn('CẢNH BÁO: Chưa thấy', self.validate(data, parts)['student_report'])

    def test_missing_llm_output_still_valid_and_insufficient(self):
        parts, visuals = self.two_parts()
        data = build(parts, visuals, {}, self.labels)
        self.assertFalse(data['sufficient_data'])
        self.validate(data, parts)

    def test_silent_gap_between_teaching_is_kept(self):
        parts = {1: {'duration': 600.0, 'segments': segs(0, 180) + segs(300, 600)}}
        matcher = Matcher(ROSTER)
        rows = synth.windows(1, parts[1], None, 60, matcher)
        labels = {w['id']: ('teaching' if w['speech'] else 'no_data') for w in rows}
        self.assertEqual(len(synth.teaching_segments(rows, labels)), 1)


class Regressions(unittest.TestCase):
    """Failures seen on the first real benchmark (session 42, 2026-11-22)."""

    def test_repeated_setup_labels_inside_lesson_count_as_teaching(self):
        parts = {1: {'duration': 1805.5, 'segments': segs(20, 1800)}}
        matcher = Matcher(ROSTER)
        rows = synth.windows(1, parts[1], None, 60, matcher)
        labels = {1: {w['id']: ('greeting' if w['k'] == 0 else 'setup' if w['k'] < 10 else 'teaching') for w in rows}}
        # model said teaching starts at the segment at ~01:40
        n = next(i for i, s in enumerate(parts[1]['segments']) if s['start'] >= 100)
        start, end = synth.boundary_seconds(parts, {'start_id': 'S1.%d' % n, 'end_id': 'S1.%d' % (len(parts[1]['segments']) - 1)})
        clips = synth.apply_boundaries({1: rows}, labels, start, end)
        spans = synth.teaching_segments(rows, labels[1], clip_start=clips[1][0], clip_end=clips[1][1])
        self.assertEqual(spans[0][0], 100)
        self.assertGreater(sum(e - s for s, e in spans), 1600)

    def test_invalid_boundary_ids_change_nothing(self):
        parts = {1: {'duration': 600.0, 'segments': segs(0, 600)}}
        self.assertEqual(synth.boundary_seconds(parts, {'start_id': 'S9.9', 'end_id': 'x'}), (None, None))

    def test_spoken_name_blocks_absence_claim(self):
        parts, _ = Contract().two_parts()
        # tiles readable for AN and BÌNH in every frame; CHI never on screen but called by name
        visuals = {1: frames(1500.4, lambda t: ['NGUYỄN AN', 'TRẦN BÌNH']), 2: frames(1200, lambda t: ['NGUYỄN AN', 'TRẦN BÌNH'])}
        parts[1]['segments'][3] = dict(parts[1]['segments'][3], text='Chi, can you read number two?')
        matcher = Matcher(ROSTER)
        spoken = synth.spoken_counts(ROSTER, parts, matcher)
        self.assertEqual(spoken['student_13'], 1)
        obs = synth.student_observations(ROSTER, parts, visuals, matcher, 10, spoken)
        chi = next(s for s in obs if s['student_key'] == 'student_13')
        self.assertEqual(chi['attendance'], 'uncertain')

    def test_names_read_in_few_frames_do_not_enable_absence(self):
        parts, _ = Contract().two_parts()
        visuals = {1: frames(1500.4, lambda t: ['TRẦN BÌNH'] if t < 20 else []),
                   2: frames(1200, lambda t: ['TRẦN BÌNH'] if t < 20 else [])}
        obs = synth.student_observations(ROSTER, parts, visuals, Matcher(ROSTER), 10, {})
        self.assertNotIn('not_observed', {s['attendance'] for s in obs})


    def test_lesson_opening_phrase_beats_late_model_start(self):
        # session 27: model chose 05:42, teacher opened the lesson at 03:54 (plain hello before it)
        part = {'duration': 1700.0, 'segments': [{'start': 91, 'end': 95, 'text': 'Hello teacher. Hello Ellie.'},
                                                  {'start': 234, 'end': 250, 'text': 'So in our last lesson, this is where we stopped'},
                                                  {'start': 342, 'end': 350, 'text': 'which one will you choose'}]}
        parts = {1: part}
        model, _ = synth.boundary_seconds(parts, {'start_id': 'S1.2', 'end_id': 'S1.2'})
        self.assertEqual(synth.earliest_start(model, synth.cue_start(parts)), (1, 234))
        self.assertEqual(synth.earliest_start(None, None), None)

    def test_warm_up_question_counts_as_teaching_start(self):
        parts = {1: {'duration': 1700.0, 'segments': [{'start': 60, 'end': 62, 'text': 'Can you hear me?'},
                                                       {'start': 91, 'end': 95, 'text': 'Hello Ellie. How are you today?'},
                                                       {'start': 234, 'end': 250, 'text': 'So in our last lesson'}]}}
        self.assertEqual(synth.cue_start(parts), (1, 91))

    def test_start_inside_quiet_greeting_window_is_exact(self):
        segments = [{'start': 92, 'end': 96, 'text': 'How are you today, Ellie?'},
                    {'start': 100, 'end': 106, 'text': 'Fine, thank you.'}] + segs(120, 900)
        parts = {1: {'duration': 900.0, 'segments': segments}}
        rows = synth.windows(1, parts[1], None, 60, Matcher(ROSTER))
        labels = {1: {w['id']: ('greeting' if w['k'] == 1 else 'teaching' if w['speech'] else 'no_data') for w in rows}}
        clips = synth.apply_boundaries({1: rows}, labels, synth.cue_start(parts), (1, 900))
        spans = synth.teaching_segments(rows, labels[1], clip_start=clips[1][0], clip_end=clips[1][1])
        self.assertEqual(spans[0][0], 92)

    def test_task_before_silence_keeps_silent_work_as_teaching(self):
        # session 27 part 2: "check the supporting opinion" then 2.5 minutes of silent reading
        segments = segs(0, 1380) + [{'start': 1435, 'end': 1440, 'text': 'Okay, keep check the support in opinion'}] + segs(1580, 1700)
        parts = {1: {'duration': 1700.0, 'segments': segments}}
        rows = synth.windows(1, parts[1], None, 60, Matcher(ROSTER))
        labels = {1: {w['id']: ('interruption' if w['k'] == 23 else 'teaching' if w['speech'] else 'no_data') for w in rows}}
        clips = synth.apply_boundaries({1: rows}, labels, (1, 0), (1, 1700))
        spans = synth.teaching_segments(rows, labels[1], clip_start=clips[1][0], clip_end=clips[1][1])
        self.assertEqual(len(spans), 1)

    def test_repeated_comments_are_dropped(self):
        parts, visuals = Contract().two_parts()
        same = 'Giáo viên thảo luận về việc học tin tức trong trường.'
        out = dict(GOOD, lesson_content=[{'comment': same, 'evidence': ['S1.1']}, {'comment': same + ' ', 'evidence': ['S1.2']},
                                         {'comment': 'Luyện mẫu câu "I usually go to school by bus".', 'evidence': ['S1.3']}])
        data = build(parts, visuals, out, Contract().labels)
        self.assertEqual(len(data['lesson_content']), 2)


class Pseudonym(unittest.TestCase):
    def test_names_replaced_and_common_words_kept(self):
        m = Matcher(ROSTER)
        text = m.pseudonymize('Good job An, now Bình please read. And you?')
        self.assertIn('[student_11]', text)
        self.assertIn('[student_12]', text)
        self.assertIn('And you?', text)


class StoreIdempotency(unittest.TestCase):
    def test_same_key_same_spec_returns_job_and_conflict_otherwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            spec = {'roster': ROSTER, 'planned_minutes': 60, 'prompt_version': '2.1',
                    'parts': [{'number': 1, 'size': 10, 'md5': '0' * 32}]}
            first = store.create('kim-0123456789ab', spec)
            self.assertEqual(store.create('kim-0123456789ab', spec)['key'], first['key'])
            with self.assertRaises(Conflict):
                store.create('kim-0123456789ab', dict(spec, planned_minutes=30))
            with self.assertRaises(Conflict):
                store.start('kim-0123456789ab')               # parts not verified yet
            store.mark_verified('kim-0123456789ab', 1)
            self.assertEqual(store.start('kim-0123456789ab')['state'], 'queued')
            self.assertEqual(store.start('kim-0123456789ab')['state'], 'queued')
            self.assertEqual(store.claim_next(), 'kim-0123456789ab')
            store.update('kim-0123456789ab', state='done', result={'x': 1})
            self.assertEqual(store.start('kim-0123456789ab')['state'], 'done')  # never re-queued


if __name__ == '__main__':
    unittest.main()
