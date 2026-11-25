const assert = require('node:assert/strict');
const { after, test } = require('node:test');

process.env.NODE_ENV = 'test';
process.env.DATABASE_URL = 'postgresql://test:test@127.0.0.1:6543/test';
process.env.JWT_SECRET = 'test-secret-not-used-by-health-endpoint';

const { app } = require('../server');
const prisma = require('../lib/prisma');

after(async () => {
  await prisma.$disconnect();
});

test('GET /health route reports backend liveness', () => {
  const routeLayer = app.router.stack.find((layer) => layer.route?.path === '/health');
  assert.ok(routeLayer, 'health route must be registered');

  let payload;
  const response = { json(value) { payload = value; } };
  routeLayer.route.stack[0].handle({}, response);

  assert.deepEqual(payload, { status: 'ok' });
});
