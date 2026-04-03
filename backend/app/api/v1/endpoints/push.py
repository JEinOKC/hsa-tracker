"""Push notification endpoints — subscribe, unsubscribe, VAPID key, and test trigger."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.utils.push import send_push_to_user

router = APIRouter()


class PushSubscribePayload(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}
    user_agent: str | None = None


@router.get("/vapid-public-key")
def get_vapid_public_key():
    """Return the VAPID public key so the frontend can subscribe."""
    return {"vapid_public_key": settings.vapid_public_key or ""}


@router.post("/subscribe", status_code=201)
def subscribe(
    payload: PushSubscribePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save (or reactivate) a push subscription for the current user."""
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .first()
    )
    if existing:
        existing.user_id = current_user.id
        existing.is_active = True
        existing.p256dh = payload.keys["p256dh"]
        existing.auth = payload.keys["auth"]
    else:
        db.add(
            PushSubscription(
                user_id=current_user.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys["p256dh"],
                auth=payload.keys["auth"],
                user_agent=payload.user_agent,
            )
        )
    db.commit()
    return {"ok": True}


@router.delete("/subscribe", status_code=204)
def unsubscribe(
    payload: PushSubscribePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a push subscription for the current user."""
    db.query(PushSubscription).filter(
        PushSubscription.user_id == current_user.id,
        PushSubscription.endpoint == payload.endpoint,
    ).delete()
    db.commit()


@router.post("/test")
def send_test_push(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger a test push notification to all of the current user's subscriptions."""
    count = send_push_to_user(
        user_id=current_user.id,
        title="HSA Tracker",
        body="Test notification — push is working!",
        db=db,
    )
    return {"sent_to": count}
