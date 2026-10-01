"""HTML документа из ИПС «Законодательство России» (pravo.gov.ru) → плоский текст.

Зачем HTML, а не копирование со страницы: вставные статьи и части там набраны
надстрочным номером (18¹, 2¹), и при копировании он превращается в обычную
цифру — «Статья 181», «часть 21». В HTML надстрочный номер размечен классом W9,
и его можно записать через точку, как принято в КонсультантПлюс: «18.1», «2.1».
"""

from html.parser import HTMLParser

SUPERSCRIPT_CLASS = "W9"
# Редакционные пометки «(В редакции …)», «(Дополнение частью - …)» — в классе mark.
EDITORIAL_CLASSES = frozenset({"mark", "markx"})
BLOCK_TAGS = frozenset({"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"})
SKIP_TAGS = frozenset({"script", "style", "head"})


class _IpsTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        # Стек открытых тегов: (тег, класс). По нему видно, внутри чего мы сейчас.
        self.stack: list[tuple[str, str]] = []
        self.editorial: list[str] | None = None  # текст текущей пометки, пока она не закрыта

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in BLOCK_TAGS:
            self._emit("\n")
        if tag == "br":
            return  # у <br> нет закрывающего тега — в стек не кладём
        cls = dict(attrs).get("class") or ""
        self.stack.append((tag, cls))
        if cls in EDITORIAL_CLASSES and self.editorial is None:
            self.editorial = []
        if cls == SUPERSCRIPT_CLASS:
            self._emit(".")

    def handle_endtag(self, tag: str) -> None:
        # Страницы ИПС не всегда закрывают теги аккуратно: снимаем со стека
        # до ближайшего совпадающего, а лишний закрывающий игнорируем.
        if not any(t == tag for t, _ in self.stack):
            return
        while self.stack:
            t, cls = self.stack.pop()
            if cls in EDITORIAL_CLASSES and not self._inside(EDITORIAL_CLASSES):
                self._close_editorial()
            if t == tag:
                break
        if tag in BLOCK_TAGS:
            self._emit("\n")

    def handle_data(self, data: str) -> None:
        if any(t in SKIP_TAGS for t, _ in self.stack):
            return
        self._emit(data)

    def _inside(self, classes: frozenset[str]) -> bool:
        return any(cls in classes for _, cls in self.stack)

    def _emit(self, text: str) -> None:
        if self.editorial is not None:
            self.editorial.append(text)
        else:
            self.out.append(text)

    def _close_editorial(self) -> None:
        text = "".join(self.editorial or [])
        self.editorial = None
        # Пометку выбрасываем, кроме «(Утратила силу - …)»: по ней парсер
        # узнаёт, что норма больше не действует, и не индексирует её.
        if "утратил" in text.lower():
            self.out.append(text)


def ips_html_to_text(html: str) -> str:
    parser = _IpsTextParser()
    parser.feed(html)
    parser.close()
    return "".join(parser.out)
