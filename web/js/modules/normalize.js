/** @module normalize — Pure data-normalization functions (no DOM or state dependencies). */

/**
 * Normalize API result into a safe meta object for rendering.
 * Contract: UI_RESPONSE_CONTRACT.md. Never throws.
 */
export function normalizeMeta(meta) {
    if (meta == null || typeof meta !== 'object') return null;
    const out = {};
    out.content = String(meta.response != null ? meta.response : meta.answer != null ? meta.answer : '').trim();
    out.actualAgentMode = meta.actualAgentMode || meta.agent_mode || null;
    out.requestedAgentMode = meta.requestedAgentMode || null;
    out.modeFallback = !!meta.modeFallback;
    out.modeOverrideReason = meta.modeOverrideReason && String(meta.modeOverrideReason).trim() || null;
    out.toolsUsed = Array.isArray(meta.toolsUsed) ? meta.toolsUsed : null;
    if (meta.media_strip != null && typeof meta.media_strip === 'object') {
        const title = String(meta.media_strip.movie_title != null ? meta.media_strip.movie_title : '').trim();
        const primaryImageUrl = meta.media_strip.primary_image_url && String(meta.media_strip.primary_image_url).trim();
        const pageUrl = meta.media_strip.page_url && String(meta.media_strip.page_url).trim();
        const year = typeof meta.media_strip.year === 'number' ? meta.media_strip.year : undefined;
        const thumbnailUrls = Array.isArray(meta.media_strip.thumbnail_urls)
            ? meta.media_strip.thumbnail_urls.slice(0, 3).map(function (u) { return u != null ? String(u).trim() : ''; }).filter(Boolean)
            : [];
        let strip = null;
        if (title) {
            strip = {
                movie_title: title,
                primary_image_url: primaryImageUrl || undefined,
                page_url: pageUrl || undefined,
                year: year,
                thumbnail_urls: thumbnailUrls
            };
        }
        out.media_strip = strip;
    } else {
        out.media_strip = null;
    }
    out.media_gallery_label = meta.media_gallery_label && String(meta.media_gallery_label).trim() || null;
    if (Array.isArray(meta.media_candidates) && meta.media_candidates.length > 0) {
        out.media_candidates = meta.media_candidates
            .filter(function (c) { return c != null && typeof c === 'object'; })
            .map(function (c) {
                const t = String(c.movie_title != null ? c.movie_title : '').trim();
                return t ? {
                    movie_title: t,
                    page_url: c.page_url != null ? String(c.page_url).trim() || '#' : '#',
                    year: typeof c.year === 'number' ? c.year : undefined,
                    primary_image_url: c.primary_image_url && String(c.primary_image_url).trim()
                } : null;
            })
            .filter(Boolean);
    } else {
        out.media_candidates = [];
    }
    if (meta.attachments != null && typeof meta.attachments === 'object' && Array.isArray(meta.attachments.sections)) {
        out.attachments = {
            sections: meta.attachments.sections
                .filter(function (s) { return s != null && typeof s === 'object' && Array.isArray(s.items); })
                .map(function (s) {
                    return {
                        type: String(s.type || '').trim() || 'movie_list',
                        title: String(s.title != null ? s.title : '').trim() || 'Movies',
                        items: (s.items || []).filter(function (it) { return it != null && typeof it === 'object'; })
                    };
                })
                .filter(function (s) { return s.items.length > 0; })
        };
    } else {
        out.attachments = null;
    }
    return out;
}

/**
 * Normalize Where to Watch error message: dedupe repeated sentences and use canonical phrasing.
 */
export function normalizeWhereToWatchErrorMessage(msg) {
    if (!msg || typeof msg !== 'string') return msg || '';
    const s = msg.trim();
    if (!s) return s;
    const canonical = 'Title not found. Try a different spelling or add the year.';
    if (s.indexOf(canonical) !== -1) return canonical;
    if (s.length % 2 === 0 && s.slice(0, s.length / 2) === s.slice(s.length / 2)) return s.slice(0, s.length / 2).trim();
    const parts = s.split(/\s*\.\s+/).filter(Boolean);
    const seen = {};
    const out = [];
    for (let i = 0; i < parts.length; i++) {
        const p = (parts[i] || '').trim();
        if (p && !seen[p]) { seen[p] = true; out.push(p); }
    }
    return out.length ? out.join('. ') + (s.slice(-1) === '.' ? '' : '') : s;
}

/**
 * HTML-escape a string using the DOM.
 */
export function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}
