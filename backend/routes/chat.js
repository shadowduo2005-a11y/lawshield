const express = require('express');
const axios = require('axios');
const http = require('http');
const https = require('https');

const prisma = require('../lib/prisma');
const auth = require('../middleware/auth');

const router = express.Router();
const AI_SERVICE_URL = (process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000')
  .trim()
  .replace(/\/+$/, '');
const AI_SERVICE_TOKEN = (process.env.AI_SERVICE_TOKEN || '').trim();
const parsedTimeout = Number.parseInt(process.env.AI_REQUEST_TIMEOUT_MS || '180000', 10);
const AI_REQUEST_TIMEOUT_MS = Number.isFinite(parsedTimeout) ? parsedTimeout : 180_000;

function aiHeaders(extra = {}) {
  return {
    ...extra,
    ...(AI_SERVICE_TOKEN ? { 'X-Service-Token': AI_SERVICE_TOKEN } : {}),
  };
}

function publicAiError(err) {
  const code = err?.code || '';
  const message = String(err?.message || err || '');
  if (code === 'ECONNREFUSED' || code === 'ENOTFOUND' || code === 'EHOSTUNREACH') {
    return 'The AI service is currently unreachable. Please try again shortly.';
  }
  if (code === 'ETIMEDOUT' || /timeout/i.test(message)) {
    return 'The AI service took too long to respond. Please try again.';
  }
  if (/status (401|403)/i.test(message)) {
    return 'The backend could not authenticate with the AI service.';
  }
  return 'The AI service could not complete this request. Please try again shortly.';
}

function writeSse(res, value) {
  if (res.writableEnded || res.destroyed) return;
  const normalized = String(value).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  for (const line of normalized.split('\n')) {
    res.write(`data: ${line}\n`);
  }
  res.write('\n');
}

function parseSseEvent(event) {
  const dataLines = event
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''));
  return dataLines.length ? dataLines.join('\n') : null;
}

// Non-streaming fallback/API endpoint.
router.post('/', auth, async (req, res) => {
  const { threadId, message } = req.body;
  if (!threadId || !message || !message.trim()) {
    return res.status(400).json({ msg: 'threadId and message are required.' });
  }

  try {
    const thread = await prisma.thread.findFirst({
      where: { id: threadId, userId: req.user.id },
      include: { messages: { orderBy: { createdAt: 'asc' } } },
    });
    if (!thread) return res.status(404).json({ msg: 'Thread not found.' });

    await prisma.message.create({
      data: { threadId, role: 'USER', content: message.trim() },
    });

    const history = (thread.messages || []).map((item) => ({
      role: item.role.toLowerCase(),
      content: item.content,
    }));

    let aiContent;
    let sources = [];
    try {
      const aiRes = await axios.post(
        `${AI_SERVICE_URL}/chat/`,
        { session_id: threadId, message: message.trim(), history },
        {
          headers: aiHeaders(),
          timeout: AI_REQUEST_TIMEOUT_MS,
        },
      );
      aiContent = aiRes.data.response || '';
      sources = Array.isArray(aiRes.data.sources) ? aiRes.data.sources : [];
      if (!aiContent) throw new Error('AI service returned an empty response');
    } catch (aiErr) {
      const detail = aiErr.response?.data?.detail || aiErr.message;
      console.error('[AI Service Error]', detail);
      aiContent = publicAiError(aiErr);
    }

    const assistantMsg = await prisma.message.create({
      data: {
        threadId,
        role: 'ASSISTANT',
        content: aiContent,
        sources: JSON.stringify(sources),
      },
    });

    await prisma.thread.update({
      where: { id: threadId },
      data: { updatedAt: new Date() },
    });
    return res.json(assistantMsg);
  } catch (err) {
    console.error('[POST /chat]', err);
    return res.status(500).json({ msg: 'Failed to process chat message.' });
  }
});

// SSE proxy from the EC2 FastAPI service to the browser.
router.post('/stream', auth, async (req, res) => {
  const { threadId, message } = req.body;
  if (!threadId || !message || !message.trim()) {
    return res.status(400).json({ msg: 'threadId and message are required.' });
  }

  res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  const heartbeat = setInterval(() => {
    if (!res.writableEnded && !res.destroyed) res.write(': keep-alive\n\n');
  }, 15_000);

  try {
    const thread = await prisma.thread.findFirst({
      where: { id: threadId, userId: req.user.id },
      include: { messages: { orderBy: { createdAt: 'asc' } } },
    });
    if (!thread) throw new Error('Thread not found');

    await prisma.message.create({
      data: { threadId, role: 'USER', content: message.trim() },
    });

    const history = (thread.messages || []).map((item) => ({
      role: item.role.toLowerCase(),
      content: item.content,
    }));

    let finalAnswer = '';
    let capturingFinal = false;
    let receivedDone = false;

    await new Promise((resolve, reject) => {
      const payload = JSON.stringify({
        session_id: threadId,
        message: message.trim(),
        history,
      });
      const url = new URL(`${AI_SERVICE_URL}/chat/stream`);
      const transport = url.protocol === 'https:' ? https : http;
      const requestHeaders = aiHeaders({
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
        Accept: 'text/event-stream',
      });

      const aiReq = transport.request({
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: `${url.pathname}${url.search}`,
        method: 'POST',
        headers: requestHeaders,
      }, (aiRes) => {
        aiRes.setEncoding('utf8');

        if (aiRes.statusCode < 200 || aiRes.statusCode >= 300) {
          let errorBody = '';
          aiRes.on('data', (chunk) => { errorBody += chunk; });
          aiRes.on('end', () => {
            reject(new Error(`AI service returned status ${aiRes.statusCode}: ${errorBody.slice(0, 500)}`));
          });
          return;
        }

        let buffer = '';
        const handleEvent = (event) => {
          const data = parseSseEvent(event);
          if (data === null) return;

          if (data === '[FINAL]') {
            capturingFinal = true;
            writeSse(res, '[FINAL]');
          } else if (data === '[DONE]') {
            receivedDone = true;
          } else if (data.startsWith('[ERROR]')) {
            throw new Error(data.slice(7).trim() || 'AI service stream failed');
          } else if (capturingFinal) {
            finalAnswer += (finalAnswer ? '\n\n' : '') + data;
            writeSse(res, data);
          } else {
            writeSse(res, data);
          }
        };

        aiRes.on('data', (chunk) => {
          buffer += chunk.replace(/\r\n/g, '\n');
          const events = buffer.split('\n\n');
          buffer = events.pop();
          try {
            events.forEach(handleEvent);
          } catch (err) {
            aiReq.destroy(err);
          }
        });

        aiRes.on('end', () => {
          try {
            if (buffer.trim()) handleEvent(buffer);
            if (!receivedDone) return reject(new Error('AI service stream ended before [DONE]'));
            if (!finalAnswer.trim()) return reject(new Error('AI service returned an empty answer'));
            return resolve();
          } catch (err) {
            return reject(err);
          }
        });
        aiRes.on('error', reject);
      });

      aiReq.on('error', reject);
      aiReq.setTimeout(AI_REQUEST_TIMEOUT_MS, () => {
        const timeoutError = new Error('AI service stream timeout');
        timeoutError.code = 'ETIMEDOUT';
        aiReq.destroy(timeoutError);
      });
      aiReq.end(payload);
    });

    await prisma.message.create({
      data: {
        threadId,
        role: 'ASSISTANT',
        content: finalAnswer,
        sources: JSON.stringify([]),
      },
    });
    await prisma.thread.update({
      where: { id: threadId },
      data: { updatedAt: new Date() },
    });
    writeSse(res, '[DONE]');
  } catch (err) {
    console.error('[POST /chat/stream]', err);
    writeSse(res, `[ERROR] ${publicAiError(err)}`);
    writeSse(res, '[DONE]');
  } finally {
    clearInterval(heartbeat);
    if (!res.writableEnded) res.end();
  }
});

module.exports = router;
