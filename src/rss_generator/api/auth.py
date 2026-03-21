import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from ..models.database import get_session
from ..config import settings
from ..models.auth import AuthConfig

router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30
_PBKDF2_ITERATIONS = 310_000

_secret: Optional[str] = None


def get_secret() -> str:
    global _secret
    if _secret is None:
        _secret = settings.jwt_secret if settings.jwt_secret else secrets.token_hex(32)
    return _secret


# ── Password hashing (PBKDF2-SHA256, no third-party deps) ────────────────────

def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": username, "exp": expire}, get_secret(), algorithm=ALGORITHM)


def verify_token(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    try:
        payload = jwt.decode(token, get_secret(), algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


SessionDep = Annotated[Session, Depends(get_session)]


# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangeCredentialsRequest(BaseModel):
    current_password: str
    new_username: Optional[str] = None
    new_password: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    config = session.exec(select(AuthConfig)).first()
    if not config:
        raise HTTPException(status_code=500, detail="Auth not configured")
    if form.username != config.username or not verify_password(form.password, config.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_token(config.username))


@router.get("/me")
def me(username: Annotated[str, Depends(verify_token)]):
    return {"username": username}


@router.put("/credentials")
def change_credentials(
    body: ChangeCredentialsRequest,
    username: Annotated[str, Depends(verify_token)],
    session: SessionDep,
):
    config = session.exec(select(AuthConfig)).first()
    if not config:
        raise HTTPException(status_code=500, detail="Auth not configured")
    if not verify_password(body.current_password, config.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.new_username:
        config.username = body.new_username
    if body.new_password:
        config.password_hash = hash_password(body.new_password)
    session.add(config)
    session.commit()
    return TokenResponse(access_token=create_token(config.username))
