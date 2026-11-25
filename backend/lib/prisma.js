const { PrismaClient } = require('@prisma/client');
const { PrismaPg } = require('@prisma/adapter-pg');
const pg = require('pg');

require('dotenv').config();

if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL is required. Use the pooled Neon connection URL.');
}

const poolMax = Number.parseInt(process.env.DATABASE_POOL_MAX || '5', 10);
const connectTimeout = Number.parseInt(
  process.env.DATABASE_CONNECT_TIMEOUT_MS || '10000',
  10,
);

// Reuse one pool/client during local hot reloads and across all route modules.
const globalStore = globalThis;
const pool = globalStore.__lawshieldPgPool || new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  max: Number.isFinite(poolMax) ? poolMax : 5,
  connectionTimeoutMillis: Number.isFinite(connectTimeout) ? connectTimeout : 10_000,
  idleTimeoutMillis: 30_000,
  keepAlive: true,
});

pool.on('error', (err) => {
  console.error('[PostgreSQL pool error]', err);
});

const adapter = new PrismaPg(pool);
const prisma = globalStore.__lawshieldPrisma || new PrismaClient({ adapter });

if (process.env.NODE_ENV !== 'production') {
  globalStore.__lawshieldPgPool = pool;
  globalStore.__lawshieldPrisma = prisma;
}

module.exports = prisma;
