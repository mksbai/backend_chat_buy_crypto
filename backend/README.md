# ChatPage Backend

A minimal FastAPI backend that powers the ChatPage frontend by streaming a placeholder response. The service is ready for local
development with Vite as well as containerized deployments.

## Features

- `POST /api/chat` streams plain-text placeholder responses using chunked transfer encoding.
- `GET /healthz` health check for readiness probes.
- Strict CORS allowing `http://localhost:5173` during development.
- Configurable chunk delay, CORS origins, and port via environment variables.
- Request logging with a generated `X-Request-Id` header.
- Optional request size guard (10KB message limit).

## Requirements

- Python 3.11+
- pip

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running Locally

```bash
uvicorn app:app --reload --port 8000
```

The backend listens on port 8000 by default. Adjust the port with the `PORT` environment variable if needed.

### Vite Proxy Configuration

Point the frontend's `/api` requests to the backend during development by updating `vite.config.ts`:

```ts
// vite.config.ts
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

For production, serve the backend behind the same origin as the frontend using a reverse proxy (e.g., Nginx or your hosting provider).

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `PORT` | `8000` | Port used by Uvicorn. |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins. |
| `LOG_LEVEL` | `info` | Logging level. |
| `DELAY_MS` | `80` | Delay between streamed chunks in milliseconds. |
| `MAX_MESSAGE_BYTES` | `10240` | Maximum allowed request message size in bytes. |

## Placeholder Response

Every chat request receives the following streamed placeholder text:

> This is a placeholder response from the backend. Your message was received and the streaming is working. Replace this with real AI output when ready.

Update `PLACEHOLDER_TEXT` in `app.py` when you are ready to integrate real AI output.

## Testing

```bash
pytest
```

## Docker

Build and run the production image:

```bash
cd backend
docker build -t chat-backend .
docker run --rm -p 8000:8000 chat-backend
```

The container exposes port 8000 and runs the Uvicorn server defined in `app.py`.

## Continuous Deployment to AWS EC2

A GitHub Actions workflow (`.github/workflows/deploy-backend.yml`) deploys the backend to an Ubuntu-based EC2 host via Docker over SSH whenever `main` is updated or the workflow is manually dispatched. Configure the following repository secrets before the first deploy:

- `SSH_PRIVATE_KEY`
- `SERVER_IP`
- `SERVER_USER`
- `SSH_PORT` (optional, defaults to 22)

### First-time EC2 setup

SSH into the instance and prepare it for deployments:

```bash
# Install Docker
sudo apt-get update -y
sudo apt-get install -y docker.io
sudo systemctl enable --now docker

# Create application directory and environment file
sudo mkdir -p /srv/chat-backend
sudo chown "$(whoami)" /srv/chat-backend
cat <<'ENVV' > /srv/chat-backend/.env
PORT=8000
CORS_ORIGINS=http://localhost:5173
ENVV
```

Adjust the `.env` file to match your production configuration if needed.

### Deployment verification

After each deploy the workflow automatically rebuilds the Docker image, restarts the `chat-backend` container, and runs a health check against `http://127.0.0.1:8000/healthz`. From outside the server you can verify the deployment via the Nginx proxy:

```bash
curl http://<SERVER_DOMAIN>/healthz
curl -N -X POST http://<SERVER_DOMAIN>/api/chat -H "Content-Type: application/json" -d '{"message":"hello"}'
```

### Rollback

If you need to roll back to a previous image tag, run:

```bash
sudo docker stop chat-backend && sudo docker rm chat-backend
sudo docker run -d --name chat-backend --restart unless-stopped \
  --env-file /srv/chat-backend/.env -p 8000:8000 chat-backend:<OLD_TAG>
```

Replace `<OLD_TAG>` with the image tag output by the workflow logs.

## Curl Example

Use `curl` with `-N` to preserve the streaming output:

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello"}'
```

You should see the placeholder text arrive in small chunks until the stream completes.
