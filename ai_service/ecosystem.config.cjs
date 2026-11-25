module.exports = {
  apps: [
    {
      name: 'ai-service',
      cwd: __dirname,
      script: '.venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      max_memory_restart: '1500M',
      exp_backoff_restart_delay: 1000,
      kill_timeout: 10000,
      env: {
        ENVIRONMENT: 'production',
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
