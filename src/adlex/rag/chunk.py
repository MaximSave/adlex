"""Нарезка фрагментов на чанки: короткие склеиваем, длинные режем.

Граница статьи не пересекается никогда: цитата «ст. 5, ч. 3–4» проверяема,
а «ст. 5–6» — уже нет.
"""

import re
from dataclasses import replace

from adlex.rag.parse import POINT_RE, Fragment

SENTENCE_RE = re.compile(r"(?<=[.;:!?])\s+(?=[А-ЯЁA-Z«(\d])")


def split_long(fragment: Fragment, max_chars: int = 1800) -> list[Fragment]:
    """Длинная часть режется по пунктам, а пункт-великан — по предложениям.

    Вводная строка части («В рекламе не допускается:») повторяется в каждом
    куске: без неё пункт «3) …» теряет смысл.
    """
    if len(fragment.text) <= max_chars:
        return [fragment]

    first_point = next((i for i, ln in enumerate(fragment.lines) if POINT_RE.match(ln)), None)
    if first_point is None:
        lead, units = [], _sentence_windows(fragment.text, max_chars)
    else:
        lead, units = fragment.lines[:first_point], fragment.lines[first_point:]
    lead_len = sum(len(x) + 1 for x in lead)

    pieces: list[Fragment] = []
    group: list[str] = []
    for unit in units:
        if group and lead_len + sum(len(x) + 1 for x in group) + len(unit) > max_chars:
            pieces.append(_piece(fragment, lead, group))
            group = []
        group.append(unit)
    if group:
        pieces.append(_piece(fragment, lead, group))
    return pieces


def _sentence_windows(text: str, max_chars: int) -> list[str]:
    """Окна из предложений с перекрытием в одно предложение."""
    sentences = SENTENCE_RE.split(text.replace("\n", " "))
    windows: list[str] = []
    window: list[str] = []
    for sentence in sentences:
        if window and len(" ".join([*window, sentence])) > max_chars:
            windows.append(" ".join(window))
            window = [window[-1]]  # перекрытие: последнее предложение переходит дальше
        window.append(sentence)
    windows.append(" ".join(window))
    return windows


def _piece(fragment: Fragment, lead: list[str], group: list[str]) -> Fragment:
    nums = [m["num"] for ln in group if (m := POINT_RE.match(ln))]
    points = (nums[0], nums[-1]) if nums else None
    return replace(fragment, points=points, lines=[*lead, *group])


def _same_scope(a: Fragment, b: Fragment) -> bool:
    """Склеивать можно только соседей внутри одной статьи (или одного письма)."""
    return a.cite_as == b.cite_as and a.article == b.article


def _mergeable(f: Fragment) -> bool:
    # Куски разрезанной части и примечания не склеиваем: их адрес
    # после склейки перестал бы быть осмысленным.
    return f.points is None and not f.note


def _join(a: Fragment, b: Fragment) -> Fragment:
    parts = paras = None
    if a.parts and b.parts:
        parts = (a.parts[0], b.parts[1])
    elif a.parts or b.parts:
        # преамбула статьи + часть 1 — адресуем по части
        parts = a.parts or b.parts
    if a.paras and b.paras:
        paras = (a.paras[0], b.paras[1])
    return replace(a, parts=parts, paras=paras, lines=[*a.lines, *b.lines])


def merge_small(
    fragments: list[Fragment], min_chars: int = 200, max_chars: int = 1800
) -> list[Fragment]:
    """Короткий фрагмент приклеивается к соседу по статье, пока влезает в max_chars."""
    result: list[Fragment] = []
    for fragment in (piece for f in fragments for piece in split_long(f, max_chars)):
        prev = result[-1] if result else None
        if (
            prev is not None
            and min(len(prev.text), len(fragment.text)) < min_chars
            and _same_scope(prev, fragment)
            and _mergeable(prev)
            and _mergeable(fragment)
            and len(prev.text) + len(fragment.text) + 1 <= max_chars
        ):
            result[-1] = _join(prev, fragment)
        else:
            result.append(fragment)
    return result
