console.log("Starting server.js...");
const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const axios = require('axios');

dotenv.config();

const isProduction = process.env.NODE_ENV === 'production';
if (isProduction) {
  const missing = [
    'DATABASE_URL',
    'JWT_SECRET',
    'AI_SERVICE_URL',
    'AI_SERVICE_TOKEN',
    'FRONTEND_URL',
  ]
    .filter((name) => !process.env[name]);
  if (missing.length) {
    throw new Error(`Missing required production environment variables: ${missing.join(', ')}`);
  }
  if (process.env.JWT_SECRET.length < 32) {
    throw new Error('JWT_SECRET must contain at least 32 characters in production.');
  }
  if (process.env.AI_SERVICE_TOKEN.length < 32) {
    throw new Error('AI_SERVICE_TOKEN must contain at least 32 characters in production.');
  }
  const frontendUrl = new URL(process.env.FRONTEND_URL);
  const aiUrl = new URL(process.env.AI_SERVICE_URL);
  if (frontendUrl.protocol !== 'https:') {
    throw new Error('FRONTEND_URL must use HTTPS in production.');
  }
  if (!['http:', 'https:'].includes(aiUrl.protocol)) {
    throw new Error('AI_SERVICE_URL must use HTTP or HTTPS.');
  }
}

const AI_SERVICE_URL = (process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000')
  .trim()
  .replace(/\/+$/, '');
const AI_SERVICE_TOKEN = (process.env.AI_SERVICE_TOKEN || '').trim();
const allowVercelPreviews = process.env.ALLOW_VERCEL_PREVIEWS === 'true';
const prisma = require('./lib/prisma');

const app = express();
app.disable('x-powered-by');
app.set('trust proxy', 1);

// ── CORS ─────────────────────────────────────────────────────────────────────
// Allow Vite dev server and any future production origin
const allowedOrigins = [
  'http://localhost:5173',
  'http://localhost:5174',
  'http://localhost:4173',
  'http://localhost:3000',
  process.env.FRONTEND_URL,
].filter(Boolean);

app.use(
  cors({
    origin: (origin, callback) => {
      // Allow requests with no origin (e.g., mobile apps, curl, Postman)
      if (
        !origin ||
        allowedOrigins.includes(origin) ||
        (allowVercelPreviews && origin.endsWith('.vercel.app'))
      ) {
        callback(null, true);
      } else {
        callback(new Error(`CORS: Origin ${origin} not allowed`));
      }
    },
    credentials: true,
  })
);

// ── Body parsing ──────────────────────────────────────────────────────────────
// Note: multer handles multipart/form-data in the document routes;
// express.json() only parses application/json.
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: false }));

app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');
  next();
});

// ── Routes ────────────────────────────────────────────────────────────────────
console.log("Loading auth routes...");
app.use('/api/auth',      require('./routes/auth'));
console.log("Loading threads routes...");
app.use('/api/threads',   require('./routes/threads'));
console.log("Loading chat routes...");
app.use('/api/chat',      require('./routes/chat'));
console.log("Loading documents routes...");
app.use('/api/documents', require('./routes/documents'));
console.log("Finished loading routes.");

// ── Health check ──────────────────────────────────────────────────────────────
app.get('/health', (req, res) => res.json({ status: 'ok' }));

// Readiness checks the two dependencies required by chat instead of reporting a
// false-positive healthy service when EC2 or PostgreSQL is unavailable.
app.get('/ready', async (req, res) => {
  const checks = { database: 'unknown', aiService: 'unknown' };
  try {
    await prisma.$queryRawUnsafe('SELECT 1');
    checks.database = 'ready';
    await axios.get(`${AI_SERVICE_URL}/ready`, {
      headers: AI_SERVICE_TOKEN ? { 'X-Service-Token': AI_SERVICE_TOKEN } : {},
      timeout: 10_000,
    });
    checks.aiService = 'ready';
    return res.json({ status: 'ready', checks });
  } catch (err) {
    console.error('[GET /ready]', err.message);
    if (checks.database === 'ready') checks.aiService = 'not_ready';
    else checks.database = 'not_ready';
    return res.status(503).json({ status: 'not_ready', checks });
  }
});

// ── 404 handler ───────────────────────────────────────────────────────────────
app.use((req, res) => {
  res.status(404).json({ msg: 'Route not found' });
});

// ── Global error handler ──────────────────────────────────────────────────────
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).json({ msg: err.message || 'Internal Server Error' });
});

// ── Start ─────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3000;
function startServer(port = PORT) {
  const server = app.listen(port, () => {
    const address = server.address();
    const boundPort = typeof address === 'object' && address ? address.port : port;
    console.log(`✅  LawShield backend running on http://localhost:${boundPort}`);
  });

  async function shutdown(signal) {
    console.log(`${signal} received; shutting down gracefully.`);
    const forceExit = setTimeout(() => process.exit(1), 10_000);
    forceExit.unref();

    server.close(async (serverErr) => {
      try {
        await prisma.$disconnect();
      } catch (dbErr) {
        console.error('[Shutdown database error]', dbErr);
      }
      clearTimeout(forceExit);
      process.exit(serverErr ? 1 : 0);
    });
  }

  process.once('SIGTERM', () => shutdown('SIGTERM'));
  process.once('SIGINT', () => shutdown('SIGINT'));
  return server;
}

if (require.main === module) {
  startServer();
}

module.exports = { app, startServer };
