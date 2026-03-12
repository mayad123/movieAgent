/** @module api — API client for CineMind backend calls. */

import { API_BASE, SEND_TIMEOUT_MS } from './state.js';

/**
 * Call GET /api/watch/where-to-watch and pass normalized result to callback.
 * movie: { title, year?, pageUrl?, pageId?, tmdbId?, mediaType? }.
 * Uses tmdbId when present; otherwise title+year (backend does Watchmode name lookup).
 */
export function fetchWhereToWatch(movie, callback) {
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
    fetch(url).then(function (res) {
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
    });
}

/**
 * Send a query to the CineMind backend. Returns parsed JSON on success; throws on error.
 * Applies an AbortController timeout of SEND_TIMEOUT_MS.
 */
export async function sendQuery(text, useRealAgent) {
    const controller = new AbortController();
    const timeoutId = setTimeout(function () { controller.abort(); }, SEND_TIMEOUT_MS);
    let response;
    try {
        response = await fetch(API_BASE + '/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_query: text,
                requestedAgentMode: useRealAgent ? 'REAL_AGENT' : 'PLAYGROUND'
            }),
            signal: controller.signal
        });
    } finally {
        clearTimeout(timeoutId);
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
