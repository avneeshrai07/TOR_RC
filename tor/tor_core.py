import time
import logging
from typing import Optional

import requests
from stem import Signal
from stem.control import Controller
from stem import SocketError

from config import (
    TOR_CONTROL_HOST,
    TOR_CONTROL_PORT,
    TOR_CONTROL_PASSWORD,
    TOR_SOCKS_HOST,
    TOR_SOCKS_PORT,
    TOR_NEWNYM_COOLDOWN,
    TOR_NEWNYM_BUILD_WAIT,
)

logger = logging.getLogger(__name__)


class TorController:
    """
    Low-level Tor controller with NEWNYM cooldown and simple helpers.
    """

    def __init__(
        self,
        host: str = TOR_CONTROL_HOST,
        port: int = TOR_CONTROL_PORT,
        password: str = TOR_CONTROL_PASSWORD,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.controller: Optional[Controller] = None
        self.last_newnym_ts: float = 0.0

    def connect(self) -> Controller:
        if self.controller and self.controller.is_alive():
            return self.controller

        try:
            self.controller = Controller.from_port(address=self.host, port=self.port)
            self.controller.authenticate(password=self.password)
            logger.info("Connected and authenticated to Tor control port")
            return self.controller
        except SocketError as e:
            logger.error("Failed to connect to Tor control port: %s", e)
            self.controller = None
            raise

    def ensure_connected(self):
        if not self.controller or not self.controller.is_alive():
            self.connect()

    def can_newnym(self) -> bool:
        return (time.time() - self.last_newnym_ts) >= TOR_NEWNYM_COOLDOWN

    def newnym(self, wait_for_build: bool = True) -> bool:
        self.ensure_connected()
        if not self.can_newnym():
            logger.info("NEWNYM cooldown active, skipping.")
            return False

        self.controller.signal(Signal.NEWNYM)
        self.last_newnym_ts = time.time()
        logger.info("NEWNYM signal sent")

        if wait_for_build:
            time.sleep(TOR_NEWNYM_BUILD_WAIT)
        return True

    def get_circuits_summary(self):
        """
        Optional debugging helper.
        """
        self.ensure_connected()
        result = []
        for circ in self.controller.get_circuits():
            if circ.status != "BUILT":
                continue
            exit_fp = circ.path[-1][0]
            exit_desc = self.controller.get_network_status(exit_fp)
            result.append(
                {
                    "id": circ.id,
                    "purpose": circ.purpose,
                    "exit_fingerprint": exit_fp,
                    "exit_address": exit_desc.address if exit_desc else None,
                }
            )
        return result


def tor_proxies() -> dict:
    """
    SOCKS5 proxies for requests.
    """
    return {
        "http": f"socks5h://{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}",
        "https": f"socks5h://{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}",
    }


def build_tor_session() -> requests.Session:
    """
    Preconfigured session using Tor SOCKS proxy.
    """
    session = requests.Session()
    session.proxies = tor_proxies()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )
    return session
