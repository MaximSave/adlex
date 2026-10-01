"""chunks.embedding допускает NULL: эмбеддинги считаются отдельным этапом.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("chunks", "embedding", nullable=True)


def downgrade() -> None:
    # NOT NULL не вернуть, пока в таблице есть чанки без эмбеддинга.
    # Откат схемы здесь теряет данные: непосчитанные чанки удаляются.
    op.execute("DELETE FROM chunks WHERE embedding IS NULL")
    op.alter_column("chunks", "embedding", nullable=False)
