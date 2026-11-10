"""Task 3: OpenAI-compatible SSE proxy with streaming PII redaction."""
import json
import os
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from .redaction import StreamingRedactor

app = FastAPI(title="QuillrAI LLM Streaming Guardrail")


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    upstream_url = os.getenv("UPSTREAM_CHAT_COMPLETIONS_URL")
    api_key = os.getenv("UPSTREAM_API_KEY")
    if not upstream_url:
        raise HTTPException(status_code=503, detail="LLM upstream is not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request") from None
    body["stream"] = True
    headers = {"content-type": "application/json", "accept": "text/event-stream"}
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    async def event_stream():
        redactor = StreamingRedactor()
        # A dedicated streaming client keeps the upstream response open while yielding downstream.
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", upstream_url, json=body, headers=headers) as upstream:
                if upstream.status_code >= 400:
                    # Do not leak upstream response bodies, stack traces, or secrets.
                    safe = json.dumps({"error": {"message": "LLM provider request failed", "type": "upstream_error"}})
                    yield f"data: {safe}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                async for line in upstream.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].lstrip()
                    if payload == "[DONE]":
                        tail = redactor.finish()
                        if tail:
                            # Final tail is emitted as a synthetic text delta.
                            event = {"choices": [{"index": 0, "delta": {"content": tail}, "finish_reason": None}]}
                            yield "data: " + json.dumps(event, separators=(",", ":")) + "\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {})
                        content = delta.get("content")
                        if isinstance(content, str):
                            safe_text = redactor.push(content)
                            delta["content"] = safe_text
                    yield "data: " + json.dumps(event, separators=(",", ":")) + "\n\n"
                tail = redactor.finish()
                if tail:
                    event = {"choices": [{"index": 0, "delta": {"content": tail}, "finish_reason": None}]}
                    yield "data: " + json.dumps(event, separators=(",", ":")) + "\n\n"
                yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"cache-control": "no-cache", "x-accel-buffering": "no"})
