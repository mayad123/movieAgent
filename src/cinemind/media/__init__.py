"""Media enrichment, caching, and attachment modules."""

from .attachment_intent_classifier import AttachmentIntentResult, classify_attachment_intent
from .media_cache import MediaCache, TTLCache, get_default_media_cache, set_default_media_cache
from .media_enrichment import (
    MediaEnrichmentResult,
    attach_media_to_result,
    build_attachments_from_media,
    enrich,
    enrich_batch,
)
from .media_focus import MEDIA_FOCUS_MULTI, MEDIA_FOCUS_SINGLE, get_media_focus
from .playground_attachments import ATTACHMENT_DEBUG_KEY, apply_playground_attachment_behavior
