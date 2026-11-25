# LawShield deployment checklist

The three services are deployed separately. Environment values are build-time
for Vercel and runtime values for Render/EC2.

Use the exact public origins below. Environment values must be plain text URLs:
do not paste Markdown such as `[http://localhost:6333](http://localhost:6333)`,
quotes, or backslashes into the hosting dashboards.

| Service | Production origin |
| --- | --- |
| Frontend | `https://lawshield.vercel.app` |
| Backend | `https://lawshield-backend.onrender.com` |
| AI service | `http://YOUR_EC2_ELASTIC_IP:8000` |

## 1. EC2 AI service

Use Python 3.12, install `ai_service/requirements.txt`, and optionally install
the full spaCy English model:

```bash
cd ai_service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

For scanned-image OCR, install `requirements-ocr.txt` later; it is deliberately
kept out of the core deployment because Paddle is large and is not required for
chat, DOCX, TXT, or text-based PDFs.

Copy the values from `ai_service/.env.example` into the EC2 environment. At
least one LLM API key must be present. For the fastest demo, keep both memory
flags disabled. Keep these internal Docker URLs as plain values:

```env
QDRANT_URL=http://localhost:6333
ELASTICSEARCH_URL=http://localhost:9200
```

Start the retrieval services before the AI process (they remain internal to
EC2 because the Compose ports bind to `127.0.0.1`):

```bash
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:6333/readyz
curl -fsS http://127.0.0.1:9200
```

Generate secrets locally (use different values for JWT and service auth):

```bash
openssl rand -hex 32
```

The `AI_SERVICE_TOKEN` value must be identical on EC2 and Render. Never commit
the Gemini key, Neon URL, JWT secret, or service token.

Start the service without development reload:

```bash
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```

PM2 restarts the Python process after crashes; `pm2 startup` plus `pm2 save`
restores it after a reboot. Verify:

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/ready
```

In the EC2 security group, allow inbound TCP `8000` from the Render service's
egress addresses when available. For a quick demo it can be open temporarily,
but the `AI_SERVICE_TOKEN` must remain enabled. Prefer an Elastic IP so Render's
`AI_SERVICE_URL` does not change after an EC2 restart.

Expose the service through HTTPS when possible. If port 8000 is public, set a
strong `AI_SERVICE_TOKEN` on both EC2 and Render.

## 2. Render backend

Set the root directory to `backend`.

- Build command: `npm ci && npx prisma generate && npx prisma db push`
- Start command: `npm start`
- Health path: `/health`

Add every value from `backend/.env.example`. For Neon, use its pooled URL
(hostname containing `-pooler`) as `DATABASE_URL` and its direct URL as
`DIRECT_URL`. Copy the URLs exactly from Neon, including `sslmode=require`;
special characters in a manually constructed password must be URL-encoded.
Production requires `DATABASE_URL`, `JWT_SECRET`, `AI_SERVICE_URL`,
`AI_SERVICE_TOKEN`, and `FRONTEND_URL`. `AI_SERVICE_URL` must be the
EC2 public origin with no trailing slash, for example
`http://YOUR_EC2_ELASTIC_IP:8000`, not `127.0.0.1`. Set the same strong
`AI_SERVICE_TOKEN` in Render and EC2.

After deployment, verify both dependencies:

```bash
curl -i https://lawshield-backend.onrender.com/ready
```

## 3. Vercel frontend

Set the root directory to `frontend` and add this build-time variable:

```env
VITE_API_URL=https://lawshield-backend.onrender.com/api
```

Redeploy after changing it; Vite embeds this value during the build. Set
`FRONTEND_URL=https://lawshield.vercel.app` on Render.

## Final smoke test

1. Open `/ready` on EC2 and Render; both must report `ready`.
2. Register/login through the Vercel site.
3. Ask `What is the Constitution of India?`.
4. In browser DevTools, `/api/chat/stream` should contain `[FINAL]`, the answer,
   and `[DONE]`.
