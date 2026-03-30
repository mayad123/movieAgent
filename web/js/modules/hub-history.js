/** @module hub-history — Pure helpers for sub-context Movie Hub multi-turn state. */

/**
 * Deep clone hub cluster array (JSON-safe).
 * @param {unknown} clusters
 * @returns {Array|null}
 */
export function cloneMovieHubClusters(clusters) {
    if (!Array.isArray(clusters)) return null;
    try {
        return JSON.parse(JSON.stringify(clusters));
    } catch (e) {
        return null;
    }
}

/**
 * Build { role, content }[] for API hubConversationHistory from messages before index `endExclusive`.
 * @param {Array<{ role: string, content?: string }>} messages
 * @param {number} endExclusive
 * @returns {{ role: string, content: string }[]}
 */
export function buildHubConversationHistory(messages, endExclusive) {
    const out = [];
    if (!Array.isArray(messages)) return out;
    const end = Math.min(endExclusive, messages.length);
    let i;
    for (i = 0; i < end; i++) {
        const m = messages[i];
        if (!m || (m.role !== 'user' && m.role !== 'assistant')) continue;
        const content = m.content != null ? String(m.content) : '';
        out.push({ role: m.role, content: content });
    }
    return out;
}

/**
 * Flatten cluster movies to "Title (Year)" strings (same contract as messages.sendMessage).
 * @param {Array<{ kind?: string, movies?: object[] }>} movieHubClusters
 * @returns {string[]}
 */
export function candidateTitlesFromClusters(movieHubClusters) {
    const dedupedClusters = dedupeMovieHubClusters(movieHubClusters);
    const titles = [];
    if (!Array.isArray(dedupedClusters)) return titles;
    dedupedClusters.forEach(function (cl) {
        const ms = (cl && Array.isArray(cl.movies)) ? cl.movies : [];
        ms.forEach(function (m) {
            if (!m || typeof m !== 'object') return;
            const title = (m.movie_title != null ? m.movie_title : m.title != null ? m.title : '').toString().trim();
            if (!title) return;
            let year = m.year;
            if (year == null && m.release_date) {
                const mYear = /^(\d{4})/.exec(String(m.release_date));
                year = mYear && mYear[1] ? mYear[1] : null;
            }
            const yearNum = year != null ? parseInt(String(year), 10) : NaN;
            if (!isNaN(yearNum) && yearNum > 0) {
                titles.push(title + ' (' + yearNum + ')');
            } else {
                titles.push(title);
            }
        });
    });
    return titles.filter(function (s) { return !!s && !!String(s).trim(); });
}

function _normalizeTitle(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

function _normalizeYear(value) {
    if (value == null) return null;
    const n = parseInt(String(value), 10);
    if (isNaN(n) || n < 1800 || n > 2100) return null;
    return n;
}

function _movieHubKey(movie) {
    if (!movie || typeof movie !== 'object') return null;
    const rawTmdb = movie.tmdbId != null ? movie.tmdbId : movie.tmdb_id;
    if (rawTmdb != null) {
        const tmdb = parseInt(String(rawTmdb), 10);
        if (!isNaN(tmdb)) return 'tmdb:' + String(tmdb);
    }
    const title = _normalizeTitle(movie.movie_title != null ? movie.movie_title : movie.title);
    if (!title) return null;
    const year = _normalizeYear(movie.year);
    if (year != null) return 'title_year:' + title + '|' + String(year);
    return 'title:' + title;
}

/**
 * Remove duplicate movies from hub clusters while preserving order.
 * Canonical key priority: tmdbId -> title+year -> title.
 * @param {Array<{ kind?: string, label?: string, movies?: object[] }>} clusters
 * @param {{ maxTotal?: number }} [options]
 * @returns {Array}
 */
export function dedupeMovieHubClusters(clusters, options) {
    if (!Array.isArray(clusters)) return [];
    const maxTotal = options && Number.isInteger(options.maxTotal) && options.maxTotal > 0
        ? options.maxTotal
        : 20;
    const seen = new Set();
    const out = [];
    let total = 0;
    clusters.forEach(function (cluster) {
        if (!cluster || typeof cluster !== 'object' || total >= maxTotal) return;
        const movies = Array.isArray(cluster.movies) ? cluster.movies : [];
        const kept = [];
        movies.forEach(function (movie) {
            if (!movie || typeof movie !== 'object' || total >= maxTotal) return;
            const key = _movieHubKey(movie);
            if (key && seen.has(key)) return;
            if (key) seen.add(key);
            kept.push(movie);
            total += 1;
        });
        if (kept.length > 0) {
            out.push(Object.assign({}, cluster, { movies: kept }));
        }
    });
    return out;
}
