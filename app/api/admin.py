import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ApiKey
from app.core.security import generate_api_key, hash_api_key
from app.schemas.api_key import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/api-keys", tags=["admin"])

# NOTE: this router is intentionally NOT protected by verify_api_key — it's the
# bootstrap mechanism for issuing the first key. In a real deployment this would
# sit behind a separate, more privileged admin credential or be a one-time CLI
# script, not a public HTTP endpoint. Flagged explicitly as a known scope
# limitation for this portfolio project.


@router.post("", response_model=ApiKeyCreateResponse)
def create_api_key(request: ApiKeyCreateRequest, db: Session = Depends(get_db)):
    raw_key = generate_api_key()
    key_record = ApiKey(key_hash=hash_api_key(raw_key), label=request.label)
    db.add(key_record)
    db.commit()
    db.refresh(key_record)

    return ApiKeyCreateResponse(
        id=key_record.id,
        label=key_record.label,
        api_key=raw_key,  # only time this is ever exposed
        created_at=key_record.created_at,
    )


@router.get("", response_model=list[ApiKeyInfo])
def list_api_keys(db: Session = Depends(get_db)):
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.patch("/{key_id}/revoke", response_model=ApiKeyInfo)
def revoke_api_key(key_id: str, db: Session = Depends(get_db)):
    key_record = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not key_record:
        raise HTTPException(status_code=404, detail="API key not found")
    key_record.is_active = False
    db.commit()
    db.refresh(key_record)
    return key_record