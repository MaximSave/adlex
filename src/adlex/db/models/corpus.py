import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adlex.db.base import Base

# Размерность эмбеддинга задана моделью intfloat/multilingual-e5-base (лаба 4).
# Числом в колонке, а не настройкой: сменить её можно только миграцией
# с переиндексацией, и схема обязана это фиксировать.
EMBEDDING_DIM = 768


class Document(Base):
    """Нормативный акт целиком: одна редакция одного закона."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    act_code: Mapped[str] = mapped_column(String(64))  # "38-FZ"
    title: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[str] = mapped_column(String(32))  # "ред. от 08.08.2024"
    # Хеш исходного файла. Уникальность = идемпотентность загрузки:
    # повторный ingest того же файла не создаст дубликат корпуса.
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        # Ленивая подгрузка в async — это неявный I/O вне корутины и MissingGreenlet.
        # lazy="raise" превращает её в понятную ошибку на этапе разработки.
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'indexed', 'failed')",
            name="status_valid",
        ),
        # Одна редакция акта заводится один раз.
        UniqueConstraint("act_code", "revision", name="uq_documents_act_code_revision"),
    )


class Chunk(Base):
    """Фрагмент акта с точным адресом цитаты и эмбеддингом."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)  # порядок внутри документа
    citation: Mapped[str] = mapped_column(String(128))  # "38-ФЗ, ст. 28, ч. 3"
    text: Mapped[str] = mapped_column(Text)
    # Структура метаданных у разных актов своя (глава, статья, часть, пункт),
    # поэтому JSONB, а не отдельные колонки.
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))

    document: Mapped[Document] = relationship(back_populates="chunks", lazy="raise")

    __table_args__ = (
        # Полнотекстовый поиск: лексический «рукав» гибридного поиска (лаба 5).
        # literal_column, а не строка "russian": обычная строка становится
        # bind-параметром, а его нельзя подставить в DDL индекса.
        Index(
            "ix_chunks_fts",
            func.to_tsvector(literal_column("'russian'"), text),
            postgresql_using="gin",
        ),
        # Приблизительный поиск ближайших соседей по косинусу — векторный «рукав».
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_id_ordinal"),
    )
