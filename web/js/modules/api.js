/** @module api — API client for CineMind backend calls. */

import { API_BASE, SEND_TIMEOUT_MS } from './state.js';

function _buildTimedSignal(timeoutMs, externalSignal) {
    const controller = new AbortController();
    const timeoutId = setTimeout(function () { controller.abort(); }, timeoutMs);
    let onAbort = null;
    if (externalSignal) {
        if (externalSignal.aborted) controller.abort();
        else {
            onAbort = function () { controller.abort(); };
            externalSignal.addEventListener('abort', onAbort, { once: true });
        }
    }
    return {
        signal: controller.signal,
        cleanup: function () {
            clearTimeout(timeoutId);
            if (externalSignal && onAbort) {
                externalSignal.removeEventListener('abort', onAbort);
            }
        }
    };
}

/**
 * Prefix a user query with a deterministic anchor marker for the Sub-context Movie Hub.
 * This is parsed server-side to constrain which candidate universe the hub filtering should use.
 *
 * Marker format:
 * [[CINEMIND_HUB_CONTEXT]]{"title":"...","year":1999,"tmdbId":123}[[/CINEMIND_HUB_CONTEXT]]
 */
export function prefixMovieHubContextQuery(userQuery, contextMovie, candidateTitles) {
    const q = userQuery != null ? String(userQuery) : '';
    if (!q) return q;
    if (!contextMovie || typeof contextMovie !== 'object') return q;

    const title = (contextMovie.title != null ? String(contextMovie.title) : '').replace(/\s+/g, ' ').trim();
    const yearRaw = contextMovie.year;
    const year = (yearRaw != null && String(yearRaw).toString().trim() !== '' && !isNaN(Number(yearRaw)))
        ? Number(yearRaw)
        : null;
    const tmdbIdRaw = contextMovie.tmdbId != null ? contextMovie.tmdbId : contextMovie.tmdb_id;
    const tmdbId = (tmdbIdRaw != null && String(tmdbIdRaw).toString().trim() !== '' && !isNaN(Number(tmdbIdRaw)))
        ? Number(tmdbIdRaw)
        : null;

    // If we can't anchor, don't add noise to the query.
    if (!title && !tmdbId) return q;

    const markerPayload = {
        title: title || null,
        year: year,
        tmdbId: tmdbId,
    };

    if (Array.isArray(candidateTitles)) {
        const normalized = candidateTitles
            .map(function (it) {
                if (it == null) return '';
                return String(it).trim();
            })
            .filter(function (s) { return !!s; })
            .slice(0, 30);
        if (normalized.length) markerPayload.candidateTitles = normalized;
    }

    const marker = `[[CINEMIND_HUB_CONTEXT]]${JSON.stringify(markerPayload)}[[/CINEMIND_HUB_CONTEXT]]`;
    return marker + '\n' + q;
}

/**
 * Call GET /api/watch/where-to-watch and pass normalized result to callback.
 * movie: { title, year?, pageUrl?, pageId?, tmdbId?, mediaType? }.
 * Uses tmdbId when present; otherwise title+year (backend does Watchmode name lookup).
 */
export function fetchWhereToWatch(movie, callback, options) {
    options = options || {};
    let tmdbId = (movie && (movie.tmdbId != null ? String(movie.tmdbId).trim() : (movie.pageId != null ? String(movie.pageId).trim() : ''))) || '';
    if (!tmdbId && movie && movie.pageUrl && typeof movie.pageUrl === 'string') {
        const m = /themoviedb\.org\/movie\/(\d+)/i.exec(movie.pageUrl);
        if (m) tmdbId = m[1];
    }
    const title = (movie && movie.title && String(movie.title).trim()) || '';
    if (!tmdbId && !title) {
        callback(new Error('Movie title or ID is required to find where to watch.'));
        return;
    }
    const mediaType = (movie.mediaType && String(movie.mediaType).trim()) || 'movie';
    const country = (movie.country && String(movie.country).trim()) || 'US';
    const params = new URLSearchParams({ mediaType: mediaType, country: country });
    if (tmdbId) params.set('tmdbId', tmdbId);
    if (title) params.set('title', title);
    if (movie.year != null && movie.year !== '') params.set('year', String(movie.year));
    const url = API_BASE + '/api/watch/where-to-watch?' + params.toString();
    const timeoutMs = (options && typeof options.timeoutMs === 'number' && options.timeoutMs > 0)
        ? options.timeoutMs
        : 12000;
    const timed = _buildTimedSignal(timeoutMs, options.signal);
    fetch(url, { signal: timed.signal }).then(function (res) {
        if (!res.ok) {
            return res.json().then(function (body) {
                callback(new Error(body.message || body.error || res.statusText));
            }, function () {
                callback(new Error(res.statusText || 'Request failed'));
            });
        }
        return res.json().then(function (data) {
            callback(null, data);
        }, function () {
            callback(new Error('Invalid response'));
        });
    }).catch(function (err) {
        callback(err && err.message ? err : new Error(String(err)));
    }).finally(function () {
        timed.cleanup();
    });
}

/**
 * Send a query to the CineMind backend. Returns parsed JSON on success; throws on error.
 * Applies an AbortController timeout of SEND_TIMEOUT_MS (overrideable).
 */
export async function sendQuery(text, useRealAgent, options) {
    options = options || {};
    const timeoutMs = (options && typeof options.timeoutMs === 'number' && options.timeoutMs > 0)
        ? options.timeoutMs
        : SEND_TIMEOUT_MS;
    const timed = _buildTimedSignal(timeoutMs, options.signal);
    let response;
    const payload = {
        user_query: text,
        requestedAgentMode: useRealAgent ? 'REAL_AGENT' : 'PLAYGROUND'
    };
    if (options.hubConversationHistory && Array.isArray(options.hubConversationHistory) && options.hubConversationHistory.length > 0) {
        payload.hubConversationHistory = options.hubConversationHistory;
    }
    try {
        response = await fetch(API_BASE + '/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: timed.signal
        });
    } finally {
        timed.cleanup();
    }
    if (!response.ok) {
        let errMsg = 'HTTP ' + response.status;
        try {
            const errBody = await response.json();
            if (errBody && errBody.detail) {
                if (typeof errBody.detail === 'string') errMsg = errBody.detail;
                else if (errBody.detail.error) errMsg = errBody.detail.error;
            }
        } catch (_) { /* ignore */ }
        throw new Error(errMsg);
    }
    let result;
    try {
        result = await response.json();
    } catch (e) {
        throw new Error('Invalid response from server');
    }
    return result;
}

/**
 * Fetch similar movies clusters for Movie Hub fallback.
 * Calls GET /api/movies/{movie_id}/similar and returns parsed JSON.
 *
 * Path `movie_id` is normally the TMDB id. If missing, pass a non-numeric placeholder (`_`)
 * and `title` (optional `year`) so the backend can resolve TMDB id via `build_similar_movie_clusters`.
 * Always pass `title`/`year` when available so cluster labels match the anchor movie.
 *
 * @param {string|number|null|undefined} tmdbId - TMDB id, or null/undefined for title-only resolve
 * @param {object} [options]
 * @param {number} [options.timeoutMs]
 * @param {string} [options.title] - anchor title (for labels + id resolve when tmdbId absent)
 * @param {number} [options.year]
 * @param {string} [options.mediaType]
 */
export async function fetchSimilarMovies(tmdbId, options) {
    options = options || {};
    const timeoutMs = (options && typeof options.timeoutMs === 'number' && options.timeoutMs > 0)
        ? options.timeoutMs
        : 12000;
    const timed = _buildTimedSignal(timeoutMs, options.signal);
    try {
        const raw = tmdbId != null ? String(tmdbId).trim() : '';
        const hasNumericId = raw !== '' && /^\d+$/.test(raw);
        // Non-numeric path segment ⇒ backend uses title/year to resolve TMDB id (see build_similar_movie_clusters).
        const pathSeg = hasNumericId ? raw : '_';
        const titleOpt = options.title != null ? String(options.title).trim() : '';
        if (!hasNumericId && !titleOpt) {
            throw new Error('tmdbId or title is required for similar movies');
        }
        const params = new URLSearchParams();
        params.set('by', 'genre');
        if (titleOpt) params.set('title', titleOpt);
        if (options.year != null && options.year !== '' && !isNaN(Number(options.year))) {
            params.set('year', String(Number(options.year)));
        }
        const mt = options.mediaType && String(options.mediaType).trim();
        if (mt) params.set('mediaType', mt);
        const url = API_BASE + '/api/movies/' + encodeURIComponent(pathSeg) + '/similar?' + params.toString();
        const res = await fetch(url, { method: 'GET', signal: timed.signal });
        if (!res.ok) {
            let msg = res.statusText || 'Request failed';
            try {
                const body = await res.json();
                msg = (body && (body.detail || body.message)) ? (body.detail || body.message) : msg;
            } catch (_) { /* ignore */ }
            throw new Error(msg);
        }
        return await res.json();
    } finally {
        timed.cleanup();
    }
}

async function _requestJson(path, options) {
    options = options || {};
    const timeoutMs = (typeof options.timeoutMs === 'number' && options.timeoutMs > 0)
        ? options.timeoutMs
        : 12000;
    const timed = _buildTimedSignal(timeoutMs, options.signal);
    try {
        const res = await fetch(API_BASE + path, {
            method: options.method || 'GET',
            headers: options.headers || {},
            body: options.body || undefined,
            signal: timed.signal
        });
        if (!res.ok) {
            let msg = res.statusText || ('HTTP ' + res.status);
            try {
                const body = await res.json();
                msg = (body && (body.detail || body.message || body.error))
                    ? (body.detail || body.message || body.error)
                    : msg;
            } catch (_) { /* ignore */ }
            throw new Error(msg);
        }
        if (res.status === 204) return null;
        return await res.json();
    } finally {
        timed.cleanup();
    }
}

export async function getProjects(options) {
    return _requestJson('/api/projects', options);
}

export async function createProject(payload, options) {
    return _requestJson('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
        timeoutMs: options && options.timeoutMs,
        signal: options && options.signal
    });
}

export async function getProject(projectId, options) {
    return _requestJson('/api/projects/' + encodeURIComponent(projectId), options);
}

export async function addProjectAssets(projectId, assets, options) {
    return _requestJson('/api/projects/' + encodeURIComponent(projectId) + '/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assets: Array.isArray(assets) ? assets : [] }),
        timeoutMs: options && options.timeoutMs,
        signal: options && options.signal
    });
}

export async function deleteProjectAsset(projectId, assetRef, options) {
    return _requestJson('/api/projects/' + encodeURIComponent(projectId) + '/assets/' + encodeURIComponent(assetRef), {
        method: 'DELETE',
        timeoutMs: options && options.timeoutMs,
        signal: options && options.signal
    });
}
