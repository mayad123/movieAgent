"""Media enrichment, caching, and attachment modules."""
from .media_enrichment import (
    MediaEnrichmentResult, enrich, enrich_batch,
    build_attachments_from_media, attach_media_to_result,
)
from .media_cache import MediaCache, TTLCache, get_default_media_cache, set_default_media_cache
from .media_focus import get_media_focus, MEDIA_FOCUS_SINGLE, MEDIA_FOCUS_MULTI
from .playground_attachments import apply_playground_attachment_behavior, ATTACHMENT_DEBUG_KEY
from .attachment_intent_classifier import AttachmentIntentResult, classify_attachment_intent
