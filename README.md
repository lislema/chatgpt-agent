# ChatGPT Agent (FastAPI + Docker)

FastAPI microservice exposing **OpenAI ChatGPT models** (via the `responses` API) behind a simple REST interface.

- `/health` → health check  
- `/prompt` → one-shot text generation  
- `/chat` → multi-turn conversation  
- `/stream` → SSE streaming of incremental output  

---

## Features
- Simple REST wrapper around OpenAI GPT models (`gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, etc).  
- Supports system instructions and multi-turn conversations.  
- Secure, multi-stage Docker build (`debug` and `prod` targets).  
- `.env` file for API key and default model.  

---

## Project Structure
```
.
├── main.py          # FastAPI app
├── requirements.txt # Python dependencies
├── Dockerfile       # Multi-stage build (builder, debug, prod)
├── .env             # Local environment variables (ignored by git)
├── .dockerignore
└── .gitignore
```

---

## Environment Variables

Create a `.env` file in the project root:

```dotenv
# OpenAI API key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Default model to use
# Options:
#   gpt-4o        (balanced, multimodal, production-ready)
#   gpt-4o-mini   (fast, cheap, great default)
#   gpt-4.1       (deeper reasoning, slower)
#   gpt-4.1-mini  (smarter reasoning, cheaper than gpt-4.1)
OPENAI_MODEL=gpt-4o-mini
```

⚠️ `.env` is ignored via `.gitignore` — never commit real keys.  
Commit a `.env.example` with placeholders if needed.

---

## Dependencies

`requirements.txt`:

```txt
fastapi==0.112.2
uvicorn==0.30.6
pydantic==2.8.2
python-dotenv==1.0.1
openai>=1.40.0
```

---

## Docker Setup

Multi-stage Dockerfile:
- **builder** → installs deps into `/app/site-packages`
- **debug** → Chainguard base with shell/tools (~700 MB)
- **prod** → Chainguard minimal runtime (~80 MB, secure)

### Build Debug
```bash
docker build --target debug -t chatgpt-agent:debug .
```

### Run Debug
```bash
docker run --rm -p 8080:8080   --env-file .env   --cap-drop ALL --security-opt no-new-privileges   --name chatgpt-agent-debug   chatgpt-agent:debug
```

### Build Prod
```bash
docker build --target prod -t chatgpt-agent:prod .
```

### Run Prod (secure, non-root, read-only)
```bash
docker run --rm -p 8080:8080   --env-file .env   --read-only   --cap-drop ALL   --security-opt no-new-privileges   --tmpfs /tmp:rw,noexec,nosuid,size=16m   --name chatgpt-agent-prod   chatgpt-agent:prod
```

---

## 🧪 Testing with `curl`

### Health
```bash
curl -s http://localhost:8080/health | jq .
```

### Prompt
```bash
curl -s http://localhost:8080/prompt   -H "Content-Type: application/json"   -d '{
    "prompt": "Give me three bullet points on why agents need guardrails.",
    "system": "You are a concise security architect.",
    "temperature": 0.2,
    "max_output_tokens": 256
  }' | jq .
```

### Chat
```bash
curl -s http://localhost:8080/chat   -H "Content-Type: application/json"   -d '{
    "messages": [
      {"role": "system", "content": "You are a concise API architect."},
      {"role": "user", "content": "What is an API gateway?"},
      {"role": "assistant", "content": "It manages, secures, and routes API traffic."},
      {"role": "user", "content": "Name two benefits of putting one in front of LLMs."}
    ],
    "temperature": 0.2,
    "max_output_tokens": 180
  }' | jq .
```

### Stream (SSE)
```bash
curl -N http://localhost:8080/stream   -H "Content-Type: application/json"   -d '{"prompt":"Write a short poem about GKE and API gateways."}'
```

---

## Image Size & Security

Check image sizes:
```bash
docker images | grep chatgpt-agent
```

Inspect CVEs (with [Trivy](https://github.com/aquasecurity/trivy)):
```bash
trivy image --severity HIGH,CRITICAL chatgpt-agent:prod
```

---

## Notes
- Default model can be overridden per-request in `/prompt` and `/chat`.  
- Debug image is large but useful for troubleshooting; prod image is small & hardened.  
- SSE endpoint (`/stream`) streams incremental chunks and the final response.  


