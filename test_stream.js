const http = require('http');

const req = http.request({
  hostname: 'localhost',
  port: 3000,
  path: '/api/chat/stream',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    // We need an auth token or bypass auth. 
    // Wait, auth middleware requires a valid JWT token!
  }
});
