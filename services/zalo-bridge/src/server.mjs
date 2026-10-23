import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createHash, timingSafeEqual } from 'node:crypto';
import { scheduleStyles } from './schedule-format.mjs';

export function createBridge({ token, dataDir, connect, loginQR }) {
    if (!token || token.length < 32) throw new Error('A private token of at least 32 characters is required');
    fs.mkdirSync(dataDir, { recursive: true, mode: 0o700 });
    const read = (name, fallback) => {
        try { return JSON.parse(fs.readFileSync(path.join(dataDir, name), 'utf8')); }
        catch (error) { if (error.code === 'ENOENT') return fallback; throw error; }
    };
    const write = (name, value) => {
        const file = path.join(dataDir, name);
        fs.writeFileSync(file + '.tmp', JSON.stringify(value), { mode: 0o600, flush: true });
        fs.renameSync(file + '.tmp', file);
    };
    let api = null;
    let state = 'disconnected';
    let qr = null;
    let account = '';
    let busyLogin = false;
    let target = read('target.json', null);
    const ledger = read('deliveries.json', {});
    for (const delivery of Object.values(ledger)) {
        if (delivery.state === 'sending') delivery.state = 'uncertain';
    }
    write('deliveries.json', ledger);
    const inflight = new Map();
    const ready = (async () => {
        const credentials = read('credentials.json', null);
        if (credentials) {
            try { api = await connect(credentials); state = 'connected'; }
            catch { state = 'disconnected'; }
        }
    })();
    async function groups() {
        if (!api) throw Object.assign(new Error('Chưa đăng nhập Zalo. Hãy quét QR.'), { status: 503 });
        const all = await api.getAllGroups();
        const ids = Object.keys(all.gridVerMap || {});
        const result = [];
        for (let i = 0; i < ids.length; i += 20) {
            const info = await api.getGroupInfo(ids.slice(i, i + 20));
            for (const [id, value] of Object.entries(info.gridInfoMap || {})) {
                result.push({ id, name: value.name || id });
            }
        }
        return result.sort((a, b) => a.name.localeCompare(b.name, 'vi'));
    }
    async function deliver(body) {
        const { key, group_id: groupId, parts } = body;
        if (typeof key !== 'string' || !/^[a-f0-9]{64}$/.test(key) ||
            !Array.isArray(parts) || !parts.length || parts.length > 20 ||
            parts.some(p => typeof p !== 'string' || !p.trim() || p.length > 1800) ||
            (body.format !== undefined && body.format !== 'schedule-v1')) {
            throw Object.assign(new Error('Nội dung gửi không hợp lệ.'), { status: 400 });
        }
        const digest = createHash('sha256').update(JSON.stringify([groupId, parts])).digest('hex');
        if (ledger[key]) {
            if (ledger[key].digest !== digest) throw Object.assign(new Error('Nội dung khác với lần gửi trước; cần đối chiếu lịch sử.'), { status: 409 });
            return ledger[key];
        }
        if (!api) throw Object.assign(new Error('Chưa đăng nhập Zalo.'), { status: 503 });
        if (!target || target.id !== groupId) throw Object.assign(new Error('Nhóm nhận chưa được xác nhận.'), { status: 400 });
        // Verify membership before starting; a failure here has no external side effect.
        const info = await api.getGroupInfo(groupId);
        if (!info.gridInfoMap?.[groupId]) throw Object.assign(new Error('Không tìm thấy nhóm Zalo đã chọn.'), { status: 400 });
        const entry = ledger[key] = { state: 'sending', digest, message_ids: [], updated_at: new Date().toISOString() };
        write('deliveries.json', ledger); // Persist intent before the first external send.
        try {
            for (const part of parts) {
                const content = { msg: part };
                if (body.format === 'schedule-v1') content.styles = scheduleStyles(part);
                const result = await api.sendMessage(content, groupId, 1);
                const id = result?.message?.msgId;
                if (!id) throw new Error('Zalo did not return a message ID');
                entry.message_ids.push(String(id));
                write('deliveries.json', ledger);
            }
            entry.state = 'sent';
        } catch {
            // Never automatically repeat a request whose delivery cannot be confirmed.
            entry.state = 'uncertain';
        }
        entry.updated_at = new Date().toISOString();
        write('deliveries.json', ledger);
        return entry;
    }
    const server = http.createServer(async (req, res) => {
        const reply = (status, value) => {
            res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
            res.end(JSON.stringify(value));
        };
        if (req.url === '/health' && req.method === 'GET') return reply(200, { ok: true });
        const supplied = Buffer.from(req.headers.authorization || '');
        const expected = Buffer.from(`Bearer ${token}`);
        if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return reply(401, { error: 'Unauthorized' });
        try {
            await ready;
            let body = {};
            if (req.method === 'POST') {
                let text = '';
                for await (const chunk of req) {
                    text += chunk;
                    if (Buffer.byteLength(text) > 100000) throw Object.assign(new Error('Request too large'), { status: 413 });
                }
                try { body = JSON.parse(text || '{}'); }
                catch { throw Object.assign(new Error('Invalid JSON'), { status: 400 }); }
            }
            if (req.url === '/status' && req.method === 'GET') return reply(200, { state, qr, account, target });
            if (req.url === '/disconnect' && req.method === 'POST') {
                if (busyLogin || inflight.size) return reply(409, { error: 'Đang đăng nhập hoặc gửi tin. Hãy thử lại sau.' });
                api = null; state = 'disconnected'; qr = null; account = ''; target = null;
                fs.rmSync(path.join(dataDir, 'credentials.json'), { force: true });
                write('target.json', null);
                return reply(200, { state });
            }
            if (req.url === '/login' && req.method === 'POST') {
                if (!busyLogin && !api) {
                    busyLogin = true; state = 'connecting'; qr = null;
                    Promise.resolve().then(() => loginQR(event => {
                        if (event.type === 'qr') { qr = event.image; state = 'qr'; }
                        if (event.type === 'scanned') { account = event.name; state = 'scanned'; }
                        if (event.type === 'credentials') write('credentials.json', event.credentials);
                    })).then(value => { api = value; state = 'connected'; qr = null; })
                        .catch(() => { state = 'disconnected'; qr = null; })
                        .finally(() => { busyLogin = false; });
                }
                return reply(202, { state });
            }
            if (req.url === '/groups' && req.method === 'GET') return reply(200, { groups: await groups() });
            if (req.url === '/target' && req.method === 'POST') {
                const match = (await groups()).find(g => g.id === body.group_id);
                if (!match) return reply(400, { error: 'Nhóm không tồn tại trong tài khoản đã đăng nhập.' });
                target = match; write('target.json', target);
                return reply(200, target);
            }
            if (req.url === '/messages' && req.method === 'POST') {
                // Serialize duplicates even while the first request is still in flight.
                const key = body.key;
                if (inflight.has(key)) await inflight.get(key);
                const operation = deliver(body);
                inflight.set(key, operation);
                try { return reply(200, await operation); }
                finally { inflight.delete(key); }
            }
            return reply(404, { error: 'Not found' });
        } catch (error) {
            // Do not expose upstream requests, cookies or access tokens.
            return reply(error.status || 502, { error: error.status ? error.message : 'Không kết nối được Zalo. Hãy kiểm tra phiên đăng nhập.' });
        }
    });
    server.requestTimeout = 30000;
    return { server, ready };
}
