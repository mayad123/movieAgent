"""
Normalize Where to Watch API response for the UI.

Output shape:
  title: { id, name, year, mediaType }
  region: country code
  offers: flat array, grouped and sorted by accessType then provider name;
          each offer: provider { id, name }, accessType, price?, webUrl?, iosUrl?, androidUrl?, quality?, lastUpdated

Rules:
- Group and sort by accessType (subscription, free, rental, purchase, tve, unknown) then provider name.
- De-dupe identical offers (same provider id + url + accessType).
- Prefer deeplink when present; keep web fallback (webUrl for web, iosUrl/androidUrl from deeplink when available).
- lastUpdated: ISO timestamp for caching transparency.
"""

from datetime import UTC, datetime
from typing import Any

# UI contract: subscription | free | rent | buy | tve | unknown
ACCESS_TYPE_ORDER = ("subscription", "free", "rent", "buy", "tve", "unknown", "other")
# Map internal names to contract
ACCESS_TYPE_ALIAS = {"rental": "rent", "purchase": "buy"}


def normalize_where_to_watch_response(
    data: dict[str, Any],
    *,
    title_id: str | None = None,
    title_name: str | None = None,
    year: int | None = None,
    media_type: str = "movie",
    last_updated: str | None = None,
) -> dict[str, Any]:
    """
    Normalize API response to UI contract: title, region, offers (flat, grouped and sorted, de-duped).

    Input `data` can have:
      - groups: [ { accessType, label, offers: [ { providerName, price, webUrl, deeplink } ] } ]
      - or offers: already flat list (will still be deduped and sorted)
    Optional request context: title_id (e.g. TMDB id), title_name, year, media_type.
    """
    now_iso = last_updated or datetime.now(UTC).isoformat()
    region = (data.get("region") or "").strip() or "US"
    title = {
        "id": (title_id or data.get("movie", {}).get("id") or "").strip() or None,
        "name": (title_name or data.get("movie", {}).get("title") or data.get("movie", {}).get("name") or "").strip()
        or "Unknown",
        "year": year if year is not None else data.get("movie", {}).get("year"),
        "mediaType": (media_type or "movie").strip().lower() or "movie",
    }
    if title["mediaType"] not in ("movie", "tv"):
        title["mediaType"] = "movie"

    # Build flat list from groups or existing offers
    flat: list[dict[str, Any]] = []
    if data.get("offers") and isinstance(data["offers"], list):
        flat = list(data["offers"])
    elif data.get("groups") and isinstance(data["groups"], list):
        for g in data["groups"]:
            if not isinstance(g, dict):
                continue
            at = (g.get("accessType") or "unknown").strip().lower() or "unknown"
            for o in g.get("offers") or []:
                if not isinstance(o, dict):
                    continue
                p_name = o.get("providerName")
                if not p_name and isinstance(o.get("provider"), dict):
                    p_name = (o.get("provider") or {}).get("name")
                p_id = o.get("providerId")
                if p_id is None and isinstance(o.get("provider"), dict):
                    p_id = (o.get("provider") or {}).get("id")
                flat.append(
                    {
                        "_accessType": at,
                        "providerName": p_name,
                        "providerId": p_id,
                        "price": o.get("price"),
                        "webUrl": o.get("webUrl") or o.get("web_url"),
                        "deeplink": o.get("deeplink") or o.get("iosUrl") or o.get("androidUrl"),
                        "iosUrl": o.get("iosUrl"),
                        "androidUrl": o.get("androidUrl"),
                        "quality": o.get("quality"),
                    }
                )
    else:
        return {"title": title, "region": region, "offers": [], "lastUpdated": now_iso}

    # Normalize each into offer shape; prefer deeplink, keep web fallback
    normalized: list[dict[str, Any]] = []
    seen: set = set()
    for o in flat:
        at = (o.get("_accessType") or "unknown").strip().lower() or "unknown"
        at = ACCESS_TYPE_ALIAS.get(at, at)
        if at not in ACCESS_TYPE_ORDER:
            at = "unknown"
        pid = o.get("providerId")
        if pid is None:
            pid = o.get("providerName") or "unknown"
        pname = (o.get("providerName") or "").strip() or str(pid) or "Unknown"
        web_url = (o.get("webUrl") or "").strip() or None
        deeplink = (o.get("deeplink") or "").strip() or None
        ios_url = (o.get("iosUrl") or "").strip() or None
        android_url = (o.get("androidUrl") or "").strip() or None
        if deeplink and not ios_url and not android_url:
            ios_url = deeplink
            android_url = deeplink
        url_key = web_url or ios_url or android_url or ""
        dedupe_key = (str(pid), url_key, at)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        price = o.get("price")
        if isinstance(price, dict) and "amount" in price:
            price = {"amount": float(price["amount"]), "currency": (price.get("currency") or "USD").strip() or "USD"}
        elif price is not None and not isinstance(price, dict):
            price = None
        quality = (o.get("quality") or "").strip() or None
        normalized.append(
            {
                "provider": {"id": pid, "name": pname},
                "accessType": at,
                "price": price,
                "webUrl": web_url,
                "iosUrl": ios_url,
                "androidUrl": android_url,
                "quality": quality,
                "lastUpdated": now_iso,
            }
        )

    # Sort: by accessType order then provider name
    def sort_key(item: dict[str, Any]) -> tuple:
        at = item.get("accessType") or "other"
        try:
            at_index = ACCESS_TYPE_ORDER.index(at)
        except ValueError:
            at_index = len(ACCESS_TYPE_ORDER)
        return (at_index, (item.get("provider") or {}).get("name") or "")

    normalized.sort(key=sort_key)

    return {
        "title": title,
        "region": region,
        "offers": normalized,
        "lastUpdated": now_iso,
    }
