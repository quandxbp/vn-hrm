import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { once } from 'node:events';
import { createBridge } from '../src/server.mjs';

const token = 'a'.repeat(40);
const groupId = 'test-group';
const key = 'b'.repeat(64);

async function setup(t, options = {}) {
    const dir = options.dir || fs.mkdtempSync(path.join(os.tmpdir(), 'kim-zalo-test-'));
    if (!options.dir) t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
    let calls = 0;
    const api = {
        getAllGroups: async () => ({ gridVerMap: { [groupId]: '1' } }),
        getGroupInfo: options.probe || (async () => ({ gridInfoMap: { [groupId]: { name: 'Nhóm thử' } } })),
        sendMessage: async (...args) => {
            calls++;
            if (options.send) return options.send(...args);
            await new Promise(resolve => setTimeout(resolve, 10));
            return { message: { msgId: calls } };
        },
    };
    const bridge = createBridge({ token, dataDir: dir, connect: options.connect || (async () => api),
        operationTimeout: options.operationTimeout || 1000,
        loginQR: async emit => { emit({ type: 'qr', image: 'test-image' }); return api; } });
    bridge.server.listen(0, '127.0.0.1');
    await once(bridge.server, 'listening');
    t.after(() => new Promise(resolve => bridge.server.close(resolve)));
    const url = `http://127.0.0.1:${bridge.server.address().port}`;
    async function request(endpoint, body, auth = token) {
        const response = await fetch(url + endpoint, { method: body ? 'POST' : 'GET',
            headers: { Authorization: `Bearer ${auth}`, 'Content-Type': 'application/json' },
            ...(body ? { body: JSON.stringify(body) } : {}) });
        return { status: response.status, body: await response.json() };
    }
    if (options.login !== false) {
        await request('/login', {});
        for (let i = 0; i < 20; i++) {
            if ((await request('/status')).body.state === 'connected') break;
            await new Promise(resolve => setTimeout(resolve, 5));
        }
        await request('/target', { group_id: groupId });
    }
    return { request, calls: () => calls, dir };
}

test('requires authentication and exposes no login session to unauthenticated callers', async t => {
    const b = await setup(t);
    assert.equal((await b.request('/status', undefined, 'bad')).status, 401);
    assert.equal((await b.request('/groups')).body.groups[0].name, 'Nhóm thử');
});

test('does not send before login, target confirmation, or with invalid content', async t => {
    const b = await setup(t, { login: false });
    assert.equal((await b.request('/messages', { key, group_id: groupId, parts: ['Lịch'] })).status, 503);
    await b.request('/login', {});
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.equal((await b.request('/messages', { key, group_id: groupId, parts: ['Lịch'] })).status, 400);
    assert.equal((await b.request('/messages', { key, group_id: groupId, parts: ['x'.repeat(1801)] })).status, 400);
    assert.equal(b.calls(), 0);
});

test('deduplicates concurrent requests, persists receipts and rejects changed content', async t => {
    const b = await setup(t);
    const body = { key, group_id: groupId, parts: ['Lịch 1', 'Lịch 2'] };
    const results = await Promise.all([b.request('/messages', body), b.request('/messages', body)]);
    assert.ok(results.every(r => r.body.state === 'sent'));
    assert.equal(b.calls(), 2);
    assert.equal((await b.request('/messages', body)).body.state, 'sent');
    assert.equal((await b.request('/messages', { ...body, parts: ['changed'] })).status, 409);
    const restarted = await setup(t, { dir: b.dir, login: false });
    assert.equal((await restarted.request('/messages', body)).body.state, 'sent');
    assert.equal(restarted.calls(), 0);
});

test('never repeats a possibly delivered message after timeout', async t => {
    const b = await setup(t, { send: async () => { throw new Error('Timed out after external send'); } });
    const body = { key, group_id: groupId, parts: ['Lịch'] };
    assert.equal((await b.request('/messages', body)).body.state, 'uncertain');
    assert.equal((await b.request('/messages', body)).body.state, 'uncertain');
    assert.equal(b.calls(), 1);
});

test('recovers interrupted deliveries as uncertain without sending again', async t => {
    const b = await setup(t);
    const body = { key, group_id: groupId, parts: ['Lịch'] };
    await b.request('/messages', body);
    const file = path.join(b.dir, 'deliveries.json');
    const ledger = JSON.parse(fs.readFileSync(file, 'utf8'));
    ledger[key].state = 'sending';
    fs.writeFileSync(file, JSON.stringify(ledger));
    const restarted = await setup(t, { dir: b.dir, login: false });
    assert.equal((await restarted.request('/messages', body)).body.state, 'uncertain');
    assert.equal(restarted.calls(), 0);
});

test('disconnect removes credentials and target but retains deduplication history', async t => {
    const b = await setup(t);
    const body = { key, group_id: groupId, parts: ['Lịch'] };
    await b.request('/messages', body);
    assert.equal((await b.request('/disconnect', {})).body.state, 'disconnected');
    assert.equal((await b.request('/status')).body.target, null);
    assert.equal((await b.request('/messages', body)).body.state, 'sent');
    assert.equal(b.calls(), 1);
});

test('passes native schedule styles to Zalo and retains plain-text compatibility', async t => {
    const sent = [];
    const b = await setup(t, { send: async content => {
        sent.push(content);
        return { message: { msgId: sent.length } };
    } });
    const text = 'LỊCH HỌC GVNN — 23/10/2026\n\n17:30–18:00 | THẦY MOSHOOD';
    await b.request('/messages', { key, group_id: groupId, parts: [text], format: 'schedule-v1' });
    assert.equal(sent[0].msg, text);
    assert.ok(sent[0].styles.some(s => s.st === 'b'));
    assert.ok(!sent[0].styles.some(s => s.st.startsWith('f_')));
    await b.request('/messages', { key: 'c'.repeat(64), group_id: groupId, parts: ['Plain text'] });
    assert.equal(sent[1].styles, undefined);
    assert.equal((await b.request('/messages', { key: 'd'.repeat(64), group_id: groupId, parts: ['Text'], format: 'unknown' })).status, 400);
    assert.equal(sent.length, 2);
});

test('failed preflight never starts a delivery and the same key can safely retry', async t => {
    let offline = false;
    const b = await setup(t, { probe: async () => {
        if (offline) throw new Error('private cookie must never be exposed');
        return { gridInfoMap: { [groupId]: { name: 'Test' } } };
    } });
    fs.writeFileSync(path.join(b.dir, 'credentials.json'), JSON.stringify({ test: true }));
    offline = true;
    const body = { key, group_id: groupId, parts: ['Schedule'] };
    const failed = await b.request('/messages', body);
    assert.equal(failed.status, 503);
    assert.equal(b.calls(), 0);
    assert.equal(JSON.stringify(failed).includes('private cookie'), false);
    assert.equal(JSON.parse(fs.readFileSync(path.join(b.dir, 'deliveries.json')))[key], undefined);
    assert.equal((await b.request('/status')).body.state, 'degraded');
    offline = false;
    assert.equal((await b.request('/messages', body)).body.state, 'sent');
    assert.equal(b.calls(), 1);
});

test('live check restores a stale session from stored credentials without sending', async t => {
    let offline = false;
    let reconnects = 0;
    const b = await setup(t, {
        probe: async () => {
            if (offline) throw Object.assign(new Error('offline'), { code: 'ECONNRESET' });
            return { gridInfoMap: { [groupId]: { name: 'Test' } } };
        },
        connect: async () => {
            reconnects++;
            return { getGroupInfo: async () => ({ gridInfoMap: { [groupId]: {} } }) };
        },
    });
    fs.writeFileSync(path.join(b.dir, 'credentials.json'), JSON.stringify({ test: true }));
    offline = true;
    const checks = await Promise.all([b.request('/check'), b.request('/check')]);
    assert.ok(checks.every(r => r.body.state === 'connected'));
    assert.equal(reconnects, 1);
    assert.equal(b.calls(), 0);
    assert.ok((await b.request('/status')).body.checked_at);
});

test('hung send is bounded, recorded as uncertain and never repeated', async t => {
    const b = await setup(t, { operationTimeout: 30, send: () => new Promise(() => {}) });
    const body = { key, group_id: groupId, parts: ['Schedule'] };
    const result = await b.request('/messages', body);
    assert.equal(result.body.state, 'uncertain');
    assert.equal(result.body.error_code, 'OPERATION_TIMEOUT');
    assert.equal((await b.request('/messages', body)).body.state, 'uncertain');
    assert.equal(b.calls(), 1);
});
