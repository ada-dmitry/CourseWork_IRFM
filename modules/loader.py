from http.client import IncompleteRead
import socket
from urllib.error import URLError
from urllib.request import Request, urlopen
import ssl
import time


def _read_response_bytes(response, chunk_size: int = 64 * 1024, min_partial_bytes: int = 4096) -> bytes:
    """Читает ответ по частям; при таймауте возвращает уже полученные байты, если их достаточно."""
    chunks = []
    total = 0

    while True:
        try:
            chunk = response.read(chunk_size)
        except (TimeoutError, socket.timeout, OSError):
            if total >= min_partial_bytes:
                return b"".join(chunks)
            raise

        if not chunk:
            break

        chunks.append(chunk)
        total += len(chunk)

    return b"".join(chunks)

def download_html(url: str, retries: int = 5, timeout: float = 40.0) -> str:
    """Загружает HTML с повторными попытками при временных сетевых ошибках."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "identity",
            "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
            "Connection": "close",
        },
    )
    last_error = None

    for attempt in range(retries):
        try:
            with urlopen(req, context=ctx, timeout=timeout) as response:
                raw = _read_response_bytes(response)
                return raw.decode("utf-8", errors="ignore")
        except IncompleteRead as exc:
            if exc.partial:
                return exc.partial.decode("utf-8", errors="ignore")
            last_error = exc
        except (TimeoutError, socket.timeout, URLError, OSError) as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(0.5 * (2 ** attempt))

    raise RuntimeError(f"Failed to download URL after {retries} attempts: {url}") from last_error