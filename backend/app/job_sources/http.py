"""Polite JSON HTTP client for public job APIs (no scraping)."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Protocol


class JsonClient(Protocol):
    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any: ...


class SourceUnavailable(RuntimeError):
    """The source could not be read; the import skips it and reports the reason."""


class HttpJsonClient:
    """GET JSON with a minimum interval per host, bounded retries and Retry-After support."""

    def __init__(self, user_agent: str, min_interval: float = 1.5, timeout: float = 60,
                 max_attempts: int = 4, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.clock = clock
        self._last_request: dict[str, float] = {}

    def _wait_for(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.min_interval - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request[host] = self.clock()

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        host = urllib.parse.urlsplit(url).netloc
        for attempt in range(1, self.max_attempts + 1):
            self._wait_for(host)
            request = urllib.request.Request(url, headers={"User-Agent": self.user_agent,
                                                           "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise SourceUnavailable(f"HTTP 404 for {host}") from error
                if error.code not in {429, 500, 502, 503, 504} or attempt == self.max_attempts:
                    raise SourceUnavailable(f"HTTP {error.code} for {host}") from error
                retry_after = error.headers.get("Retry-After") if error.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 ** attempt
                self.sleep(min(delay, 120.0))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                if attempt == self.max_attempts:
                    raise SourceUnavailable(f"{type(error).__name__} for {host}") from error
                self.sleep(2.0 ** attempt)
        raise SourceUnavailable(f"No response from {host}")
