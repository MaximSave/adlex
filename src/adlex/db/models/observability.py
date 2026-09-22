import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adlex.db.base import Base


class AgentRun(Base):
    """Один прогон графа агента: что спросили, чем кончилось, сколько стоило.

    Эти две таблицы и превращают агента из чёрного ящика в объяснимую систему:
    по ним видно, какие шаги были сделаны, почему прогон упал и во что обошёлся.
    """

    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    intent: Mapped[str] = mapped_column(String(32))  # qa | check | landing
    status: Mapped[str] = mapped_column(String(24), default="running")
    model: Mapped[str] = mapped_column(String(128))

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    # Деньги — Numeric, а не float: двоичная дробь не хранит копейки точно.
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'done', 'failed', 'awaiting_approval')",
            name="status_valid",
        ),
        # «Последние прогоны этого диалога»
        Index(
            "ix_agent_runs_conversation_id_created_at",
            "conversation_id",
            created_at.desc(),
        ),
        # «Все упавшие за сутки»
        Index("ix_agent_runs_status_created_at", "status", created_at.desc()),
    )


class ToolCall(Base):
    """Один вызов инструмента внутри прогона: аргументы, результат, длительность."""

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    # У каждого инструмента своя форма аргументов и результата — колонками не описать,
    # а искать по ним нужно: JSONB это умеет (при необходимости плюс GIN-индекс).
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="ok")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempt: Mapped[int] = mapped_column(Integer, default=1)  # номер попытки при ретраях
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[AgentRun] = relationship(back_populates="tool_calls", lazy="raise")

    __table_args__ = (
        CheckConstraint("status IN ('ok', 'error', 'rejected')", name="status_valid"),
    )
