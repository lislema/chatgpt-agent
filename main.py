import os
import json
from typing import List, Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# OpenAI SDK (v1.x)
from openai import OpenAI

# --- Bootstrap ---
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY. Set it in your environment or .env file.")

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=API_KEY)

app = FastAPI(
    title="Local ChatGPT Agent",
    version="1.0.0",
    description="FastAPI microservice that routes requests to OpenAI GPT models via the Responses API.",
)

# -------- Helpers --------
def _out_text_from_response(resp) -> str:
    """
    Extract plain text from OpenAI Responses API response.
    Prefers resp.output_text; otherwise walks resp.output items.
    """
    text = getattr(resp, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    try:
        out = []
        output = getattr(resp, "output", None) or []
        for item in output:
            t = getattr(item, "text", None)
            if t and getattr(t, "value", None):
                out.append(t.value)
        if out:
            return "\n".join(out)
    except Exception:
        pass
    return ""

def _err(detail: str, code: str = "GENERATION_ERROR", status: int = 500):
    raise HTTPException(status_code=status, detail={"code": code, "message": detail})

# -------- Schemas --------
class PromptRequest(BaseModel):
    prompt: str = Field(..., description="User prompt text.")
    model: Optional[str] = Field(None, description="Override model id (defaults to env).")
    system: Optional[str] = Field(None, description="Optional system instruction.")
    max_output_tokens: Optional[int] = Field(1024, ge=1, le=8192)
    temperature: Optional[float] = Field(0.3, ge=0.0, le=2.0)

class ChatMessage(BaseModel):
    # OpenAI roles we’ll accept
    role: str = Field(..., pattern="^(system|developer|user|assistant)$")
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., description="Chronological messages.")
    model: Optional[str] = None
    max_output_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.3

# -------- Routes --------
@app.get("/health")
def health():
    return JSONResponse(content={"status": "ok", "version": "1.0.0", "service": "chatgpt-agent"})

@app.post("/prompt")
def prompt(req: PromptRequest):
    """
    One-shot text generation with optional system instruction.
    """
    model = req.model or DEFAULT_MODEL
    try:
        resp = client.responses.create(
            model=model,
            instructions=req.system or None,          # system-style guidance
            input=req.prompt,                         # user text
            temperature=req.temperature or 0.3,
            max_output_tokens=req.max_output_tokens or 1024,
        )
        return {"model": model, "output": _out_text_from_response(resp)}
    except Exception as e:
        _err(str(e))

@app.post("/chat")
def chat(req: ChatRequest):
    """
    Multi-turn chat. We fold messages into:
    - instructions: concat of system/developer
    - input: a readable transcript of user/assistant turns
    """
    model = req.model or DEFAULT_MODEL
    sys_parts, convo = [], []

    for m in req.messages:
        if m.role in ("system", "developer"):
            sys_parts.append(m.content)
        else:
            prefix = "User" if m.role == "user" else "Assistant"
            convo.append(f"{prefix}: {m.content}")

    instructions = "\n".join(sys_parts) if sys_parts else None
    input_blob = "\n".join(convo) if convo else ""

    try:
        resp = client.responses.create(
            model=model,
            instructions=instructions,
            input=input_blob,
            temperature=req.temperature or 0.3,
            max_output_tokens=req.max_output_tokens or 1024,
        )
        return {"model": model, "output": _out_text_from_response(resp)}
    except Exception as e:
        _err(str(e))

@app.post("/stream")
def stream(req: PromptRequest):
    """
    SSE streaming using OpenAI Responses API (stream=True).
    Emits:
      data: {"delta": "..."}  for incremental chunks
      data: {"final": "..."}  once complete
    """
    async def event_gen() -> AsyncGenerator[bytes, None]:
        model = req.model or DEFAULT_MODEL
        try:
            stream = client.responses.create(
                model=model,
                instructions=req.system or None,
                input=req.prompt,
                temperature=req.temperature or 0.3,
                max_output_tokens=req.max_output_tokens or 1024,
                stream=True,
            )
            final_buf: list[str] = []
            for event in stream:
                etype = getattr(event, "type", None)
                if etype == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    if delta:
                        final_buf.append(delta)
                        yield f"data: {json.dumps({'delta': delta})}\n\n".encode("utf-8")
                elif etype == "response.completed":
                    final_text = "".join(final_buf)
                    yield f"data: {json.dumps({'final': final_text})}\n\n".encode("utf-8")
                # ignore other event types for this simple agent
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.get("/versions")
def versions():
    import openai as _openai
    return {
        "service": "chatgpt-agent",
        "sdk": getattr(_openai, "__version__", "unknown"),
        "model_default": DEFAULT_MODEL,
        "env_key_present": bool(API_KEY),
    }