"""
Watchmode API client for Where to Watch (server-side only).

- Provider catalog (/v1/sources/): cached in-memory, refreshed monthly.
- Title lookup: /v1/autocomplete-search/ by TMDB ID or name fallback.
- Availability: /v1/title/{id}/sources/ with regions.
- Response caching for availability per title+country (TTL 6h).
- Normalizes to UI contract: groups by access type, provider name, price, webUrl, deeplink.
"""
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

WATCHMODE_BASE = "https://api.watchmode.com/v1"

# Canonical user-facing messages (single source of truth; avoid duplication in UI)
MSG_TITLE_NOT_FOUND_TMDB = "Title not found for the given TMDB id and type."
MSG_TITLE_NOT_FOUND_NAME = "Title not found. Try a different spelling or add the year."
SOURCES_CACHE_TTL_SEC = 30 * 24 * 3600  # 30 days
AVAILABILITY_CACHE_TTL_SEC = 6 * 3600  # 6 hours (respect typical provider cache guidance)

# Map Watchmode type codes to our access types and labels
ACCESS_TYPE_MAP = {
    "sub": ("subscription", "Subscription"),
    "subscription": ("subscription", "Subscription"),
    "streaming": ("subscription", "Subscription"),
    "free": ("free", "Free"),
    "ads": ("free", "Free"),
    "rent": ("rental", "Rent"),
    "rental": ("rental", "Rent"),
    "buy": ("purchase", "Buy"),
    "purchase": ("purchase", "Buy"),
    "addon": ("subscription", "Add-on"),
    "tve": ("tve", "TV Everywhere"),
}


def _normalize_access_type(wm_type: str) -> tuple[str, str]:
    if not wm_type:
        return ("other", "Other")
    key = (wm_type or "").strip().lower()
    return ACCESS_TYPE_MAP.get(key, ("other", key.title()))


class WatchmodeClient:
    """Watchmode API client with in-memory caching for sources and availability."""

    def __init__(self, api_key: str, timeout: float = 15.0):
        self._api_key = api_key
        self._timeout = timeout
        self._sources_cache: dict[str, Any] | None = None
        self._sources_cache_ts: float = 0
        self._availability_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._provider_names: dict[int, str] = {}

    def _cache_key(self, title_id: str, country: str) -> str:
        return f"{title_id}|{country.upper()}"

    async def _get_sources_catalog_uncached(self) -> dict[int, str]:
        """Fetch /v1/sources/ and return mapping source_id -> name."""
        url = f"{WATCHMODE_BASE}/sources/"
        params = {"apiKey": self._api_key}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        if isinstance(data, list):
            return {int(s.get("id", 0)): str(s.get("name", "") or "").strip() or f"Source {s.get('id')}" for s in data if s.get("id") is not None}
        return {}

    async def get_sources_catalog(self) -> dict[int, str]:
        """Provider catalog (source_id -> name), cached ~30 days."""
        now = time.monotonic()
        if self._sources_cache is not None and (now - self._sources_cache_ts) < SOURCES_CACHE_TTL_SEC:
            return self._sources_cache
        try:
            self._sources_cache = await self._get_sources_catalog_uncached()
            self._sources_cache_ts = now
            self._provider_names = self._sources_cache
            return self._sources_cache
        except Exception as e:
            logger.warning("Watchmode sources catalog fetch failed: %s", e)
            if self._sources_cache is not None:
                return self._sources_cache
            return {}

    async def find_title_id_by_tmdb(self, tmdb_id: str, media_type: str) -> int | None:
        """
        Resolve Watchmode title id from TMDB id + type.
        Tries title details with composite id (movie-603 / tv-1396) first; falls back to autocomplete-search.
        """
        tmdb_id = (tmdb_id or "").strip()
        media_type = (media_type or "movie").strip().lower()
        if not tmdb_id:
            return None
        if media_type not in ("movie", "tv"):
            media_type = "movie"

        # Try title details with composite id (Watchmode accepts movie-603, tv-1396 style)
        for composite_id in [f"{media_type}-{tmdb_id}", f"tmdb_{media_type}_{tmdb_id}"]:
            try:
                detail_url = f"{WATCHMODE_BASE}/title/{composite_id}/details/"
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    r = await client.get(detail_url, params={"apiKey": self._api_key})
                    if r.status_code == 404:
                        continue
                    r.raise_for_status()
                    data = r.json()
                wid = data.get("id") or data.get("watchmode_id")
                if wid is not None:
                    return int(wid)
            except (httpx.HTTPStatusError, ValueError, KeyError):
                continue

        # Fallback: autocomplete-search by tmdb_id or name
        url = f"{WATCHMODE_BASE}/autocomplete-search/"
        params = {"apiKey": self._api_key, "search_value": tmdb_id, "search_field": "tmdb_id"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(url, params=params)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                data = r.json()
            results = data if isinstance(data, list) else (data.get("results") or data.get("titles") or [])
            if results and isinstance(results[0], dict):
                i = results[0].get("id") or results[0].get("watchmode_id")
                return int(i) if i is not None else None
        except (httpx.HTTPStatusError, ValueError, KeyError) as e:
            logger.debug("Watchmode autocomplete-search failed: %s", e)
        return None

    async def find_title_id_by_name(self, title: str, year: int | None, media_type: str) -> int | None:
        """
        Resolve Watchmode title id from title name (and optional year) via autocomplete-search.
        Uses search_field=name, search_value=title. Returns first result's id when available.
        """
        title = (title or "").strip()
        media_type = (media_type or "movie").strip().lower()
        if not title or media_type not in ("movie", "tv"):
            return None
        url = f"{WATCHMODE_BASE}/autocomplete-search/"
        params = {"apiKey": self._api_key, "search_value": title, "search_field": "name"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(url, params=params)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                data = r.json()
            results = data if isinstance(data, list) else (data.get("results") or data.get("titles") or [])
            if not results or not isinstance(results[0], dict):
                return None
            # Prefer result matching year if provided
            if year is not None:
                for item in results:
                    item_year = item.get("year")
                    if item_year is not None and int(item_year) == int(year):
                        i = item.get("id") or item.get("watchmode_id")
                        if i is not None:
                            return int(i)
            i = results[0].get("id") or results[0].get("watchmode_id")
            return int(i) if i is not None else None
        except (httpx.HTTPStatusError, ValueError, KeyError) as e:
            logger.debug("Watchmode autocomplete-search by name failed: %s", e)
        return None

    async def get_title_details(self, title_id: str) -> dict[str, Any] | None:
        """GET /v1/title/{title_id}/details/ to get title info including external_ids (e.g. tmdb_id)."""
        url = f"{WATCHMODE_BASE}/title/{title_id}/details/"
        params = {"apiKey": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(url, params=params)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
        except (httpx.HTTPStatusError, ValueError, KeyError):
            return None

    def _extract_tmdb_id_from_details(self, details: dict[str, Any] | None) -> str | None:
        """Extract TMDB id from Watchmode title details response."""
        if not details or not isinstance(details, dict):
            return None
        tid = details.get("tmdb_id")
        if tid is not None and str(tid).strip():
            return str(tid).strip()
        ext = details.get("external_ids") or {}
        if isinstance(ext, dict):
            tid = ext.get("tmdb") or ext.get("tmdb_id")
            if tid is not None and str(tid).strip():
                return str(tid).strip()
        return None

    async def get_title_sources_raw(self, title_id: str, regions: str) -> dict[str, Any]:
        """
        GET /v1/title/{title_id}/sources/?regions=...&types=...

        title_id: Watchmode ID (e.g. 345534), IMDB ID (e.g. tt0903747), or TMDB format (e.g. movie-278, tv-1396).
        See https://api.watchmode.com/docs#tag/Title/operation/getTitleSources
        """
        url = f"{WATCHMODE_BASE}/title/{title_id}/sources/"
        params = {
            "apiKey": self._api_key,
            "regions": regions,
            "types": "sub,free,purchase,rent,tve",
            "sourceTypes": "sub,free,purchase,rent,tve",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def get_availability(
        self, tmdb_id: str, media_type: str, country: str
    ) -> tuple[str | None, dict[str, Any] | None]:
        """
        Get availability for a title. Returns (error_message, normalized_response).
        Uses Watchmode getTitleSources with TMDB-format title_id (e.g. movie-278, tv-1396).
        """
        regions = country.upper() if country else "US"
        mt = (media_type or "movie").strip().lower()
        if mt not in ("movie", "tv"):
            mt = "movie"
        title_id = f"{mt}-{(tmdb_id or '').strip()}"
        if not (tmdb_id or "").strip():
            return MSG_TITLE_NOT_FOUND_TMDB, None

        ck = self._cache_key(title_id, regions)
        now_sec = time.time()
        if ck in self._availability_cache:
            ts, payload = self._availability_cache[ck]
            if (now_sec - ts) < AVAILABILITY_CACHE_TTL_SEC:
                return None, payload

        try:
            raw = await self.get_title_sources_raw(title_id, regions)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return MSG_TITLE_NOT_FOUND_TMDB, None
            if e.response.status_code == 429:
                return "Rate limit exceeded. Try again later.", None
            return f"Watchmode API error: {e.response.status_code}.", None
        except Exception:
            logger.exception("Watchmode sources request failed")
            return "Service temporarily unavailable.", None

        catalog = await self.get_sources_catalog()
        normalized = self._normalize_sources_response(raw, regions, catalog)
        self._availability_cache[ck] = (now_sec, normalized)
        return None, normalized

    def _strip_disambiguation_suffix(self, title: str) -> str | None:
        """
        If title ends with ' (something)' and 'something' is not a 4-digit year,
        return the base title without the parenthetical (for retry when exact match fails).
        E.g. 'Avatar (franchise)' -> 'Avatar'; 'Avatar (2009)' -> None (keep year).
        """
        if not title or " (" not in title or not title.endswith(")"):
            return None
        base, _, suffix = title.rpartition(" (")
        suffix = suffix[:-1].strip()  # drop trailing )
        if not base.strip():
            return None
        if len(suffix) == 4 and suffix.isdigit():
            return None  # year: don't strip
        return base.strip() or None

    async def get_availability_by_title(
        self, title: str, year: int | None, media_type: str, country: str
    ) -> tuple[str | None, dict[str, Any] | None]:
        """
        Get availability by title name (and optional year). Uses autocomplete-search then sources.
        Returns (error_message, normalized_response) like get_availability.
        If exact title fails and title has a disambiguation suffix (e.g. " (franchise)"), retries with base name.
        """
        title = (title or "").strip()
        if not title:
            return "Title is required for title-based lookup.", None
        regions = (country or "US").upper()
        media_type = (media_type or "movie").strip().lower()
        if media_type not in ("movie", "tv"):
            media_type = "movie"
        ck = self._cache_key(f"name-{title}-{year}-{media_type}", regions)
        now_sec = time.time()
        if ck in self._availability_cache:
            ts, payload = self._availability_cache[ck]
            if (now_sec - ts) < AVAILABILITY_CACHE_TTL_SEC:
                return None, payload
        title_id = await self.find_title_id_by_name(title, year, media_type)
        if title_id is None:
            base_title = self._strip_disambiguation_suffix(title)
            if base_title and base_title != title:
                title_id = await self.find_title_id_by_name(base_title, year, media_type)
                if title_id is not None:
                    logger.info("Where-to-watch: title '%s' not found; used base title '%s'", title, base_title)
        if title_id is None:
            return MSG_TITLE_NOT_FOUND_NAME, None
        try:
            raw = await self.get_title_sources_raw(str(title_id), regions)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return MSG_TITLE_NOT_FOUND_NAME, None
            if e.response.status_code == 429:
                return "Rate limit exceeded. Try again later.", None
            return f"Watchmode API error: {e.response.status_code}.", None
        except Exception:
            logger.exception("Watchmode sources request failed")
            return "Service temporarily unavailable.", None
        catalog = await self.get_sources_catalog()
        normalized = self._normalize_sources_response(raw, regions, catalog)
        details = await self.get_title_details(str(title_id))
        resolved_tmdb_id = self._extract_tmdb_id_from_details(details)
        if resolved_tmdb_id:
            normalized["_resolved_tmdb_id"] = resolved_tmdb_id
        self._availability_cache[ck] = (now_sec, normalized)
        return None, normalized

    def _normalize_sources_response(
        self, raw: Any, region: str, provider_names: dict[int, str]
    ) -> dict[str, Any]:
        """Convert Watchmode sources response to UI contract: movie, region, groups[].accessType, label, offers[]."""
        out = {
            "movie": {},
            "region": region,
            "groups": [],
        }
        if not isinstance(raw, dict):
            if isinstance(raw, list):
                sources = raw
            else:
                return out
        else:
            # Watchmode may use "sources", "title_sources", "results", or "data"
            sources = (
                raw.get("sources")
                or raw.get("title_sources")
                or raw.get("results")
                or raw.get("data")
            )
            if not isinstance(sources, list):
                sources = []
        if not isinstance(sources, list):
            return out
        if len(sources) == 0 and isinstance(raw, dict):
            logger.debug("Watchmode sources response empty; keys received: %s", list(raw.keys()))

        by_type: dict[str, list[dict[str, Any]]] = {}
        for s in sources:
            if not isinstance(s, dict):
                continue
            wm_type = (s.get("type") or s.get("access_type") or "").strip().lower()
            access_type, label = _normalize_access_type(wm_type)
            source_id = s.get("source_id") or s.get("sourceId") or s.get("id")
            name = (s.get("name") or "").strip() or provider_names.get(int(source_id) if source_id is not None else 0) or "Unknown"
            web_url = (s.get("web_url") or s.get("webUrl") or s.get("url") or "").strip() or None
            deeplink = (s.get("deeplink") or s.get("deeplink_url") or "").strip() or None
            if not deeplink and isinstance(s.get("deeplinks"), dict):
                deeplink = (s["deeplinks"].get("ios") or s["deeplinks"].get("android") or "").strip() or None
            price = None
            if s.get("price") is not None:
                try:
                    amt = float(s["price"])
                    price = {"amount": amt, "currency": (s.get("currency") or "USD").strip() or "USD"}
                except (TypeError, ValueError):
                    pass
            offer = {
                "providerId": source_id,
                "providerName": name,
                "price": price,
                "webUrl": web_url,
                "deeplink": deeplink,
            }
            by_type.setdefault(access_type, []).append((label, offer))

        # Dedupe by provider per type; build groups in fixed order
        order = ["subscription", "free", "rental", "purchase", "tve", "other"]
        for at in order:
            if at not in by_type:
                continue
            labels_offers = by_type[at]
            unique_offers: list[dict[str, Any]] = []
            seen_names = set()
            for _label, offer in labels_offers:
                if offer["providerName"] in seen_names:
                    continue
                seen_names.add(offer["providerName"])
                unique_offers.append(offer)
            if not unique_offers:
                continue
            group_label = labels_offers[0][0] if labels_offers else at.title()
            out["groups"].append({
                "accessType": at,
                "label": group_label,
                "offers": unique_offers,
            })
        for at, labels_offers in by_type.items():
            if at in order:
                continue
            unique_offers = [o for _, o in labels_offers]
            out["groups"].append({"accessType": at, "label": at.title(), "offers": unique_offers})
        return out


def get_watchmode_client(api_key: str | None = None) -> WatchmodeClient | None:
    """Factory: returns WatchmodeClient if api_key is set, else None."""
    from config import get_watchmode_api_key
    key = (api_key or get_watchmode_api_key() or "").strip()
    if not key:
        return None
    return WatchmodeClient(api_key=key)
