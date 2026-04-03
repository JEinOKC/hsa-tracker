#!/usr/bin/env python3
"""
Send a test push notification to all active subscriptions in the database.

Usage (run from the backend/ directory):

  python scripts/send_test_push.py
  python scripts/send_test_push.py "Custom Title" "Custom body message"

Requires VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY to be set in your .env.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models.push_subscription import PushSubscription  # noqa: F401 — registers with Base.metadata
from app.utils.push import send_push_to_user

title = sys.argv[1] if len(sys.argv) > 1 else "HSA Tracker"
body = sys.argv[2] if len(sys.argv) > 2 else "Test push notification from make push-test"

if not settings.vapid_private_key:
    print("\nERROR: VAPID_PRIVATE_KEY is not set.")
    print("Run: python scripts/generate_vapid_keys.py  to generate keys\n")
    sys.exit(1)

engine = create_engine(settings.database_url)
Session = sessionmaker(bind=engine)
db = Session()

# Find all users with active subscriptions and send to each
from app.models.user import User  # noqa: F401

user_ids = (
    db.query(PushSubscription.user_id)
    .filter(PushSubscription.is_active == True)  # noqa: E712
    .distinct()
    .all()
)

if not user_ids:
    print("\nNo active push subscriptions found.")
    print("Subscribe first via the Settings page in the app.\n")
    sys.exit(0)

total = 0
for (user_id,) in user_ids:
    sent = send_push_to_user(user_id=user_id, title=title, body=body, db=db)
    total += sent
    print(f"  user {user_id}: sent {sent} notification(s)")

print(f"\nDone — {total} notification(s) sent to {len(user_ids)} user(s).\n")
