"""Watchmode integration: streaming availability lookup and normalization."""
from .client import get_watchmode_client, WatchmodeClient
from .normalizer import normalize_where_to_watch_response
