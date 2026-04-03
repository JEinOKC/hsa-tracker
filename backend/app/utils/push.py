"""Web Push notification helper using pywebpush + VAPID."""

import json

from sqlalchemy.orm import Session

from app.config import settings
from app.models.push_subscription import PushSubscription


def send_push_to_user(user_id, title: str, body: str, db: Session) -> int:
    """Send a push notification to all active subscriptions for a user.

    Returns the number of successful sends.
    Silently deactivates subscriptions that return 404/410 (Gone).
    Does nothing if VAPID keys are not configured.
    """
    if not settings.vapid_private_key:
        return 0

    from pywebpush import webpush, WebPushException  # lazy import — optional dep

    subs = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active == True,  # noqa: E712
        )
        .all()
    )

    payload = json.dumps({"title": title, "body": body})
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_claims_email},
            )
            sent += 1
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (404, 410):
                sub.is_active = False
                db.commit()
    return sent
