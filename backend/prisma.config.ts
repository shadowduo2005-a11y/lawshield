import { defineConfig } from 'prisma/config';
import { PrismaPg } from '@prisma/adapter-pg';
import pg from 'pg';
import 'dotenv/config';

// Prisma schema operations should use Neon's direct (non-pooler) connection
// when available. Runtime traffic continues to use DATABASE_URL via lib/prisma.js.
const migrationUrl = process.env.DIRECT_URL || process.env.DATABASE_URL;
const pool = new pg.Pool({ connectionString: migrationUrl });

const adapter = new PrismaPg(pool);

export default defineConfig({
  earlyAccess: true,
  schema: './prisma/schema.prisma',
  datasource: {
    url: migrationUrl,
  },
  migrate: {
    adapter,
  },
});
