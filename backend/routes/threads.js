const express = require('express');
const router = express.Router();
const prisma = require('../lib/prisma');
const auth = require('../middleware/auth');

// ── GET /api/threads ──────────────────────────────────────────────────────────
// Returns all threads for the authenticated user, newest first.
router.get('/', auth, async (req, res) => {
  try {
    const threads = await prisma.thread.findMany({
      where: { userId: req.user.id },
      orderBy: { updatedAt: 'desc' },
    });
    res.json(threads);
  } catch (err) {
    console.error('[GET /threads]', err);
    res.status(500).json({ msg: 'Failed to fetch threads.' });
  }
});

// ── POST /api/threads ─────────────────────────────────────────────────────────
// Create a new thread for the authenticated user.
router.post('/', auth, async (req, res) => {
  const { title } = req.body;
  try {
    const thread = await prisma.thread.create({
      data: {
        userId: req.user.id,
        title: (title && title.trim()) ? title.trim() : 'New Matter',
      },
    });
    res.status(201).json(thread);
  } catch (err) {
    console.error('[POST /threads]', err);
    res.status(500).json({ msg: 'Failed to create thread.' });
  }
});

// ── GET /api/threads/:id ──────────────────────────────────────────────────────
// Returns a single thread with its messages (ascending by time).
router.get('/:id', auth, async (req, res) => {
  try {
    const thread = await prisma.thread.findFirst({
      where: { id: req.params.id, userId: req.user.id },
      include: {
        messages: { orderBy: { createdAt: 'asc' } },
      },
    });
    if (!thread) return res.status(404).json({ msg: 'Thread not found.' });
    res.json(thread);
  } catch (err) {
    console.error('[GET /threads/:id]', err);
    res.status(500).json({ msg: 'Failed to fetch thread.' });
  }
});

// ── PATCH /api/threads/:id ────────────────────────────────────────────────────
// Rename a thread.
router.patch('/:id', auth, async (req, res) => {
  const { title } = req.body;
  if (!title || !title.trim()) {
    return res.status(400).json({ msg: 'title is required.' });
  }
  try {
    const thread = await prisma.thread.findFirst({
      where: { id: req.params.id, userId: req.user.id },
    });
    if (!thread) return res.status(404).json({ msg: 'Thread not found.' });

    const updated = await prisma.thread.update({
      where: { id: req.params.id },
      data: { title: title.trim() },
    });
    res.json(updated);
  } catch (err) {
    console.error('[PATCH /threads/:id]', err);
    res.status(500).json({ msg: 'Failed to rename thread.' });
  }
});

// ── DELETE /api/threads/:id ───────────────────────────────────────────────────
// Delete a thread. Messages are removed automatically via onDelete: Cascade.
router.delete('/:id', auth, async (req, res) => {
  try {
    const thread = await prisma.thread.findFirst({
      where: { id: req.params.id, userId: req.user.id },
    });
    if (!thread) return res.status(404).json({ msg: 'Thread not found.' });

    // Messages cascade-delete automatically (schema: onDelete: Cascade)
    await prisma.thread.delete({ where: { id: req.params.id } });

    res.json({ msg: 'Thread deleted successfully.' });
  } catch (err) {
    console.error('[DELETE /threads/:id]', err);
    res.status(500).json({ msg: 'Failed to delete thread.' });
  }
});

module.exports = router;
