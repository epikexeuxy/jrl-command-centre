"""Rate limiting via slowapi (in-memory storage; Redis-backed storage arrives in Phase 4)."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
