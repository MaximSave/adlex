"""Разбор текста нормативного акта на структурные фрагменты.

Никакого I/O: на вход строка, на выход список фрагментов. Поэтому парсер
тестируется на кусках текста без файлов и без базы.
"""

import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any

CHAPTER_RE = re.compile(r"^Глава\s+(?P<num>\d+(?:\.\d+)*)\.\s*(?P<title>.*)$")
# Номера со вставками: «Статья 14.3.1», «5.1.» — поэтому (?:\.\d+)*, а не одна точка.
ARTICLE_RE = re.compile(r"^Статья\s+(?P<num>\d+(?:\.\d+)*)\.\s*(?P<title>.*)$")
# Часть: «5.1. Текст с заглавной». Пункт внутри части — «1) текст», со скобкой.
PART_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.\s+(?P<rest>[А-ЯЁA-Z«(].*)$")
POINT_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\)\s")
NOTE_RE = re.compile(r"^Примечани[ея]\.?\s*(?P<rest>.*)$")
END_RE = re.compile(r"^Президент\s+Российской\s+Федерации")
# «Утратила силу», «(Утратил силу - …)», «(Часть утратила силу - …)», «(Статья утратила силу …)»
REPEALED_RE = re.compile(
    r"^\(?\s*(?:(?:Часть|Пункт|Подпункт|Статья|Абзац)\s+)?утратил[аио]?\s+силу", re.IGNORECASE
)

# Редакционные пометки: «(в ред. Федерального закона …)», «(В редакции …)»,
# «(часть 5.1 введена …)», «(Пункт дополнен - …)». В норму они не входят.
# «(Утратила силу - …)» здесь намеренно нет: по нему парсер выкидывает норму целиком.
EDITORIAL_RE = re.compile(
    r"\s*\((?=[^()]*(?:Федеральн|закон))(?:[^()]*?)"
    r"(?:ред\.|редакции|введен|дополнен|изменен)[^()]*\)",
    re.IGNORECASE,
)


# Невидимые символы из HTML: особые пробелы → обычный пробел, остальное — удалить.
INVISIBLE = str.maketrans(
    {
        "\u00a0": " ",  # неразрывный пробел (&nbsp;)
        "\u202f": " ",  # узкий неразрывный пробел
        "\u2009": " ",  # тонкий пробел
        "\u00ad": None,  # мягкий перенос
        "\u200b": None,  # пробел нулевой ширины
        "\ufeff": None,  # BOM
    }
)


def normalize(text: str) -> str:
    """Единый вид текста до регулярок: без невидимых символов и лишних пробелов.

    NFC, а не NFKC: NFKC заодно превращает «№» в «No», а надстрочную «¹» в «1»,
    то есть портит сам текст закона.
    """
    text = unicodedata.normalize("NFC", text).translate(INVISIBLE)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(lines)


def clean_lines(text: str) -> list[str]:
    """Непустые строки без служебного текста КонсультантПлюс и ИПС."""
    result: list[str] = []
    in_note_block = False
    for line in text.split("\n"):
        if not line:
            in_note_block = False  # блок примечания Консультанта кончается пустой строкой
            continue
        if line.startswith("КонсультантПлюс: примечание"):
            in_note_block = True
        if in_note_block or ">>>" in line:
            continue
        line = EDITORIAL_RE.sub("", line).strip()
        if line:
            result.append(line)
    return result


def _span(first: str, last: str) -> str:
    return first if first == last else f"{first}–{last}"


@dataclass(slots=True)
class Fragment:
    """Кусок акта с точным адресом. Адрес собирается без LLM, детерминированно."""

    cite_as: str  # «38-ФЗ», «КоАП РФ», «Письмо ФАС России от … № …»
    article: str | None = None
    article_title: str = ""
    chapter: str | None = None
    parts: tuple[str, str] | None = None  # (первая, последняя) — после склейки их несколько
    points: tuple[str, str] | None = None
    paras: tuple[int, int] | None = None  # абзацы — для писем, у которых нет статей
    note: bool = False  # примечание к статье
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def citation(self) -> str:
        pieces = [self.cite_as]
        if self.article:
            pieces.append(f"ст. {self.article}")
        if self.parts:
            pieces.append(f"ч. {_span(*self.parts)}")
        if self.note:
            pieces.append("прим.")
        if self.points:
            pieces.append(f"п. {_span(*self.points)}")
        if self.paras:
            pieces.append(f"абз. {_span(str(self.paras[0]), str(self.paras[1]))}")
        return ", ".join(pieces)

    @property
    def embed_text(self) -> str:
        """Текст для эмбеддинга: заголовок даёт фрагменту тематический якорь."""
        if self.article:
            head = f"{self.cite_as}. Статья {self.article}. {self.article_title}".rstrip(". ")
            return f"{head}.\n{self.text}"
        return f"{self.cite_as}.\n{self.text}"

    @property
    def meta(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "article": self.article,
            "article_title": self.article_title,
            "parts": list(self.parts) if self.parts else None,
            "points": list(self.points) if self.points else None,
            "paras": list(self.paras) if self.paras else None,
            "note": self.note,
        }


def parse_law(raw: str, cite_as: str) -> list[Fragment]:
    """Закон или кодекс: глава → статья → часть. Один фрагмент на часть статьи."""
    fragments: list[Fragment] = []
    chapter: str | None = None
    article: Fragment | None = None  # шаблон текущей статьи: номер, название, глава
    current: Fragment | None = None
    skip_article = False

    def flush() -> None:
        # Пустая часть — это часть, от которой после чистки ничего не осталось
        # (например, «4. (Утратила силу - …)»). Утратившие силу нормы не индексируем.
        if current and current.lines and not REPEALED_RE.match(current.lines[0]):
            fragments.append(current)

    for line in clean_lines(normalize(raw)):
        if END_RE.match(line):
            break
        if m := CHAPTER_RE.match(line):
            flush()
            current, article = None, None
            chapter = m["num"]
            continue
        if m := ARTICLE_RE.match(line):
            flush()
            title = m["title"].strip()
            skip_article = not title or bool(REPEALED_RE.match(title))
            article = Fragment(cite_as, article=m["num"], article_title=title, chapter=chapter)
            current = replace(article, lines=[])  # преамбула статьи до первой части
            continue
        if article is None or skip_article:
            continue  # шапка закона до первой статьи или утратившая силу статья
        if m := PART_RE.match(line):
            flush()
            current = replace(article, parts=(m["num"], m["num"]), lines=[m["rest"]])
            continue
        if m := NOTE_RE.match(line):
            flush()
            current = replace(article, note=True, lines=[m["rest"]] if m["rest"] else [])
            continue
        if (pm := POINT_RE.match(line)) and REPEALED_RE.match(line[pm.end() :]):
            continue  # «3) утратил силу. - …»
        if current is not None:
            current.lines.append(line)
    flush()
    return fragments


def parse_letter(raw: str, cite_as: str) -> list[Fragment]:
    """Письмо или разъяснение без статей: один фрагмент на абзац, склейка — в chunk.py."""
    return [
        Fragment(cite_as, paras=(i, i), lines=[line])
        for i, line in enumerate(clean_lines(normalize(raw)), start=1)
    ]
