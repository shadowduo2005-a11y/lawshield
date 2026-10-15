const express = require('express');
const router = express.Router();
const prisma = require('../lib/prisma');
const auth = require('../middleware/auth');
const axios = require('axios');
const http = require('http');
const https = require('https');

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';

// ── POST /api/chat ─────────────────────────────────────────────────────────────
// 1. Validates the thread belongs to the authenticated user.
// 2. Saves the user message.
// 3. Proxies to the Python AI service.
// 4. Saves the assistant response.
// 5. Returns the full assistant message record.
router.post('/', auth, async (req, res) => {
  const { threadId, message } = req.body;

  if (!threadId || !message || !message.trim()) {
    return res.status(400).json({ msg: 'threadId and message are required.' });
  }

  try {
    // Verify thread ownership and get history
    const thread = await prisma.thread.findFirst({
      where: { id: threadId, userId: req.user.id },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' }
        }
      }
    });
    if (!thread) return res.status(404).json({ msg: 'Thread not found.' });

    // Persist user message immediately (so it is visible even if AI fails)
    await prisma.message.create({
      data: { threadId, role: 'USER', content: message.trim() },
    });

    const history = (thread.messages || []).map(m => ({
      role: m.role.toLowerCase(),
      content: m.content
    }));

    // ── Call Python AI service ──────────────────────────────────────────────
    let aiContent = '';
    let sources = [];

    try {
      const aiRes = await axios.post(
        `${AI_SERVICE_URL}/chat/`,
        { session_id: threadId, message: message.trim(), history },
        { timeout: 120_000 } // 2-minute timeout – AI graph can be slow
      );
      aiContent = aiRes.data.response || '';
      sources   = Array.isArray(aiRes.data.sources) ? aiRes.data.sources : [];
    } catch (aiErr) {
      const detail = aiErr.response?.data?.detail || aiErr.message;
      console.error('[AI Service Error]', detail);
      aiContent = "I'm sorry, I'm having trouble connecting to the AI service right now. Please try again in a moment.";
    }

    // Persist assistant response
    const assistantMsg = await prisma.message.create({
      data: {
        threadId,
        role:    'ASSISTANT',
        content: aiContent,
        sources: JSON.stringify(sources),
      },
    });

    // Bump thread's updatedAt so it rises to the top of the list
    await prisma.thread.update({
      where: { id: threadId },
      data:  { updatedAt: new Date() },
    });

    res.json(assistantMsg);
  } catch (err) {
    console.error('[POST /chat]', err);
    res.status(500).json({ msg: 'Failed to process chat message.' });
  }
});


// ── POST /api/chat/stream ──────────────────────────────────────────────────────
// SSE streaming proxy: saves the user message, streams tokens from the Python AI
// service in real time, then saves the completed assistant message at the end.
//
// SSE event format sent to the frontend:
//   data: [Node: supervisor]\n\n   ← progress ping (pipeline step)
//   data: [FINAL]\n\n             ← signals next event is the full answer
//   data: <answer text>\n\n       ← the actual response
//   data: [DONE]\n\n              ← stream complete
router.post('/stream', auth, async (req, res) => {
  const { threadId, message } = req.body;

  if (!threadId || !message || !message.trim()) {
    return res.status(400).json({ msg: 'threadId and message are required.' });
  }

  // ── Set up SSE headers ──────────────────────────────────────────────────────
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no'); // disable nginx buffering if applicable
  res.flushHeaders();

  const send = (data) => res.write(`data: ${data}\n\n`);

  try {
    // Verify thread ownership and load history
    const thread = await prisma.thread.findFirst({
      where: { id: threadId, userId: req.user.id },
      include: { messages: { orderBy: { createdAt: 'asc' } } },
    });
    if (!thread) {
      send('[ERROR] Thread not found.');
      send('[DONE]');
      return res.end();
    }

    // Persist the user message immediately
    await prisma.message.create({
      data: { threadId, role: 'USER', content: message.trim() },
    });

    const history = (thread.messages || []).map(m => ({
      role: m.role.toLowerCase(),
      content: m.content,
    }));

    // ── Stream from Python AI service ────────────────────────────────────────
    let finalAnswer = '';
    let capturingFinal = false;

    await new Promise((resolve, reject) => {
      const payload = JSON.stringify({
        session_id: threadId,
        message: message.trim(),
        history,
      });

      const url = new URL(`${AI_SERVICE_URL}/chat/stream`);
      const lib = url.protocol === 'https:' ? https : http;

      const reqOptions = {
        hostname: url.hostname,
        port: url.port || (url.protocol === 'https:' ? 443 : 80),
        path: url.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(payload),
          Accept: 'text/event-stream',
        },
      };

      const aiReq = lib.request(reqOptions, (aiRes) => {
        aiRes.setEncoding('utf8');

        let buffer = '';

        aiRes.on('data', (chunk) => {
          buffer += chunk;

          // Split on SSE event boundaries
          const events = buffer.split('\n\n');
          buffer = events.pop(); // keep incomplete tail for next chunk

          for (const event of events) {
            if (!event.trim()) continue;

            // Strip the "data: " prefix that the Python service adds
            const line = event.startsWith('data: ')
              ? event.slice(6)
              : event;

            if (line === '[FINAL]') {
              capturingFinal = true;
              send('[FINAL]');
            } else if (line === '[DONE]') {
              send('[DONE]');
            } else if (capturingFinal) {
              // This line is the actual answer text
              finalAnswer += (finalAnswer ? '\n\n' : '') + line;
              send(line);
            } else {
              // Progress ping (e.g. "[Node: supervisor]") — forward as-is
              send(line);
            }
          }
        });

        aiRes.on('end', () => resolve());
        aiRes.on('error', (err) => reject(err));
      });

      aiReq.on('error', (err) => reject(err));
      aiReq.setTimeout(120_000, () => {
        aiReq.destroy();
        reject(new Error('AI service stream timeout'));
      });

      aiReq.write(payload);
      aiReq.end();
    });

    // ── Persist the completed assistant response ──────────────────────────────
    if (finalAnswer) {
      const assistantMsg = await prisma.message.create({
        data: {
          threadId,
          role:    'ASSISTANT',
          content: finalAnswer,
          sources: JSON.stringify([]),
        },
      });

      // Bump thread updatedAt
      await prisma.thread.update({
        where: { id: threadId },
        data:  { updatedAt: new Date() },
      });
    }

  } catch (err) {
    console.error('[POST /chat/stream]', err);
    send('[ERROR] An unexpected error occurred. Please try again.');
    send('[DONE]');
  }

  res.end();
});

module.exports = router;
