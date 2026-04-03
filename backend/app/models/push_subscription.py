"""Push subscription model for Web Push notifications."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(Text, nullable=False)   # keys.p256dh from PushSubscription.toJSON()
    auth = Column(Text, nullable=False)     # keys.auth from PushSubscription.toJSON()
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")
