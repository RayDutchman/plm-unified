"""M1.5 认证测试。"""
import pytest
from jose import ExpiredSignatureError


def test_password_hash_roundtrip():
    from app.core.security import get_password_hash, verify_password
    h = get_password_hash("admin12345")
    assert h != "admin12345"
    assert verify_password("admin12345", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_handles_garbage_hash():
    from app.core.security import verify_password
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_access_token_encode_decode():
    from app.core.security import create_access_token, decode_token
    tok = create_access_token({"sub": "admin", "role": "admin"})
    payload = decode_token(tok)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert payload["typ"] == "access"


def test_expired_token_rejected():
    from datetime import timedelta
    from app.core.security import create_access_token, decode_token
    tok = create_access_token({"sub": "admin"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ExpiredSignatureError):
        decode_token(tok)
