"""Task 4: per-tenant token quota and model failover router."""
import asyncio
import os
import time
import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .database import TokenDatabase
from .rate_limiter import SlidingWindowTokenLimiter, RateLimitExceeded

app = FastAPI(title="QuillrAI Model Router")
db = TokenDatabase(os.getenv("TOKEN_DB_PATH", "token_usage.sqlite3"))
limiter = SlidingWindowTokenLimiter(db, limit=50_000, window_seconds=60)


class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    max_tokens: int = Field(default=1000, ge=1, le=20_000)


def estimate_tokens(text: str) -> int:
    # Conservative lightweight estimate; replace with provider tokenizer in production.
    return max(1, (len(text) + 3) // 4)


async def call_provider(url: str | None, payload: dict, provider_name: str):
    if not url:
        # Deterministic local mock provider makes the assessment runnable offline.
        return {"provider": provider_name, "output": f"[{provider_name} mock] {payload['prompt'][:120]}"}
    async with httpx.AsyncClient(timeout=3.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code == 429:
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
        response.raise_for_status()
        return response.json()


@app.post("/v1/completions")
async def create_completion(body: CompletionRequest, x_tenant_key: str | None = Header(default=None)):
    if not x_tenant_key:
        raise HTTPException(status_code=401, detail={"code": "TENANT_KEY_REQUIRED", "message": "Tenant key required"})
    estimated = estimate_tokens(body.prompt) + body.max_tokens
    try:
        quota = await limiter.reserve(x_tenant_key, estimated)
    except RateLimitExceeded:
        raise HTTPException(status_code=429, detail={"code": "TOKEN_RATE_LIMIT", "message": "Tenant token limit exceeded"}) from None

    payload = {"prompt": body.prompt, "max_tokens": body.max_tokens}
    primary = os.getenv("PRIMARY_MODEL_URL")
    backup = os.getenv("BACKUP_MODEL_URL")
    try:
        result = await asyncio.wait_for(call_provider(primary, payload, "primary"), timeout=3.0)
        selected = "primary"
    except (asyncio.TimeoutError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
        is_429 = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
        is_timeout = isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException))
        if not (is_429 or is_timeout):
            raise HTTPException(status_code=502, detail={"code": "MODEL_UPSTREAM_ERROR", "message": "Model provider failed"}) from None
        try:
            result = await asyncio.wait_for(call_provider(backup, payload, "backup"), timeout=10.0)
            selected = "backup"
        except Exception:
            raise HTTPException(status_code=502, detail={"code": "MODEL_UNAVAILABLE", "message": "Primary and backup models unavailable"}) from None
    except Exception:
        raise HTTPException(status_code=502, detail={"code": "MODEL_UPSTREAM_ERROR", "message": "Model provider failed"}) from None

    return {"provider": selected, "result": result, "quota": quota}
