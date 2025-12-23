import logging
import time
from typing import Optional

import requests

from config import (
    TOR_IP_RENEW_INTERVAL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BACKOFF_FACTOR,
)
from tor.tor_core import TorController, build_tor_session

logger = logging.getLogger(__name__)


class TorSessionManager:
    """
    High-level manager:
    - Holds a Tor controller and a requests.Session.
    - Automatically rotates IP based on:
        * Time interval (default every 30 minutes).
        * HTTP status (403/429).
        * Network failures.
    """

    def __init__(
        self,
        ip_renew_interval: int = TOR_IP_RENEW_INTERVAL,
        max_retries_per_request: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    ):
        self.controller = TorController()
        self.session: Optional[requests.Session] = None
        self.current_ip: Optional[str] = None
        self.session_active: bool = False
        self.last_ip_change_time: Optional[float] = None

        self.ip_renew_interval = ip_renew_interval
        self.max_retries_per_request = max_retries_per_request
        self.backoff_factor = backoff_factor

    # -------- Internals -------- #

    def _ensure_session(self):
        if self.session is None:
            self.session = build_tor_session()

    def _ensure_started(self):
        if not self.session_active:
            self.start_session()

    def _maybe_rotate_by_time(self):
        if (
            self.session_active
            and self.last_ip_change_time is not None
            and (time.time() - self.last_ip_change_time) > self.ip_renew_interval
        ):
            logger.info("IP renew interval reached; rotating IP.")
            self.renew_ip()

    def _sleep_backoff(self, attempt: int):
        delay = self.backoff_factor * attempt
        logger.info("Sleeping %.2f seconds before retry", delay)
        time.sleep(delay)

    # -------- Public API -------- #

    def start_session(self) -> bool:
        try:
            self.controller.ensure_connected()
            self._ensure_session()
            self.renew_ip(initial=True)
            self.session_active = True
            return True
        except Exception as e:
            logger.error("Failed to start Tor session: %s", e)
            self.session_active = False
            return False

    def renew_ip(self, initial: bool = False) -> bool:
        """
        Default change logic:
        - Ask Tor for NEWNYM (with cooldown).
        - Wait a bit and update last_ip_change_time.
        - Do NOT hammer Tor; session reuse is preferred.
        """
        if not self.session:
            self._ensure_session()

        rotated = self.controller.newnym(wait_for_build=True)
        if not rotated and not initial:
            logger.info("NEWNYM was skipped due to cooldown.")
            return False

        self.last_ip_change_time = time.time()
        logger.info("Tor IP rotation requested (initial=%s)", initial)
        # Optionally you can fetch and log new exit IP here via an external check.
        return True

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Perform an HTTP request through Tor with:
        - Auto session start.
        - Time-based rotation.
        - Retry on 403/429/network failures with IP change.
        """
        self._ensure_started()
        self._maybe_rotate_by_time()

        for attempt in range(1, self.max_retries_per_request + 1):
            try:
                resp = self.session.request(method=method, url=url, **kwargs)

                if resp.status_code in (403, 429):
                    logger.warning(
                        "Status %s on %s; rotating IP and retrying.",
                        resp.status_code,
                        url,
                    )
                    self.renew_ip()
                    if attempt == self.max_retries_per_request:
                        resp.raise_for_status()
                    self._sleep_backoff(attempt)
                    continue

                resp.raise_for_status()
                return resp

            except requests.exceptions.RequestException as e:
                logger.warning(
                    "Request error (attempt %d/%d) for %s: %s",
                    attempt,
                    self.max_retries_per_request,
                    url,
                    e,
                )
                self.renew_ip()
                if attempt == self.max_retries_per_request:
                    raise
                self._sleep_backoff(attempt)

        # Should not reach here
        raise RuntimeError("Exhausted retries for URL: %s" % url)

    def close(self):
        if self.session:
            self.session.close()
            self.session = None
        if self.controller.controller:
            self.controller.controller.close()
            self.controller.controller = None
        self.session_active = False
        logger.info("Tor session closed.")


# Global singleton if you want simple usage
tor_session_manager = TorSessionManager()
