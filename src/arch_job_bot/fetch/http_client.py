"""HTTP client with browser TLS impersonation, polite jitter, and backoff.

Israeli boards flag plain-`requests` traffic by its TLS/JA3 + HTTP2 fingerprint;
`curl_cffi` impersonating chrome124 spoofs that and is usually enough at one-user
volume. We keep volume tiny, add random jitter, and back off on 429/403.
"""

from __future__ import annotations

import logging
import random
import time

try:
    from curl_cffi import requests as cffi_requests
except Exception:  # pragma: no cover - import guard for envs without curl_cffi
    cffi_requests = None

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# A 200 whose body is actually a bot-challenge (Cloudflare/Incapsula). Treated as a
# failure so a datacenter-blocked source raises SourceError instead of matching 0 jobs.
_CHALLENGE_MARKERS = (
    "just a moment",
    "performing security verification",
    "challenge-platform",
    "cf-browser-verification",
    "_cf_chl",
    "attention required! | cloudflare",
    "checking your browser before",
    "this website uses a security service to protect",
)


def _is_challenge(text: str) -> bool:
    head = (text or "")[:4000].lower()
    return any(m in head for m in _CHALLENGE_MARKERS)


class HttpClient:
    def __init__(
        self,
        *,
        impersonate: str = "chrome124",
        timeout: float = 25.0,
        min_delay: float = 1.0,
        jitter: float = 1.5,
        max_retries: int = 2,   # fail blocked sources fast (don't burn minutes on retries)
    ):
        if cffi_requests is None:
            raise RuntimeError("curl_cffi is not installed; run pip install -r requirements.txt")
        self.impersonate = impersonate
        self.timeout = timeout
        self.min_delay = min_delay
        self.jitter = jitter
        self.max_retries = max_retries
        self._session = cffi_requests.Session(impersonate=impersonate)
        self._session.headers.update(DEFAULT_HEADERS)

    def _sleep_polite(self) -> None:
        time.sleep(self.min_delay + random.uniform(0, self.jitter))

    def get_text(self, url: str, *, params: dict | None = None,
                 headers: dict | None = None) -> str | None:
        """GET and return decoded text, or None on persistent failure."""
        backoff = 2.0
        for attempt in range(1, self.max_retries + 1):
            self._sleep_polite()
            try:
                resp = self._session.get(url, params=params, headers=headers, timeout=self.timeout)
            except Exception as e:  # noqa: BLE001
                log.warning("GET %s failed (attempt %d/%d): %s", url, attempt, self.max_retries, e)
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 200:
                if _is_challenge(resp.text):
                    log.warning("GET %s -> 200 but bot-challenge body (attempt %d/%d); backing off",
                                url, attempt, self.max_retries)
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                return resp.text
            if resp.status_code in (403, 429, 503):
                log.warning("GET %s -> %s (attempt %d/%d); backing off",
                            url, resp.status_code, attempt, self.max_retries)
                time.sleep(backoff)
                backoff *= 2
                continue
            log.warning("GET %s -> %s; giving up", url, resp.status_code)
            return None
        log.error("GET %s exhausted retries", url)
        return None

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:  # noqa: BLE001
            pass
