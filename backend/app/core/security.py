"""密码哈希与 JWT 令牌编解码。密码用裸 bcrypt（与 myPDM 一致）。"""
from datetime import datetime, timedelta

import bcrypt
from jose import jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480   # 8 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 启动即校验密钥强度，避免弱密钥签发可伪造令牌
if len(settings.jwt_secret) < 32:
    raise RuntimeError("JWT_SECRET 长度不足，至少 32 个字符（生成：openssl rand -hex 32）")


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "typ": "access"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def create_refresh_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": username, "exp": expire, "typ": "refresh"}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并校验签名/过期；失败抛 jose 异常（JWTError/ExpiredSignatureError）。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
