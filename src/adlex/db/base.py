from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Шаблоны имён для индексов и ограничений. Без них PostgreSQL придумывает имена сам,
# они отличаются на разных базах, и автогенерация Alembic начинает конфликтовать
# сама с собой: то, что она считает новым ограничением, на деле уже существует.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Общий предок всех моделей: держит единый MetaData, из которого Alembic
    берёт целевую схему при автогенерации миграций."""

    metadata = MetaData(naming_convention=NAMING)
