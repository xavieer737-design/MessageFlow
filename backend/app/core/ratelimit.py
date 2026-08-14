"""Rate limiting (slowapi). Limits are configured per-endpoint."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
