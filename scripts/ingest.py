"""Загрузка корпуса: манифест → парсинг → чанки → таблицы documents и chunks.

Запуск из корня репозитория (оттуда читается .env):
    uv run python scripts/ingest.py --dry-run --sample 5   # только разобрать и показать
    uv run python scripts/ingest.py                        # записать в базу

Эмбеддинги здесь не считаются — это отдельный этап (лаба 4). Поэтому документ
остаётся в статусе pending, а chunks.embedding — NULL.
"""

import argparse
import asyncio
import hashlib
import statistics
from datetime import date
from pathlib import Path
from typing import Literal

import structlog
import yaml
from pydantic import BaseModel, Field

from adlex.config import get_settings
from adlex.db.models import Chunk, Document
from adlex.db.repositories import corpus as repo
from adlex.db.session import create_engine, create_session_factory, session_scope
from adlex.logging import setup_logging
from adlex.rag.chunk import merge_small
from adlex.rag.ips import ips_html_to_text
from adlex.rag.parse import Fragment, normalize, parse_law, parse_letter

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "corpus" / "manifest" / "manifest.yaml"
RAW_DIR = ROOT / "corpus" / "raw"

log = structlog.get_logger()


class ManifestEntry(BaseModel):
    act_code: str  # ключ в базе, латиницей: 38-FZ
    cite_as: str  # как акт выглядит в цитате: 38-ФЗ
    title: str
    kind: Literal["law", "letter"]  # закон режем по статьям, письмо — по абзацам
    file: str
    revision: str = Field(max_length=32)
    source_url: str
    fetched_at: date
    excerpt: str | None = None  # если взят не весь акт: «только ст. 14.3, 14.3.1»


def load_manifest(path: Path) -> list[ManifestEntry]:
    items = yaml.safe_load(path.read_text(encoding="utf-8")) or []  # пустой файл — None
    return [ManifestEntry.model_validate(item) for item in items]


def read_source(path: Path) -> str:
    """Текст акта из файла: HTML из ИПС конвертируется, .txt читается как есть."""
    # utf-8-sig: Блокнот и часть редакторов на Windows пишут BOM в начало файла.
    raw = path.read_text(encoding="utf-8-sig")
    return ips_html_to_text(raw) if path.suffix == ".html" else raw


def build_chunks(entry: ManifestEntry, text: str) -> list[Fragment]:
    parse = parse_law if entry.kind == "law" else parse_letter
    chunks = merge_small(parse(text, entry.cite_as))
    if not chunks:
        # Пустой результат — почти всегда не тот kind или файл не в той кодировке.
        raise ValueError(f"{entry.file}: парсер не нашёл ни одного фрагмента")
    return chunks


def log_stats(entry: ManifestEntry, chunks: list[Fragment]) -> None:
    lengths = sorted(len(c.text) for c in chunks)
    log.info(
        "parsed",
        act=entry.act_code,
        articles=len({c.article for c in chunks if c.article}),
        chunks=len(chunks),
        len_min=lengths[0],
        len_median=int(statistics.median(lengths)),
        len_max=lengths[-1],
    )


def print_sample(chunks: list[Fragment], n: int) -> None:
    """Равномерная выборка, а не случайная: повторный запуск покажет те же чанки."""
    step = max(1, len(chunks) // n)
    for chunk in chunks[::step][:n]:
        print(f"\n=== {chunk.citation} ({len(chunk.text)} симв.)\n{chunk.embed_text}")


async def main(dry_run: bool, sample: int) -> None:
    settings = get_settings()
    setup_logging(settings.env)

    prepared: list[tuple[ManifestEntry, str, list[Fragment]]] = []
    for entry in load_manifest(MANIFEST):
        text = read_source(RAW_DIR / entry.file)
        chunks = build_chunks(entry, text)
        log_stats(entry, chunks)
        if sample:
            print_sample(chunks, sample)
        prepared.append((entry, text, chunks))
    log.info("corpus", documents=len(prepared), chunks=sum(len(c) for _, _, c in prepared))
    if dry_run:
        return

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        for entry, text, chunks in prepared:
            # Контрольная сумма нормализованного текста, а не байтов файла:
            # CRLF, BOM и неразрывные пробелы не должны делать «новую» редакцию.
            checksum = hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()
            # Одна транзакция на документ: упал разбор пятого акта —
            # первые четыре остаются в базе целиком, а пятый не остаётся наполовину.
            async with session_scope(session_factory) as session:
                if await repo.get_document_by_checksum(session, checksum):
                    log.info("unchanged", act=entry.act_code)
                    continue
                replaced = await repo.delete_document(session, entry.act_code, entry.revision)
                document = await repo.create_document(
                    session,
                    Document(
                        act_code=entry.act_code,
                        title=entry.title,
                        source_url=entry.source_url,
                        revision=entry.revision,
                        checksum=checksum,
                        status="pending",
                    ),
                )
                await repo.add_chunks(
                    session,
                    [
                        Chunk(
                            document_id=document.id,
                            ordinal=i,
                            citation=c.citation,
                            # В базу — текст вместе с заголовком статьи: и полнотекстовый,
                            # и векторный поиск (лабы 4–5) должны видеть один и тот же текст.
                            text=c.embed_text,
                            meta=c.meta,
                        )
                        for i, c in enumerate(chunks)
                    ],
                )
            log.info("ingested", act=entry.act_code, chunks=len(chunks), replaced=replaced)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Загрузка корпуса нормативки в базу")
    parser.add_argument("--dry-run", action="store_true", help="только разобрать, без базы")
    parser.add_argument("--sample", type=int, default=0, help="показать N чанков на акт")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.sample))
