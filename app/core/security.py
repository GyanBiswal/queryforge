import secrets
import logging
from fastapi import Security, HTTPException, Depends
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db.database import get_db
from app.db.models import ApiKey

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> str:
    """Generates a new plaintext key — shown to the user ONCE at creation time, never stored."""
    return f"qf_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return pwd_context.hash(raw_key)


def verify_api_key(
    provided_key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    """
    FastAPI dependency — validates the X-API-Key header against stored hashes.
    Raises 401 if missing, invalid, or revoked.
    """
    if not provided_key:
        raise HTTPException(status_code=401, detail="Missing API key. Provide it via the X-API-Key header.")

    # We can't look up by hash directly (bcrypt hashes are salted, non-deterministic),
    # so we check the provided key against every active key's hash. Fine at small scale;
    # a real high-traffic system would use a fast lookup prefix + hash suffix instead.
    active_keys = db.query(ApiKey).filter(ApiKey.is_active == True).all()

    for key_record in active_keys:
        if pwd_context.verify(provided_key, key_record.key_hash):
            key_record.last_used_at = datetime.now(timezone.utc)
            db.commit()
            return key_record

    logger.warning("Rejected request with invalid or revoked API key")
    raise HTTPException(status_code=401, detail="Invalid or revoked API key.")