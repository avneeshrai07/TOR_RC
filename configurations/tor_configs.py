import os

# Tor control / socks
TOR_CONTROL_HOST = os.getenv("TOR_CONTROL_HOST", "127.0.0.1")
TOR_CONTROL_PORT = int(os.getenv("TOR_CONTROL_PORT", "9051"))
TOR_CONTROL_PASSWORD = os.getenv("TOR_CONTROL_PASSWORD", "StrongCtrlPass123")

TOR_SOCKS_HOST = os.getenv("TOR_SOCKS_HOST", "127.0.0.1")
TOR_SOCKS_PORT = int(os.getenv("TOR_SOCKS_PORT", "9050"))

# Tor IP rotation defaults
TOR_NEWNYM_COOLDOWN = int(os.getenv("TOR_NEWNYM_COOLDOWN", "10"))       # seconds
TOR_NEWNYM_BUILD_WAIT = int(os.getenv("TOR_NEWNYM_BUILD_WAIT", "10"))   # seconds
TOR_IP_RENEW_INTERVAL = int(os.getenv("TOR_IP_RENEW_INTERVAL", "1800")) # 30 minutes

# Request behavior
DEFAULT_MAX_RETRIES = int(os.getenv("DEFAULT_MAX_RETRIES", "3"))
DEFAULT_BACKOFF_FACTOR = float(os.getenv("DEFAULT_BACKOFF_FACTOR", "1.5"))


