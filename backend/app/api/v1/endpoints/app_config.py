"""Public app configuration endpoint — no auth required"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class AppConfigResponse(BaseModel):
    require_invite: bool


@router.get("", response_model=AppConfigResponse)
async def get_app_config():
    """
    Return public app configuration that the frontend needs before login.
    Currently exposes whether invite tokens are required for registration.
    """
    return AppConfigResponse(require_invite=settings.require_invite)
