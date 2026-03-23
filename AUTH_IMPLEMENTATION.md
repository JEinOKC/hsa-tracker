# Authentication Implementation Status

## Current State

This app uses **passkey-only authentication** (WebAuthn/FIDO2). There is no email/password login UI and none is planned.

Email/password and TOTP backend code exists in `auth.py` and `security.py` but has no frontend and is not used. It can be ignored or removed in the future.

---

## What Works

### Backend

| Component | Status | Location |
|-----------|--------|----------|
| Passkey registration (start + complete) | ✅ | `api/v1/endpoints/passkey.py` |
| Passkey login (start + complete) | ✅ | `api/v1/endpoints/passkey.py` |
| JWT token generation (access + refresh) | ✅ | `utils/security.py` |
| Auth middleware (`get_current_user`) | ✅ | `dependencies.py` |
| User model + passkey model | ✅ | `models/user.py` |
| WebAuthn helpers | ✅ | `utils/webauthn.py` |

Endpoints:
- `POST /api/v1/passkey/register/start`
- `POST /api/v1/passkey/register/complete`
- `POST /api/v1/passkey/login/start`
- `POST /api/v1/passkey/login/complete`
- `GET /api/v1/auth/me` (requires valid JWT)

### Frontend

| Component | Status | Location |
|-----------|--------|----------|
| Passkey service (API calls) | ✅ | `services/passkey.ts` |
| Auth service (token storage, `isAuthenticated`) | ✅ | `services/auth.ts` |
| Auth state (Zustand) | ✅ | `store/authStore.ts` |
| PasskeyLoginForm | ✅ | `components/auth/PasskeyLoginForm.tsx` |
| PasskeyRegisterForm | ✅ | `components/auth/PasskeyRegisterForm.tsx` |
| ProtectedRoute | ✅ | `components/ProtectedRoute.tsx` |
| Login page | ✅ | `pages/Login.tsx` |

### Tests

- **Backend**: 62 tests passing, 78% coverage (`backend/tests/`)
- **Frontend**: 34 tests passing (`frontend/src/**/__tests__/`)

---

## What's Stubbed (Not Implemented)

All business logic endpoints return empty arrays or 501 Not Implemented. This is documented by `backend/tests/test_stub_endpoints.py`.

| Area | GET list | GET by ID | POST/PUT/DELETE |
|------|----------|-----------|-----------------|
| Transactions | `[]` | 404 | 501 |
| Families | `[]` | 404 | 501 |
| Categories | 5 hardcoded system categories | — | 501 |

---

## Running Tests

```bash
# Backend (requires Docker)
docker-compose -f docker-compose.dev.yml exec backend pytest -v

# Frontend (requires Node 20)
source ~/.nvm/nvm.sh && nvm use 20
cd frontend && npm run test:run
```

---

## Security Notes

- Passkeys are phishing-resistant by design (FIDO2/WebAuthn)
- Access tokens expire in 30 minutes, refresh tokens in 7 days
- Tokens stored in localStorage
- HTTPS required in production (WebAuthn requirement)
- Set `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` to your domain before deploying

## Production Checklist

1. Enable HTTPS/TLS
2. Set strong `SECRET_KEY` and `JWT_SECRET_KEY` in `.env`
3. Set `WEBAUTHN_RP_ID` and `WEBAUTHN_ORIGIN` to your domain
4. Run database migration: `make db-upgrade`
