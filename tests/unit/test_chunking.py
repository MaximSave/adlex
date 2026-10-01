from itertools import groupby
from pathlib import Path

import pytest

from adlex.rag.chunk import merge_small, split_long
from adlex.rag.parse import Fragment, normalize, parse_law, parse_letter

FIXTURE = Path(__file__).parent.parent / "fixtures" / "law_sample.txt"


@pytest.fixture
def fragments() -> list[Fragment]:
    return parse_law(FIXTURE.read_text(encoding="utf-8"), cite_as="38-ФЗ")


def test_articles_found_and_repealed_dropped(fragments: list[Fragment]) -> None:
    assert [a for a, _ in groupby(f.article for f in fragments)] == ["5", "14.3.1", "28"]


def test_citations(fragments: list[Fragment]) -> None:
    citations = [f.citation for f in fragments]
    assert citations == [
        "38-ФЗ, ст. 5, ч. 1",
        "38-ФЗ, ст. 5, ч. 2",
        "38-ФЗ, ст. 5, ч. 3",
        "38-ФЗ, ст. 5, ч. 5.1",  # вставная часть не приклеилась к соседней
        "38-ФЗ, ст. 14.3.1",
        "38-ФЗ, ст. 28, ч. 1",
        "38-ФЗ, ст. 28, ч. 3",
        "38-ФЗ, ст. 28, прим.",
    ]


def test_points_stay_inside_part(fragments: list[Fragment]) -> None:
    part2 = fragments[1]
    assert part2.lines[0].startswith("Недобросовестной признается")
    assert part2.lines[1].startswith("1) содержит")
    assert part2.lines[2].startswith("2) порочит")
    assert "утратил" not in part2.text  # утративший силу пункт выкинут


def test_service_text_removed(fragments: list[Fragment]) -> None:
    text = "\n".join(f.text for f in fragments)
    for noise in ("в ред.", "введена", "КонсультантПлюс", ">>>", "Путин", "Утратила"):
        assert noise not in text


def test_normalize_invisible_characters() -> None:
    assert normalize("Статья\u00a05. Ре\u00adклама ") == "Статья 5. Реклама"


def test_normalize_keeps_law_text() -> None:
    # NFKC превратил бы «№» в «No», а «¹» в «1»
    assert normalize("от 13.03.2006 № 38-ФЗ, ст. 18¹") == "от 13.03.2006 № 38-ФЗ, ст. 18¹"


@pytest.mark.parametrize(
    "line",
    [
        "4. (Утратила силу - Федеральный закон от 28.07.2012 N 133-ФЗ)",
        "4. Утратил силу. - Федеральный закон от 28.07.2012 N 133-ФЗ.",
        "4. (Часть утратила силу - Федеральный закон от 27.10.2008 № 179-ФЗ)",
    ],
)
def test_repealed_part_formats(line: str) -> None:
    text = f"Статья 7. Проверка\n1. Действующая часть.\n{line}"
    assert [f.citation for f in parse_law(text, "38-ФЗ")] == ["38-ФЗ, ст. 7, ч. 1"]


def test_merge_never_crosses_article(fragments: list[Fragment]) -> None:
    chunks = merge_small(fragments, min_chars=200, max_chars=1800)

    def by_article(items: list[Fragment]) -> dict[str | None, str]:
        return {a: "\n".join(f.text for f in g) for a, g in groupby(items, lambda f: f.article)}

    # склейка меняет нарезку, но не состав статей
    assert by_article(chunks) == by_article(fragments)
    assert chunks[0].citation == "38-ФЗ, ст. 5, ч. 1–3"  # короткие части склеились


def test_split_long_keeps_lead_and_points() -> None:
    lead = "В рекламе не допускается:"
    points = [f"{i}) пункт номер {i} " + "текст " * 15 for i in range(1, 31)]
    part = Fragment("38-ФЗ", article="5", parts=("4", "4"), lines=[lead, *points])

    pieces = split_long(part, max_chars=800)

    assert len(pieces) > 1
    assert all(len(p.text) <= 800 for p in pieces)
    assert all(p.lines[0] == lead for p in pieces)
    assert pieces[0].citation.startswith("38-ФЗ, ст. 5, ч. 4, п. 1–")
    assert sum(len(p.lines) - 1 for p in pieces) == 30  # ни один пункт не потерян


def test_letter_paragraphs_merge() -> None:
    letter = "ФАС России разъясняет.\n\nПервый абзац.\nВторой абзац."
    chunks = merge_small(parse_letter(letter, cite_as="Письмо ФАС"))
    assert [c.citation for c in chunks] == ["Письмо ФАС, абз. 1–3"]
