"""Реэкспорт всех моделей.

Alembic сравнивает базу с `Base.metadata`, а таблица попадает в metadata только
при импорте её модуля. Поэтому импорт всех моделей собран здесь, и env.py
достаточно импортировать один этот пакет — иначе автогенерация молча
предложит удалить «лишние» таблицы.
"""

from adlex.db.base import Base
from adlex.db.models.corpus import EMBEDDING_DIM, Chunk, Document
from adlex.db.models.dialog import Conversation, Message
from adlex.db.models.observability import AgentRun, ToolCall

__all__ = [
    "EMBEDDING_DIM",
    "AgentRun",
    "Base",
    "Chunk",
    "Conversation",
    "Document",
    "Message",
    "ToolCall",
]
