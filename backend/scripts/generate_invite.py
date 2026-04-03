#!/usr/bin/env python3
"""
CLI for managing HSA Tracker registration invite tokens.

Usage (run from the backend/ directory with your .env in place):

  python scripts/generate_invite.py create
  python scripts/generate_invite.py create --label "for alice"
  python scripts/generate_invite.py list
  python scripts/generate_invite.py revoke solemn-laughing-monkey

Tokens look like: solemn-laughing-monkey
Each token is single-use — once someone registers with it, it's burned.
"""

import argparse
import os
import sys
from datetime import datetime

# Allow running from the backend/ directory directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coolname import generate_slug
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load .env before importing app modules (mirrors what uvicorn does)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
except ImportError:
    pass  # dotenv is optional; env vars may already be set

from app.config import settings
from app.database import Base
from app.models.user import RegistrationToken  # noqa: F401 — registers with Base.metadata


def get_session():
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)  # no-op if tables already exist
    Session = sessionmaker(bind=engine)
    return Session()


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_create(args):
    session = get_session()
    token_str = generate_slug(3)
    token = RegistrationToken(token=token_str, label=args.label or None)
    session.add(token)
    session.commit()
    print(f"\nInvite token created:")
    print(f"\n  {token_str}\n")
    if args.label:
        print(f"  Label : {args.label}")
    print(f"  Share this token with the person you want to invite.")
    print(f"  It can only be used once.\n")


def cmd_list(args):
    session = get_session()
    tokens = session.query(RegistrationToken).order_by(RegistrationToken.created_at.desc()).all()

    if not tokens:
        print("\nNo invite tokens found.\n")
        return

    col_w = [36, 20, 8, 20]
    header = f"{'TOKEN':<{col_w[0]}}  {'LABEL':<{col_w[1]}}  {'STATUS':<{col_w[2]}}  {'USED BY':<{col_w[3]}}"
    print(f"\n{header}")
    print("-" * (sum(col_w) + 6))
    for t in tokens:
        status = "used" if t.is_used else "unused"
        used_by = t.used_by_username or ""
        label = t.label or ""
        print(f"{t.token:<{col_w[0]}}  {label:<{col_w[1]}}  {status:<{col_w[2]}}  {used_by:<{col_w[3]}}")
    print()


def cmd_revoke(args):
    session = get_session()
    token = session.query(RegistrationToken).filter(RegistrationToken.token == args.token).first()
    if not token:
        print(f"\nToken not found: {args.token}\n")
        sys.exit(1)
    if token.is_used:
        print(f"\nToken '{args.token}' was already used by '{token.used_by_username}' — nothing to revoke.\n")
        sys.exit(1)
    session.delete(token)
    session.commit()
    print(f"\nToken revoked: {args.token}\n")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manage HSA Tracker registration invite tokens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Generate a new invite token")
    p_create.add_argument("--label", help="Optional note about who this token is for")

    sub.add_parser("list", help="List all tokens and their status")

    p_revoke = sub.add_parser("revoke", help="Delete an unused token")
    p_revoke.add_argument("token", help="The token string to revoke")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "revoke":
        cmd_revoke(args)


if __name__ == "__main__":
    main()
