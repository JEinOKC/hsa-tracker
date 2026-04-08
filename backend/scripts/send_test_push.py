#!/usr/bin/env python3
"""
Send a test push notification to active subscriptions in the database.

Usage (run from the backend/ directory):

  python scripts/send_test_push.py
  python scripts/send_test_push.py "Custom Title" "Custom body message"
  python scripts/send_test_push.py "Title" "Body" --user email@example.com

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

args = [a for a in sys.argv[1:] if not a.startswith('--')]
title = args[0] if len(args) > 0 else "HSA Tracker"
body = args[1] if len(args) > 1 else "Test push notification from make push-test"

target_email = None
if '--user' in sys.argv:
    idx = sys.argv.index('--user')
    if idx + 1 < len(sys.argv):
        target_email = sys.argv[idx + 1]

if not settings.vapid_private_key:
    print("\nERROR: VAPID_PRIVATE_KEY is not set.")
    print("Run: python scripts/generate_vapid_keys.py  to generate keys\n")
    sys.exit(1)

from app.database import _clean_database_url
engine = create_engine(_clean_database_url(settings.database_url))
Session = sessionmaker(bind=engine)
db = Session()

# Find target users with active subscriptions
from app.models.user import User  # noqa: F401

query = db.query(PushSubscription.user_id).filter(PushSubscription.is_active == True)  # noqa: E712

if target_email:
    user = db.query(User).filter(
        (User.username == target_email) | (User.email == target_email)
    ).first()
    if not user:
        print(f"\nERROR: No user found with username or email '{target_email}'.\n")
        sys.exit(1)
    query = query.filter(PushSubscription.user_id == user.id)
    print(f"\nSending to user: {target_email}")

user_ids = query.distinct().all()

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
