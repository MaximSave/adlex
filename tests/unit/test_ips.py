from adlex.rag.ips import ips_html_to_text
from adlex.rag.parse import normalize, parse_law

# Разметка как на страницах ИПС: надстрочный номер — span.W9, пометки — span.mark.
IPS_SAMPLE = """
<html><head><style>.W9{vertical-align:super}</style></head><body>
<p class="H">Статья 18<span class="W9" style="">1</span>. Реклама в сети "Интернет"</p>
<p>1.&nbsp;Реклама в сети подлежит маркировке. <span class="mark">(Дополнение частью&nbsp;-
Федеральный закон от&nbsp;02.07.2021&nbsp;№&nbsp;347-ФЗ)</span></p>
<p>2<span class="W9">1</span>.&nbsp;Часть 1<span class="W9">1</span> — для всех.</p>
<p>3. <span class="mark">(Часть утратила силу - Федеральный закон от 21.07.2014 № 264-ФЗ)</span></p>
</body></html>
"""


def test_superscript_becomes_dotted_number() -> None:
    text = normalize(ips_html_to_text(IPS_SAMPLE))
    assert 'Статья 18.1. Реклама в сети "Интернет"' in text
    assert "2.1. Часть 1.1 — для всех." in text


def test_editorial_marks_dropped_but_repeal_kept() -> None:
    text = normalize(ips_html_to_text(IPS_SAMPLE))
    assert "Дополнение" not in text
    assert "3. (Часть утратила силу" in text  # по этой пометке парсер выкинет часть


def test_ips_html_through_parser() -> None:
    fragments = parse_law(ips_html_to_text(IPS_SAMPLE), cite_as="38-ФЗ")
    assert [f.citation for f in fragments] == ["38-ФЗ, ст. 18.1, ч. 1", "38-ФЗ, ст. 18.1, ч. 2.1"]
