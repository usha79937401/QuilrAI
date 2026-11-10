import os, time, jwt
from task2_mcp_gateway.auth import get_role_from_authorization

def test_extract_role(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    token = jwt.encode({"role": "admin", "exp": int(time.time()) + 60}, "test-secret", algorithm="HS256")
    assert get_role_from_authorization("Bearer " + token) == "admin"
