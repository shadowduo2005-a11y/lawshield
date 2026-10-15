const express = require('express');
const router = express.Router();
const prisma = require('../lib/prisma');
const auth = require('../middleware/auth');
const multer = require('multer');
const FormData = require('form-data');
const axios = require('axios');

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000';

// Store file in memory so we can pipe it to the AI service
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 50 * 1024 * 1024 }, // 50 MB limit
  fileFilter: (req, file, cb) => {
    const allowed = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
    ];
    if (allowed.includes(file.mimetype)) {
      cb(null, true);
    } else {
      cb(new Error(`Unsupported file type: ${file.mimetype}`));
    }
  },
});

// ── GET /api/documents ────────────────────────────────────────────────────────
router.get('/', auth, async (req, res) => {
  try {
    const documents = await prisma.document.findMany({
      where: { userId: req.user.id },
      orderBy: { createdAt: 'desc' },
    });
    res.json(documents);
  } catch (err) {
    console.error('[GET /documents]', err);
    res.status(500).json({ msg: 'Failed to fetch documents.' });
  }
});

// ── POST /api/documents/upload-and-ingest ─────────────────────────────────────
// auth middleware first, then multer (order matters – multer must come after auth
// so that Express parses the bearer token from headers before consuming the stream)
router.post(
  '/upload-and-ingest',
  auth,
  (req, res, next) => upload.single('file')(req, res, (err) => {
    if (err) {
      return res.status(400).json({ msg: err.message });
    }
    next();
  }),
  async (req, res) => {
    if (!req.file) {
      return res.status(400).json({ msg: 'No file uploaded. Send the file under the "file" key.' });
    }

    // ── Forward to Python AI service ────────────────────────────────────────
    let aiData = null;
    let status = 'Ready';

    try {
      const form = new FormData();
      form.append('file', req.file.buffer, {
        filename:    req.file.originalname,
        contentType: req.file.mimetype,
      });

      const aiRes = await axios.post(
        `${AI_SERVICE_URL}/documents/upload-and-ingest`,
        form,
        {
          headers: { ...form.getHeaders() },
          timeout: 120_000, // 2-minute timeout – OCR can be slow
          maxContentLength: Infinity,
          maxBodyLength:    Infinity,
        }
      );
      aiData = aiRes.data;
    } catch (aiErr) {
      const detail = aiErr.response?.data?.detail || aiErr.message;
      console.error('[Document AI Service Error]', detail);
      status = 'Processing Failed';
    }

    // ── Persist document metadata regardless of AI outcome ──────────────────
    try {
      const doc = await prisma.document.create({
        data: {
          userId:   req.user.id,
          filename: req.file.originalname,
          fileType: req.file.mimetype,
          size:     `${(req.file.size / 1024 / 1024).toFixed(2)} MB`,
          status,
        },
      });

      res.json({ document: doc, aiData });
    } catch (dbErr) {
      console.error('[Document DB Error]', dbErr);
      res.status(500).json({ msg: 'Failed to save document metadata.' });
    }
  }
);

// ── DELETE /api/documents/:id ─────────────────────────────────────────────────
router.delete('/:id', auth, async (req, res) => {
  try {
    const doc = await prisma.document.findFirst({
      where: { id: req.params.id, userId: req.user.id },
    });
    if (!doc) return res.status(404).json({ msg: 'Document not found.' });

    await prisma.document.delete({ where: { id: req.params.id } });
    res.json({ msg: 'Document deleted.' });
  } catch (err) {
    console.error('[DELETE /documents/:id]', err);
    res.status(500).json({ msg: 'Failed to delete document.' });
  }
});

module.exports = router;
