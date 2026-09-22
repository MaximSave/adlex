"""Доступ к корпусу. Весь SQL живёт здесь, а не в роутерах и не в узлах агента.

Так запросы можно протестировать отдельно (лаба 13), а поменять способ хранения —
не трогая HTTP-контур.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adlex.db.models import Chunk, Document


async def get_document_by_checksum(session: AsyncSession, checksum: str) -> Document | None:
    """Ключевой запрос идемпотентной загрузки: этот файл уже проиндексирован?"""
    result = await session.execute(select(Document).where(Document.checksum == checksum))
    return result.scalar_one_or_none()


async def create_document(session: AsyncSession, document: Document) -> Document:
    session.add(document)
    # flush, а не commit: id генерируется приложением, но строка должна попасть
    # в транзакцию до вставки чанков. Коммитит тот, кто владеет транзакцией.
    await session.flush()
    return document


async def add_chunks(session: AsyncSession, chunks: Sequence[Chunk]) -> int:
    session.add_all(chunks)
    await session.flush()
    return len(chunks)


async def get_chunks_by_document(session: AsyncSession, document_id: uuid.UUID) -> Sequence[Chunk]:
    result = await session.execute(
        select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.ordinal)
    )
    return result.scalars().all()


async def count_chunks(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(Chunk))
    return result.scalar_one()
