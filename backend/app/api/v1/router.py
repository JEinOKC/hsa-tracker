"""Main API router for v1 endpoints"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    passkey,
    families,
    transactions,
    categories,
    bank,
    documents,
)

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(passkey.router, prefix="/passkey", tags=["Passkey Authentication"])
api_router.include_router(families.router, prefix="/families", tags=["Families"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(bank.router, prefix="/bank", tags=["Bank Integration"])
api_router.include_router(documents.router, prefix="/bank", tags=["Documents"])
