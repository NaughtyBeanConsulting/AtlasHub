'use strict';

const path = require('path');

// Shares the repo-root .env with Django (same file systemd points at).
require('dotenv').config({ path: path.resolve(__dirname, '..', '.env') });

/**
 * AtlasHub WhatsApp Node Worker
 *
 * Runs whatsapp-web.js and exposes an HTTP API consumed by Django.
 *
 * Endpoints (all require Authorization: Bearer <WHATSAPP_WORKER_TOKEN>):
 *   GET  /health        → { ok: true }
 *   GET  /status        → { status, qr_base64, error }
 *   POST /restart       → restarts the WhatsApp client
 *   POST /disconnect    → logout + wipe session → fresh QR
 *   POST /send          → { phone, message } → { ok, error? }
 *
 * Environment:
 *   WHATSAPP_WORKER_PORT    default 8030 (ClockInSop uses 8025 — both can
 *                           share a host)
 *   WHATSAPP_WORKER_TOKEN   shared secret (same value in Django .env)
 *   WHATSAPP_SESSION_PATH   default ../whatsapp_session (gitignored!)
 *   COUNTRY_CODE            default 27 (South Africa)
 *   CHROME_PATH             optional explicit Chrome/Chromium binary
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const qrcode = require('qrcode');

const PORT = parseInt(process.env.WHATSAPP_WORKER_PORT || '8030', 10);
const TOKEN = process.env.WHATSAPP_WORKER_TOKEN || '';
const SESSION_PATH = process.env.WHATSAPP_SESSION_PATH
    || path.resolve(__dirname, '..', 'whatsapp_session');
const COUNTRY_CODE = process.env.COUNTRY_CODE || '27';

// ── State ────────────────────────────────────────────────────────────────────

let state = { status: 'STARTING', qr_base64: null, error: null };

// ── Phone normalisation ──────────────────────────────────────────────────────

function normalisePhone(raw) {
    let digits = raw.replace(/\D/g, '');
    if (digits.startsWith('00')) digits = digits.slice(2);
    else if (digits.startsWith('0')) digits = COUNTRY_CODE + digits.slice(1);
    return digits;
}

// ── WhatsApp client ──────────────────────────────────────────────────────────

function createClient() {
    const client = new Client({
        authStrategy: new LocalAuth({ dataPath: SESSION_PATH }),
        puppeteer: {
            headless: true,
            executablePath: process.env.CHROME_PATH || undefined,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
            ],
        },
    });

    client.on('qr', async (qr) => {
        console.log('[wa] QR received');
        try {
            const dataUrl = await qrcode.toDataURL(qr);
            state.qr_base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
            state.status = 'QR_READY';
            state.error = null;
        } catch (err) {
            console.error('[wa] QR generation error:', err.message);
        }
    });

    client.on('authenticated', () => {
        console.log('[wa] Authenticated');
        state.qr_base64 = null;
        state.error = null;
    });

    client.on('ready', () => {
        console.log('[wa] Ready');
        state.status = 'CONNECTED';
        state.qr_base64 = null;
        state.error = null;
    });

    client.on('auth_failure', (msg) => {
        console.error('[wa] Auth failure:', msg);
        state.status = 'ERROR';
        state.error = `Auth failure: ${msg}`;
    });

    client.on('disconnected', (reason) => {
        console.log('[wa] Disconnected:', reason);
        state.status = 'DISCONNECTED';
        state.qr_base64 = null;
    });

    return client;
}

let waClient = createClient();
waClient.initialize().catch((err) => {
    console.error('[wa] Init error:', err.message);
    state.status = 'ERROR';
    state.error = err.message;
});

// ── HTTP API ─────────────────────────────────────────────────────────────────

const app = express();
app.use(express.json());

app.use((req, res, next) => {
    if (!TOKEN) return next();
    if (req.headers.authorization !== `Bearer ${TOKEN}`) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
});

app.get('/health', (_req, res) => res.json({ ok: true }));

app.get('/status', (_req, res) => res.json(state));

app.post('/restart', async (req, res) => {
    console.log('[wa] Restart requested');
    try { await waClient.destroy(); } catch (_) {}
    state = { status: 'STARTING', qr_base64: null, error: null };
    waClient = createClient();
    waClient.initialize().catch((err) => {
        state.status = 'ERROR';
        state.error = err.message;
    });
    res.json({ ok: true });
});

app.post('/disconnect', async (req, res) => {
    console.log('[wa] Disconnect + clear session requested');
    try { await waClient.logout(); } catch (_) {}
    try { await waClient.destroy(); } catch (_) {}

    // Wipe the session directory so the next init shows a fresh QR
    const fs = require('fs');
    try {
        if (fs.existsSync(SESSION_PATH)) {
            fs.rmSync(SESSION_PATH, { recursive: true, force: true });
            console.log('[wa] Session directory cleared');
        }
    } catch (err) {
        console.error('[wa] Could not clear session:', err.message);
    }

    state = { status: 'STARTING', qr_base64: null, error: null };
    waClient = createClient();
    waClient.initialize().catch((err) => {
        state.status = 'ERROR';
        state.error = err.message;
    });
    res.json({ ok: true });
});

app.post('/send', async (req, res) => {
    const { phone, message } = req.body || {};
    if (!phone || !message) {
        return res.status(400).json({ ok: false, error: 'phone and message required' });
    }
    if (state.status !== 'CONNECTED') {
        return res.status(503).json({ ok: false, error: `WhatsApp not connected (${state.status})` });
    }
    try {
        const number = normalisePhone(String(phone));
        await waClient.sendMessage(`${number}@c.us`, message);
        res.json({ ok: true });
    } catch (err) {
        console.error('[wa] Send failed:', err.message);
        res.status(500).json({ ok: false, error: err.message });
    }
});

app.listen(PORT, '127.0.0.1', () => {
    console.log(`[wa] AtlasHub worker listening on 127.0.0.1:${PORT}`);
});

// ── Graceful shutdown ────────────────────────────────────────────────────────

async function shutdown() {
    console.log('[wa] Shutting down...');
    try { await waClient.destroy(); } catch (_) {}
    process.exit(0);
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
