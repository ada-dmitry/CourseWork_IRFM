import ssl
import subprocess
import time
from urllib.request import Request, urlopen


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
}


def download_with_curl(url: str, timeout: float) -> str:
    """
    Загружает URL через системный curl с поддержкой gzip и редиректов.

    Флаги: -L следует редиректам, --compressed принимает gzip/br,
    --silent подавляет прогресс, --show-error выводит ошибки в stderr.
    Если stdout пуст (curl вернул ошибку), бросает RuntimeError со stderr.
    """
    command = [
        "curl",
        "-L",
        "--compressed",
        "--silent",
        "--show-error",
        "--max-time",
        str(int(timeout)),
        "-A",
        HEADERS["User-Agent"],
        url,
    ]
    result = subprocess.run(command, capture_output=True, check=False)

    if result.stdout:
        return result.stdout.decode("utf-8", errors="ignore")

    message = result.stderr.decode("utf-8", errors="ignore").strip()
    raise RuntimeError(message or f"curl finished with code {result.returncode}")


def download_with_urllib(url: str, timeout: float) -> str:
    """
    Загружает URL через стандартный urllib с отключённой проверкой SSL-сертификата (иначе может лечь).
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    request = Request(url, headers=HEADERS)
    with urlopen(request, context=context, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def download_html(url: str, retries: int = 3, timeout: float = 30.0) -> str:
    """Загружает HTML-страницу с retry-логикой.

    Порядок загрузчиков: curl → urllib (curl обходит часть защит consultant.ru).
    На каждой итерации retry пробует оба; пауза 0.5 с между попытками.
    Если все попытки исчерпаны — бросает RuntimeError с причиной последней ошибки.
    """
    loaders = [download_with_curl, download_with_urllib]
    last_error = None

    for _ in range(retries):
        for loader in loaders:
            try:
                return loader(url, timeout)
            except Exception as exc:
                last_error = exc

        time.sleep(0.5)

    raise RuntimeError(f"Failed to download URL: {url}") from last_error
