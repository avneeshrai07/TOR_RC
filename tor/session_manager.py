import logging
import time
from typing import Optional

import requests

from configurations.tor_configs import (
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
    - Logs:
        * Current Tor exit IP
        * Minutes since current IP started being used
        * Minutes remaining until next rotation (by policy)
        * Tor MaxCircuitDirtiness + NEWNYM cooldown wait
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

        # avoid hitting ipify too frequently (extra request through tor)
        self._last_ip_check_ts: float = 0.0
        self._ip_check_cooldown_seconds: float = 30.0  # check at most once every 30s

    # -------- Internals -------- #

    def _ensure_session(self):
        if self.session is None:
            self.session = build_tor_session()

    def _ensure_started(self):
        if not self.session_active:
            self.start_session()

    def _sleep_backoff(self, attempt: int):
        delay = self.backoff_factor * attempt
        logger.info("Sleeping %.2f seconds before retry", delay)
        time.sleep(delay)

    # -------- IP Tracking / Logging -------- #

    def _fmt_min(self, seconds: float) -> str:
        return f"{seconds/60:.2f} min"

    def _get_max_circuit_dirtiness_seconds(self) -> int:
        """
        Tor rotates circuits after MaxCircuitDirtiness seconds (default often 600s).
        This provides an "expected" window for circuit freshness.
        """
        try:
            if self.controller and getattr(self.controller, "controller", None):
                val = self.controller.controller.get_conf("MaxCircuitDirtiness", "600")
                return int(val)
        except Exception:
            pass
        return 600

    def _get_newnym_wait_seconds(self) -> int:
        """
        Tor enforces a cooldown between NEWNYM signals.
        """
        try:
            if self.controller and getattr(self.controller, "controller", None):
                return int(self.controller.controller.get_newnym_wait())
        except Exception:
            pass
        return 0

    def _fetch_exit_ip_through_tor(self) -> Optional[str]:
        """
        Fetch public IP through Tor (exit IP) using the SAME session (and proxies).
        Uses ipify via Tor, so keep it rate-limited.
        """
        try:
            self._ensure_session()
            r = self.session.get("https://api.ipify.org?format=json", timeout=20)
            r.raise_for_status()
            return r.json().get("ip")
        except Exception as e:
            logger.warning("Failed to fetch Tor exit IP: %s", e)
            return None

    def _maybe_update_ip_cache(self):
        """
        Rate-limited IP check to avoid extra traffic.
        Updates current_ip + last_ip_change_time only if IP actually changed.
        """
        now = time.time()
        if (now - self._last_ip_check_ts) < self._ip_check_cooldown_seconds:
            return

        self._last_ip_check_ts = now
        ip = self._fetch_exit_ip_through_tor()
        if not ip:
            return

        # If IP changed, reset timer
        if self.current_ip != ip:
            self.current_ip = ip
            self.last_ip_change_time = now

    def log_ip_status(self, reason: str = ""):
        """
        Logs:
        - current exit IP
        - minutes since this IP started being used
        - minutes remaining until rotation by your time-based policy
        - tor MaxCircuitDirtiness + NEWNYM cooldown
        """
        now = time.time()

        # Update IP cache (rate-limited)
        self._maybe_update_ip_cache()

        used_for = (now - self.last_ip_change_time) if self.last_ip_change_time else 0.0
        rotates_in = (
            max(0.0, self.ip_renew_interval - used_for)
            if self.last_ip_change_time is not None
            else 0.0
        )

        dirtiness = self._get_max_circuit_dirtiness_seconds()
        newnym_wait = self._get_newnym_wait_seconds()

        logger.info(
            "Tor IP%s | ip=%s | used_for=%s | rotates_in=%s | policy_interval=%ss | MaxCircuitDirtiness=%ss | NEWNYM_wait=%ss",
            f" ({reason})" if reason else "",
            self.current_ip,
            self._fmt_min(used_for),
            self._fmt_min(rotates_in),
            self.ip_renew_interval,
            dirtiness,
            newnym_wait,
        )

    def _maybe_rotate_by_time(self):
        if (
            self.session_active
            and self.last_ip_change_time is not None
            and (time.time() - self.last_ip_change_time) > self.ip_renew_interval
        ):
            logger.info("IP renew interval reached; rotating IP.")
            self.log_ip_status(reason="before_time_rotate")
            self.renew_ip()
            self.log_ip_status(reason="after_time_rotate")

    # -------- Public API -------- #

    def start_session(self) -> bool:
        try:
            self.controller.ensure_connected()
            self._ensure_session()
            self.renew_ip(initial=True)
            self.session_active = True

            # log once at startup
            self.log_ip_status(reason="startup")
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
            self.log_ip_status(reason="newnym_skipped")
            return False

        # We mark "rotation requested now".
        # Real IP may or may not change immediately; log_ip_status will detect actual change.
        self.last_ip_change_time = time.time()
        logger.info("Tor IP rotation requested (initial=%s)", initial)

        # log right after rotation signal
        self.log_ip_status(reason="rotate_requested")
        return True

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Perform an HTTP request through Tor with:
        - Auto session start.
        - Time-based rotation.
        - Retry on 403/429/network failures with IP change.
        - Logs IP status before requests and around rotations.
        """
        self._ensure_started()
        self._maybe_rotate_by_time()

        # log before request
        self.log_ip_status(reason="before_request")

        for attempt in range(1, self.max_retries_per_request + 1):
            try:
                resp = self.session.request(method=method, url=url, **kwargs)

                if resp.status_code in (403, 429):
                    logger.warning(
                        "Status %s on %s; rotating IP and retrying.",
                        resp.status_code,
                        url,
                    )
                    self.log_ip_status(reason=f"status_{resp.status_code}_before_rotate")
                    self.renew_ip()
                    self.log_ip_status(reason=f"status_{resp.status_code}_after_rotate")

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
                self.log_ip_status(reason="exception_before_rotate")
                self.renew_ip()
                self.log_ip_status(reason="exception_after_rotate")

                if attempt == self.max_retries_per_request:
                    raise

                self._sleep_backoff(attempt)

        raise RuntimeError("Exhausted retries for URL: %s" % url)

    def close(self):
        if self.session:
            self.session.close()
            self.session = None

        if self.controller and getattr(self.controller, "controller", None):
            self.controller.controller.close()
            self.controller.controller = None

        self.session_active = False
        logger.info("Tor session closed.")


# Global singleton if you want simple usage
tor_session_manager = TorSessionManager()
