"""Main API router for v1 endpoints"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    app_config,
    auth,
    passkey,
    family_invites,
    families,
    transactions,
    categories,
    bank,
    documents,
    roles,
    households,
    push,
    rules,
)

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(app_config.router, prefix="/config", tags=["App Config"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(passkey.router, prefix="/passkey", tags=["Passkey Authentication"])
api_router.include_router(family_invites.router, prefix="/family-invites", tags=["Family Invites"])
api_router.include_router(families.router, prefix="/families", tags=["Families"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(bank.router, prefix="/bank", tags=["Bank Integration"])
api_router.include_router(documents.router, prefix="/bank", tags=["Documents"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles & Access"])
api_router.include_router(households.router, prefix="/households", tags=["Households"])
api_router.include_router(push.router, prefix="/push", tags=["Push Notifications"])
api_router.include_router(rules.router, prefix="/bank", tags=["HSA Rules Engine"])
