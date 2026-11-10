"""Task 2: minimal HTTP JSON-RPC reverse proxy with tool-level RBAC."""
import os
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from .auth import get_role_from_authorization

app = FastAPI(title="QuillrAI MCP Security Gateway")
DOWNSTREAM_URL = os.getenv("DOWNSTREAM_MCP_URL", "http://127.0.0.1:9001/rpc")


def rpc_error(request_id, code: int, message: str):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


@app.post("/rpc")
async def proxy_rpc(request: Request, authorization: str | None = Header(default=None)):
    role = get_role_from_authorization(authorization)
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(rpc_error(None, -32700, "Parse error"), status_code=400)

    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
        return JSONResponse(rpc_error(payload.get("id") if isinstance(payload, dict) else None,
                                      -32600, "Invalid Request"), status_code=400)

    method = payload["method"]
    request_id = payload.get("id")

    if method == "tools/call":
        params = payload.get("params")
        tool_name = params.get("name") if isinstance(params, dict) else None
        if not isinstance(tool_name, str):
            return JSONResponse(rpc_error(request_id, -32602, "Invalid params"), status_code=400)
        if tool_name.startswith("admin_") and role != "admin":
            return JSONResponse(rpc_error(request_id, -32001, "Unauthorized Tool Call"), status_code=403)
    elif method != "tools/list":
        # Other MCP methods are passed through; downstream remains responsible for protocol validation.
        pass

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upstream = await client.post(
                DOWNSTREAM_URL,
                content=await request.body(),
                headers={"content-type": "application/json", "accept": request.headers.get("accept", "application/json")},
            )
        return Response(content=upstream.content, status_code=upstream.status_code,
                        headers={"content-type": upstream.headers.get("content-type", "application/json")})
    except httpx.TimeoutException:
        return JSONResponse(rpc_error(request_id, -32000, "Downstream timeout"), status_code=504)
    except httpx.HTTPError:
        return JSONResponse(rpc_error(request_id, -32000, "Downstream unavailable"), status_code=502)
