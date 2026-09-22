import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adlex.db.base import Base


class Conversation(Base):
    """Диалог пользователя с сервисом: контейнер для сообщений и прогонов агента."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class Message(Base):
    """Одно сообщение диалога. Ответы ассистента хранят цитаты в meta."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages", lazy="raise")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="role_valid"),
        # Под главный запрос: «покажи историю диалога по порядку».
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )
