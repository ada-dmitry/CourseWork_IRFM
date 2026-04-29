import re
import time
from urllib.parse import urljoin, urldefrag, urlparse

from lxml import html

from modules.loader import download_html


START_URL = "https://www.consultant.ru/document/cons_doc_LAW_10699/" # Базовый адрес УК РФ (откуда мы начинаем обход)
FIRST_ARTICLE_URL = START_URL + "e8ecf933c52a85d9223094e0e7fbf52f0128d399/" # Первая статья (для детерминированности обхода)

ARTICLE_RE = re.compile(r"^\s*(?:УК РФ,?\s+)?Статья\s+\d+(?:\.\d+)?\.", re.IGNORECASE) 
STRUCTURE_PREFIX_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[а-яё])[\.)]\s+", re.IGNORECASE) # Строки, начинающиеся с нумерованного или буквенного маркера списка.
SPACE_RE = re.compile(r"[ \t\r\f\v]+")


def normalize_url(base_url: str, href: str) -> str:
    """
    Преобразует относительный href в абсолютный URL и отрезает фрагмент (#...).
    """
    url = urljoin(base_url, href)
    url, _ = urldefrag(url)
    return url


def document_prefix(url: str) -> str:
    """
    Возвращает двухуровневый префикс пути URL — например /document/cons_doc_LAW_10699/.

    Используется для проверки, что ссылка ведёт в тот же документ.
    """
    parts = [part for part in urlparse(url).path.split("/") if part]
    return f"/{parts[0]}/{parts[1]}/"


def is_same_document(url: str, prefix: str) -> bool:
    """
    Проверяет, что URL принадлежит тому же документу на consultant.ru.
    """
    parsed = urlparse(url)
    return parsed.netloc in {"", "consultant.ru", "www.consultant.ru"} and parsed.path.startswith(prefix)


def download_document_page(url: str, allow_partial: bool = False) -> str:
    """
    Загружает страницу документа, повторяя запрос с возрастающими таймаутами (8, 30, 30 с).

    По умолчанию считает страницу полной только если HTML заканчивается тегом </html>.
    allow_partial=True отключает эту проверку (нужно для индексной страницы, которая может
    грузиться медленно). Между попытками — пауза 0.5 с.
    """
    last_html = ""

    for timeout in (8, 15, 30):
        try:
            page_html = download_html(url, retries=1, timeout=timeout)
        except RuntimeError:
            time.sleep(0.5)
            continue

        if allow_partial or "</html>" in page_html[-100:].lower():
            return page_html

        last_html = page_html
        time.sleep(0.5)

    if last_html:
        return last_html

    raise RuntimeError(f"Failed to download page: {url}")


def clean_text(text: str) -> str:
    """
    Нормализует пробелы и срезает нумерационные префиксы вида «1. », «а) », «2.1 ».
    """
    text = text.replace("\xa0", " ")
    text = SPACE_RE.sub(" ", text)
    text = STRUCTURE_PREFIX_RE.sub("", text)
    return text.strip()


def main_content(tree):
    """
    Возвращает корневой div.document-page__content или None, если он не найден.
    """
    nodes = tree.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' document-page__content ')]")
    return nodes[0] if nodes else None


def article_title(tree) -> str:
    """
    Извлекает заголовок статьи: сначала ищет <h1>, fallback — первый div.doc-style.
    """
    content = main_content(tree)
    if content is None:
        return ""

    h1 = content.xpath(".//h1")
    if h1:
        text = clean_text(h1[0].text_content())
        if text:
            return text

    styles = content.xpath(".//div[contains(concat(' ', normalize-space(@class), ' '), ' doc-style ')]")
    return clean_text(styles[0].text_content()) if styles else ""


def service_line(line: str) -> bool:
    """
    Возвращает True для редакционных пометок и реквизитов, которые не нужны в тексте.

    Фильтрует: пометки «(в ред. ФЗ ...)», «(введён ...)», «(см. текст ...)»,
    подпись президента, дату подписания и номер закона вида «N 63-ФЗ».
    """
    low = line.lower()

    if low.startswith("(см. текст") or low.startswith("(в ред.") or low.startswith("(введен"):
        return True
    if low.startswith("(част") and ("в ред." in low or "введен" in low):
        return True
    if "федеральн" in low and any(word in low for word in ("ред.", "введен", "утратил")):
        return True
    if low in {"президент", "российской федерации", "б.ельцин", "москва, кремль"}:
        return True
    if re.fullmatch(r"\d{1,2}\s+[а-яё]+\s+\d{4}\s+года", low):
        return True
    if re.fullmatch(r"n\s+\d+\s*-\s*фз", low):
        return True

    return False


def extract_page_text(tree) -> str:
    """
    Извлекает смысловой текст статьи из HTML-дерева.

    Перед сбором абзацев удаляет из дерева заголовок (h1), блоки doc-style,
    doc-insert и doc-roll (вставки, примечания, раскрывающиеся блоки), чтобы
    их текст не попал в результат. Затем собирает все <p>, фильтрует служебные
    строки через service_line() и возвращает текст через \n.
    """
    content = main_content(tree)
    if content is None:
        return ""

    for node in content.xpath(
        ".//h1"
        " | .//div[contains(concat(' ', normalize-space(@class), ' '), ' doc-style ')]"
        " | .//div[contains(concat(' ', normalize-space(@class), ' '), ' doc-insert ')]"
        " | .//div[contains(concat(' ', normalize-space(@class), ' '), ' doc-roll ')]"
    ):
        node.getparent().remove(node)

    lines = []
    for p in content.xpath(".//p"):
        line = clean_text(p.text_content())
        if line and not service_line(line):
            lines.append(line)

    return "\n".join(lines)


def extract_article_urls(tree, base_url: str) -> list[str]:
    """
    Собирает ссылки на статьи со страницы — те, чей текст совпадает с ARTICLE_RE.

    Возвращает список уникальных URL в порядке появления на странице.
    Внешние ссылки (не на тот же документ) отбрасываются.
    """
    prefix = document_prefix(base_url)
    result = []

    for link in tree.xpath("//a[@href]"):
        text = clean_text(link.text_content())
        url = normalize_url(base_url, link.attrib["href"])
        if ARTICLE_RE.match(text) and is_same_document(url, prefix) and url not in result:
            result.append(url)

    return result


def extract_next_document_url(tree, base_url: str) -> str | None:
    """
    Возвращает URL следующей страницы через кнопку-стрелку pages__right, или None.
    """
    prefix = document_prefix(base_url)
    links = tree.xpath("//a[contains(concat(' ', normalize-space(@class), ' '), ' pages__right ')][@href]")
    if not links:
        return None

    url = normalize_url(base_url, links[0].attrib["href"])
    return url if is_same_document(url, prefix) else None


def next_known_article(current_url: str, known_urls: list[str], visited: set[str]) -> str | None:
    """
    Находит следующую непосещённую статью из known_urls после current_url.

    Используется как fallback, когда страница не содержит кнопки pages__right —
    например, когда статья занимает ровно одну страницу и стрелки нет.
    """
    if current_url not in known_urls:
        return None

    current_index = known_urls.index(current_url)
    for url in known_urls[current_index + 1:]:
        if url not in visited:
            return url

    return None


def add_known_urls(known_urls: list[str], urls: list[str]) -> None:
    """
    Добавляет новые URL в known_urls, не нарушая порядок и без дублей."""
    for url in urls:
        if url not in known_urls:
            known_urls.append(url)


def crawl_document(start_url: str = START_URL, max_pages: int = 800) -> list[dict]:
    """
    Обходит документ УК РФ и возвращает список статей.

    Алгоритм:
    1. Загружает индексную страницу и собирает ссылки на все статьи (known_urls).
    2. Начинает с первой статьи и идёт по ним в порядке оглавления.
    3. На каждой странице:
       - добавляет найденные ссылки на статьи в known_urls;
       - если заголовок — статья, сохраняет текст;
       - переходит на следующую страницу через pages__right или next_known_article().
    4. Останавливается на «Статья 361.» (последняя статья УК), по лимиту max_pages
       или если следующий URL недоступен.

    Возвращает list[dict] с ключами: url, title, text.
    """
    pages = []
    visited = set()
    known_urls = []

    try:
        start_html = download_document_page(start_url, allow_partial=True)
        add_known_urls(known_urls, extract_article_urls(html.fromstring(start_html), start_url))
        current_url = known_urls[0] if known_urls else FIRST_ARTICLE_URL
    except RuntimeError as exc:
        print(f"[crawler] start page is unavailable: {exc}")
        current_url = FIRST_ARTICLE_URL
        add_known_urls(known_urls, [FIRST_ARTICLE_URL])

    while current_url and current_url not in visited and len(visited) < max_pages:
        visited.add(current_url)

        try:
            page_html = download_document_page(current_url)
        except RuntimeError as exc:
            print(f"[crawler] skip page {current_url}: {exc}")
            break

        tree = html.fromstring(page_html)
        title = article_title(tree)
        article_urls = extract_article_urls(tree, current_url)
        next_url = extract_next_document_url(tree, current_url)

        add_known_urls(known_urls, article_urls)

        if ARTICLE_RE.match(title):
            text = extract_page_text(tree)
            if text:
                pages.append({"url": current_url, "title": title, "text": text})

        if "Статья 361." in title:
            break

        if next_url is None:
            next_url = next_known_article(current_url, known_urls, visited)
        current_url = next_url

    return pages
