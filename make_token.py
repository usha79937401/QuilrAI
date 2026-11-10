"""Local-only helper to mint short-lived test JWTs."""
import os, sys, time, jwt

if len(sys.argv) != 2 or sys.argv[1] not in {"admin", "viewer"}:
    raise SystemExit("Usage: python -m task2_mcp_gateway.make_token admin|viewer")
secret = os.getenv("JWT_SECRET")
if not secret:
    raise SystemExit("Set JWT_SECRET first")
print(jwt.encode({"role": sys.argv[1], "iat": int(time.time()), "exp": int(time.time()) + 3600}, secret, algorithm="HS256"))
