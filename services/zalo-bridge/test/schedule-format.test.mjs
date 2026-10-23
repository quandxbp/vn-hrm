import { test } from 'node:test';
import assert from 'node:assert/strict';
import { scheduleStyles } from '../src/schedule-format.mjs';

test('styles key schedule sections using Zalo native text properties without styling URLs', () => {
    const text = 'LỊCH HỌC GVNN — 23/10/2026\n\n17:30–18:00 | THẦY MOSHOOD\nHỌC VIÊN: HỌC SINH A - ALEX\n\nLINK HỌC THẦY, CÔ\n- THẦY MOSHOOD: https://example.zoom.us/j/ABC?pwd=MixedCase';
    const styles = scheduleStyles(text);
    const has = (content, type) => styles.some(s => text.slice(s.start, s.start + s.len) === content && s.st === type);
    assert.ok(has('LỊCH HỌC GVNN — 23/10/2026', 'b'));
    assert.ok(has('LỊCH HỌC GVNN — 23/10/2026', 'c_15a85f'));
    assert.ok(has('17:30–18:00 | THẦY MOSHOOD', 'b'));
    assert.ok(!styles.some(s => s.st.startsWith('f_')));
    assert.ok(has('THẦY MOSHOOD', 'c_15a85f'));
    assert.ok(has('LINK HỌC THẦY, CÔ', 'b'));
    assert.ok(!styles.some(s => s.st === 'c_db342e' || s.st === 'c_f27806'));
    assert.ok(styles.every(s => s.start >= 0 && s.len > 0 && s.start + s.len <= text.length));
    assert.ok(styles.every(s => !text.slice(s.start, s.start + s.len).includes('https://')));
});

test('uses UTF-16 offsets for emoji and formats split parts independently', () => {
    const part = '😀\n19:00–19:30 | CÔ ZAHRA\nHỌC VIÊN: ANNA';
    const styles = scheduleStyles(part);
    assert.ok(styles.some(s => s.start === 3 && s.st === 'b'));
    assert.ok(styles.some(s => part.slice(s.start, s.start + s.len) === 'CÔ ZAHRA' && s.st === 'c_15a85f'));
    assert.ok(scheduleStyles('- CÔ ZAHRA: https://meet.google.com/a').some(s => s.start === 2 && s.len === 8));
});

test('styles grouped teacher headings and every lesson, leaving group links clickable', () => {
    const text = 'LỊCH HỌC GVNN — 23/10/2026\n\nThầy MOSHOOD\n17:30–18:00: ALEX\n21:00–21:30: JOHNSON\nLINK HỌC: https://meet.google.com/abc\n\nCô ZAHRA\n18:30–19:00: RYAN\nLINK HỌC: https://zoom.us/j/123';
    const styles = scheduleStyles(text);
    const has = (content, type) => styles.some(s => text.slice(s.start, s.start + s.len) === content && s.st === type);
    assert.ok(has('Thầy MOSHOOD', 'c_15a85f'));
    assert.ok(has('Cô ZAHRA', 'b'));
    for (const time of ['17:30–18:00', '21:00–21:30', '18:30–19:00']) assert.ok(has(time, 'b'));
    assert.equal(styles.filter(s => text.slice(s.start, s.start + s.len) === 'LINK HỌC:').length, 2);
    assert.ok(styles.every(s => !text.slice(s.start, s.start + s.len).includes('https://')));
    assert.ok(!styles.some(s => s.st.startsWith('f_')));
    assert.ok(!styles.some(s => text.slice(s.start, s.start + s.len).includes('ALEX')));
});
