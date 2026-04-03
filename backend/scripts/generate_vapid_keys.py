#!/usr/bin/env python3
"""
One-time VAPID key generator for Web Push notifications.

Run once, then add the output values to your .env / Doppler:

  cd backend && python scripts/generate_vapid_keys.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from py_vapid import Vapid
except ImportError:
    print("ERROR: pywebpush not installed. Run: pip install pywebpush")
    sys.exit(1)

v = Vapid()
v.generate_keys()

import base64
from cryptography.hazmat.primitives import serialization

# Private key as raw base64url scalar (no newlines — safe for env vars / Doppler)
raw_private = v.private_key.private_numbers().private_value.to_bytes(32, "big")
private_b64 = base64.urlsafe_b64encode(raw_private).rstrip(b"=").decode()

raw_public = v.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)
public_b64 = base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode()

print("\nVAPID keys generated — add these to your .env / Doppler:\n")
print(f"VAPID_PRIVATE_KEY={private_b64}")
print(f"VAPID_PUBLIC_KEY={public_b64}")
print(f"VITE_VAPID_PUBLIC_KEY={public_b64}")
print()
print("(VITE_VAPID_PUBLIC_KEY and VAPID_PUBLIC_KEY should be the same value)")
