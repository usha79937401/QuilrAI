"""JWT bearer authentication helpers for the MCP gateway."""
import os
import jwt
from fastapi import HTTPException, status


def get_role_from_authorization(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Gateway authentication is not configured")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token") from None
    role = claims.get("role")
    if role not in {"admin", "viewer"}:
        raise HTTPException(status_code=403, detail="Unsupported role")
    return role
