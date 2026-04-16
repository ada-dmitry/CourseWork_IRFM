from urllib.parse import urljoin, urldefrag
from lxml import html

from modules.loader import download_html

def normalize_url(base_url: str, href: str) -> str:
    full = urljoin(base_url, href)
    full, _ = urldefrag(full)
    return full

def extract_links(page_html: str, base_url: str) -> list[str]:
    """
    Извлекает все уникальные ссылки из HTML-страницы.
    :param page_html: HTML-код страницы
    :param base_url: Базовый URL для нормализации ссылок
    :return: Список уникальных нормализованных ссылок
    """
    tree = html.fromstring(page_html)
    links = []

    for a in tree.xpath("//a[@href]"):
        href = a.attrib["href"].strip()
        full_url = normalize_url(base_url, href)
        links.append(full_url)

    return list(dict.fromkeys(links))


def is_terminal_page(page_html: str, url: str) -> bool:
    tree = html.fromstring(page_html)
    links = tree.xpath("//a[contains(text(), 'УК РФ Статья')]")
    return len(links) == 0

def extract_page_text(page_html: str, url: str) -> str:
    tree = html.fromstring(page_html)
    text = tree.text_content()
    return text.strip()

def crawl_document(start_url, is_terminal_page=is_terminal_page, extract_document_links=extract_links, extract_page_text=extract_page_text):
    visited = set()
    pages = []

    def dfs(url):
        if url in visited:
            return
        visited.add(url)

        try:
            page_html = download_html(url)
        except RuntimeError as exc:
            print(f"[crawler] skip unreachable page: {url} ({exc})")
            return

        if is_terminal_page(page_html, url):
            text = extract_page_text(page_html, url)
            pages.append({"url": url, "text": text})
            return

        child_links = extract_document_links(page_html, url)
        for link in child_links:
            dfs(link)

    dfs(start_url)
    return pages