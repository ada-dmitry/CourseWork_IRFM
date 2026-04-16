import ssl
import subprocess
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen


HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
}


def download_with_curl(url: str, timeout: float) -> str:
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
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    request = Request(url, headers=HEADERS)
    with urlopen(request, context=context, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def download_html(url: str, retries: int = 3, timeout: float = 30.0) -> str:
    """Загружает HTML. Для ConsultantPlus сначала пробует curl, для остальных сайтов urllib."""
    is_consultant = urlparse(url).netloc.endswith("consultant.ru")
    loaders = [download_with_curl, download_with_urllib] if is_consultant else [download_with_urllib, download_with_curl]
    last_error = None

    for _ in range(retries):
        for loader in loaders:
            try:
                return loader(url, timeout)
            except Exception as exc:
                last_error = exc

        time.sleep(0.5)

    raise RuntimeError(f"Failed to download URL: {url}") from last_error
