import logging
import random
import time
import httpx

from app.core.config import get_settings

logger = logging.getLogger("uniflow.http")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ExternalServiceError(Exception):
    """Erro controlado ao comunicar com APIs externas."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict | None = None,
    json_body: dict | None = None,
    data: dict | None = None,
    max_attempts: int = 3,
    timeout: float | None = None,
) -> httpx.Response:
    """
    Executa requisição HTTP/HTTPS com timeout explícito e retentativa
    com backoff exponencial + jitter para timeouts, HTTP 429 e 5xx.
    """
    settings = get_settings()
    req_timeout = timeout or settings.http_timeout_seconds
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=req_timeout, follow_redirects=False) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    data=data,
                )

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_attempts:
                delay = (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning(
                    "HTTP %s em %s (tentativa %d/%d). Aguardando %.2fs...",
                    response.status_code,
                    url.split("?")[0],
                    attempt,
                    max_attempts,
                    delay,
                )
                time.sleep(delay)
                continue

            return response

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt < max_attempts:
                delay = (2 ** (attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning(
                    "Falha de rede (%s) na tentativa %d/%d. Retentando em %.2fs...",
                    type(exc).__name__,
                    attempt,
                    max_attempts,
                    delay,
                )
                time.sleep(delay)
            else:
                raise ExternalServiceError(
                    f"Falha de rede após {max_attempts} tentativas: {type(exc).__name__}"
                ) from exc

    raise ExternalServiceError(f"Falha inesperada ao consultar serviço externo: {last_error}")
