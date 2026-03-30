/** @module layout — Sidebar, header, right panel, conversation list, and toast notifications. */

import {
    sidebar, sidebarToggle, rightPanel, rightPanelToggle,
    conversationList, conversationTitle, headerMainView, headerSubView,
    headerBreadcrumb, subConversationMovieBadge, mainEl,
    movieHubView, movieHubSelectedPoster, movieHubSelectedTitle, movieHubSelectedTagline,
    movieHubResetBtn, movieHubRetrieving, movieHubSimilarByGenre, movieHubSimilarByTone, movieHubSimilarByCast,
    chatColumn, messageList, composerInput, retrievingRow, newChatBtn,
    projectsPageBtn, useRealAgentToggle, modeBadge, app,
    headerBackBtn, headerSubRenameBtn, headerSubCloseBtn
} from './dom.js';

import {
    appState, getActiveConversation, getActiveThread, nextId, getActiveMovieContext
} from './state.js';
import { renderSimilarCluster, createHeroCard } from './posters.js';
import { sendQuery, prefixMovieHubContextQuery, fetchSimilarMovies, getProjects, getProject, deleteProjectAsset } from './api.js';
import { cloneMovieHubClusters, buildHubConversationHistory, candidateTitlesFromClusters, dedupeMovieHubClusters } from './hub-history.js';

/* ── Callback registry (breaks circular deps with chat/collection modules) ── */

let _renderMessages = null;
let _renderCollectionPanel = null;
let _addSubConversationFromPoster = null;

export function setLayoutCallbacks({ renderMessages, renderCollectionPanel, addSubConversationFromPoster }) {
    _renderMessages = renderMessages;
    _renderCollectionPanel = renderCollectionPanel;
    _addSubConversationFromPoster = addSubConversationFromPoster;
}

/* ── Module-level state ── */

let stackNavigationState = null;
let activeHubAutoLoadController = null;
let activeHubFallbackController = null;

function _cfgNumber(key, fallback) {
    try {
        const cfg = (window && window.CINEMIND_CONFIG) ? window.CINEMIND_CONFIG : {};
        const raw = cfg[key];
        const n = Number(raw);
        return Number.isFinite(n) ? n : fallback;
    } catch (_) {
        return fallback;
    }
}

function abortActiveHubRequests() {
    if (activeHubAutoLoadController) {
        try { activeHubAutoLoadController.abort(); } catch (_) { /* ignore */ }
        activeHubAutoLoadController = null;
    }
    if (activeHubFallbackController) {
        try { activeHubFallbackController.abort(); } catch (_) { /* ignore */ }
        activeHubFallbackController = null;
    }
}

const filmIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></svg>';

/* ── Toast helpers ── */

export function showSavedToCollectionToast() {
    const el = document.getElementById('rightPanelSavedToast');
    if (!el) return;
    el.textContent = 'Added to Collection';
    el.classList.add('is-visible');
    clearTimeout(showSavedToCollectionToast._hideId);
    showSavedToCollectionToast._hideId = setTimeout(() => {
        el.classList.remove('is-visible');
    }, 2500);
}

export function showSavedToProjectToast(projectName) {
    const el = document.getElementById('rightPanelSavedToast');
    if (!el) return;
    el.textContent = 'Saved to ' + (projectName || 'Project');
    el.classList.add('is-visible');
    clearTimeout(showSavedToProjectToast._hideId);
    showSavedToProjectToast._hideId = setTimeout(() => {
        el.classList.remove('is-visible');
    }, 2500);
}

export function showAlreadyAddedToast() {
    const el = document.getElementById('rightPanelSavedToast');
    if (!el) return;
    el.textContent = 'Already Added';
    el.classList.add('is-visible');
    clearTimeout(showAlreadyAddedToast._hideId);
    showAlreadyAddedToast._hideId = setTimeout(() => {
        el.classList.remove('is-visible');
    }, 2000);
}

export function showFallbackToast(message) {
    const el = document.getElementById('rightPanelSavedToast');
    if (!el) return;
    el.textContent = message && message.length > 60 ? message.slice(0, 57) + '\u2026' : (message || 'Switched to Playground.');
    el.classList.add('is-visible', 'toast-fallback');
    clearTimeout(showFallbackToast._hideId);
    showFallbackToast._hideId = setTimeout(() => {
        el.classList.remove('is-visible', 'toast-fallback');
    }, 4500);
}

/* ── Right-panel open + collection scroll ── */

export function openRightPanelToCollection() {
    if (rightPanel && rightPanel.classList.contains('collapsed')) {
        rightPanel.classList.remove('collapsed');
        app.classList.add('right-panel-open');
    }
    const collectionEl = document.getElementById('collectionList');
    if (collectionEl) {
        setTimeout(() => {
            collectionEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 80);
    }
    showSavedToCollectionToast();
}

/* ── Sidebar / right-panel toggles ── */

export function toggleSidebar() {
    sidebar.classList.toggle('collapsed');
    app.classList.toggle('sidebar-collapsed', sidebar.classList.contains('collapsed'));
}

export function toggleRightPanel() {
    if (rightPanel) rightPanel.classList.toggle('collapsed');
    app.classList.toggle('right-panel-open', rightPanel && !rightPanel.classList.contains('collapsed'));
}

/* ── Conversation management ── */

export function addConversation() {
    const id = nextId();
    appState.conversations.unshift({
        id,
        title: 'New conversation',
        messages: [],
        collection: [],
        activeScope: 'This Conversation',
        subConversations: []
    });
    appState.activeConversationId = id;
    appState.activeSubConversationId = null;
    appState.conversationView = 'main';
    appState.lastViewByConversationId[id] = { view: 'main', subId: null };
    if (composerInput) composerInput.value = '';
    updateConversationList();
    if (_renderMessages) _renderMessages();
    if (_renderCollectionPanel) _renderCollectionPanel();
    updateHeaderForView();
    updateRightPanelScope();
    if (composerInput) composerInput.focus();
}

export function switchConversation(mainId, subId) {
    if (mainId === appState.activeConversationId
        && (subId == null ? !appState.activeSubConversationId : subId === appState.activeSubConversationId)) return;
    if (appState.conversationView === 'main' && chatColumn && appState.activeConversationId) {
        appState.mainScrollTopByConversationId[appState.activeConversationId] = chatColumn.scrollTop;
    }
    appState.activeConversationId = mainId;
    abortActiveHubRequests();
    if (subId != null && subId !== '') {
        appState.activeSubConversationId = subId;
        appState.conversationView = 'sub';
        appState.lastViewByConversationId[mainId] = { view: 'sub', subId };
    } else {
        appState.activeSubConversationId = null;
        appState.conversationView = 'main';
    }
    // After active sub/main view is updated so hide/show targets the right thread.
    hideRetrieving();
    appState.restoreScrollTop = (appState.conversationView === 'main')
        ? (appState.mainScrollTopByConversationId[mainId] != null ? appState.mainScrollTopByConversationId[mainId] : null)
        : null;
    updateConversationList();
    if (_renderMessages) _renderMessages();
    if (_renderCollectionPanel) _renderCollectionPanel();
    updateHeaderForView();
    updateRightPanelScope();
    // Entering a sub from the sidebar does not run addSubConversationFromPoster; resume hub load if it never finished.
    if (appState.conversationView === 'sub') {
        const t = getActiveThread();
        const s = t && t.sub;
        if (s && s.contextMovie && !s._hubClustersLoaded && !s._hubClustersLoading) {
            void maybeAutoLoadMovieHubClusters(s);
        }
    }
}

export function addSubConversationFromPoster(movie) {
    const main = getActiveConversation();
    if (!main || !movie || !String(movie.title || '').trim()) return;
    const title = String(movie.title).trim();
    const subTitle = 'Re: ' + title + (movie.year != null ? ' (' + movie.year + ')' : '');
    // Do not pass `movie.relatedMovies` into the sub: attachment code attaches the *parent
    // message’s full candidate universe* to every poster for hub filtering — that list is
    // not “similar to the clicked movie.” Hub rows come from `maybeAutoLoadMovieHubClusters`
    // / TMDB similar for this title’s `tmdbId` (see docs/errors/MOVIE_HUB_AND_SUBCONTEXT.md).
    const contextMovie = {
        title,
        year: movie.year,
        pageUrl: (movie.pageUrl && String(movie.pageUrl).trim()) || undefined,
        pageId: (movie.pageId && String(movie.pageId).trim()) || undefined,
        imageUrl: (movie.imageUrl && String(movie.imageUrl).trim()) || undefined,
        tmdbId: movie.tmdbId || movie.tmdb_id || undefined,
        mediaType: movie.mediaType || movie.media_type || undefined
    };
    const sub = {
        id: nextId(),
        title: subTitle,
        contextMovie,
        messages: []
    };
    if (!main.subConversations) main.subConversations = [];
    main.subConversations.unshift(sub);
    if (appState.conversationView === 'main' && chatColumn) {
        appState.mainScrollTopByConversationId[main.id] = chatColumn.scrollTop;
    }
    appState.activeSubConversationId = sub.id;
    abortActiveHubRequests();
    hideRetrieving();
    appState.conversationView = 'sub';
    appState.lastViewByConversationId[main.id] = { view: 'sub', subId: sub.id };
    updateConversationList();
    if (_renderMessages) _renderMessages();
    if (_renderCollectionPanel) _renderCollectionPanel();
    updateHeaderForView();
    updateRightPanelScope();

    // Auto-load hub clusters (LLM-driven) for this sub-context.
    // This keeps the hub aligned with the design goal: 20+ similar titles grouped by genre.
    void maybeAutoLoadMovieHubClusters(sub);

    if (composerInput) composerInput.focus();
}

function getHubContextLabel(movie) {
    if (!movie) return '';
    const title = movie.title && String(movie.title).trim();
    const year = movie.year != null ? String(movie.year) : '';
    return year ? (title || '') + ' (' + year + ')' : (title || '');
}

function clearHubContainers() {
    if (movieHubSimilarByGenre) movieHubSimilarByGenre.classList.add('hidden');
    if (movieHubSimilarByTone) movieHubSimilarByTone.classList.add('hidden');
    if (movieHubSimilarByCast) movieHubSimilarByCast.classList.add('hidden');
    if (movieHubSelectedTagline) movieHubSelectedTagline.classList.remove('hidden');
}

/** Strip cluster poster rows only (context mini-hero unchanged). Used while hub loads. */
function clearHubPosterStripsForLoading() {
    if (movieHubSimilarByGenre) {
        movieHubSimilarByGenre.innerHTML = '';
        movieHubSimilarByGenre.classList.add('hidden');
    }
    if (movieHubSimilarByTone) {
        movieHubSimilarByTone.innerHTML = '';
        movieHubSimilarByTone.classList.add('hidden');
    }
    if (movieHubSimilarByCast) {
        movieHubSimilarByCast.innerHTML = '';
        movieHubSimilarByCast.classList.add('hidden');
    }
}

function setMovieHubUpdating(isUpdating) {
    if (!movieHubRetrieving) return;
    movieHubRetrieving.classList.toggle('hidden', !isUpdating);
    if (appState.conversationView !== 'sub') return;
    if (isUpdating) {
        clearHubPosterStripsForLoading();
    } else {
        const thread = getActiveThread();
        if (thread && thread.sub) updateMovieHub(thread);
    }
}

async function maybeAutoLoadMovieHubClusters(sub) {
    if (!sub || !sub.contextMovie) return;
    if (sub._hubClustersLoading || sub._hubClustersLoaded) return;

    // If the context changes while the request is in-flight, ignore stale results.
    const requestedSubId = sub.id;
    let scheduleBackfill = false;
    sub._hubClustersLoading = true;
    setMovieHubUpdating(true);

    const contextLabel = getHubContextLabel(sub.contextMovie);
    const anchorText = contextLabel ? contextLabel : 'this movie';

    const maxAttempts = Math.max(1, Math.min(5, Math.floor(_cfgNumber('hubAutoMaxAttempts', 2))));
    const minRequiredGenreMovies = Math.max(1, Math.min(20, Math.floor(_cfgNumber('hubMinInitialRenderMovies', 10))));
    const targetGenreMovies = 20; // prefer full set
    sub._hubClustersAttempts = (sub._hubClustersAttempts || 0) + 1;
    const attempt = sub._hubClustersAttempts;

    const priorMovies = (sub._hubClustersLastPayload && Array.isArray(sub._hubClustersLastPayload) ? sub._hubClustersLastPayload : []);
    const priorAvoidSet = new Set();
    const priorTmdbSet = new Set();
    (priorMovies || []).forEach(function (c) {
        if (!c || String(c.kind || '').toLowerCase() !== 'genre') return;
        const movies = c.movies;
        if (!Array.isArray(movies)) return;
        movies.forEach(function (m) {
            if (!m) return;
            const t = (m.title || m.movie_title || '').toString().trim();
            if (!t) return;
            const key = t.toLowerCase();
            if (!priorAvoidSet.has(key) && priorAvoidSet.size < 20) priorAvoidSet.add(key);

            const tmdbIdRaw = (m.tmdbId != null ? m.tmdbId : (m.tmdb_id != null ? m.tmdb_id : null));
            if (tmdbIdRaw != null) {
                const tmdbIdNum = parseInt(String(tmdbIdRaw), 10);
                if (!isNaN(tmdbIdNum) && tmdbIdNum > 0) priorTmdbSet.add(tmdbIdNum);
            }
        });
    });

    const avoidLine = (attempt > 1 && priorAvoidSet.size > 0)
        ? ('Avoid repeating any of these titles from previous attempts: ' + Array.from(priorAvoidSet).slice(0, 20).join('; '))
        : '';

    const prompt = [
        'Show 20 movies similar to ' + anchorText + ' grouped by genre.',
        'Return exactly 4 genre categories.',
        'Return ONLY the genre blocks. No extra commentary. No markdown.',
        'Prefer variety across genres and themes.',
        avoidLine,
        'For each category:',
        '- Start with a line: Genre: <GenreName>',
        '- Then provide 5 numbered lines formatted exactly as: "1. Title (Year)"',
        'Total titles: 20.'
    ].filter(Boolean).join('\n');

    const outgoingText = prefixMovieHubContextQuery(prompt, sub.contextMovie);
    let didApply = false;
    let markLoaded = false;

    // Count movie cards that should render in the genre cluster.
    // We count by non-empty title (not unique tmdbId) so the "20+ titles" UX
    // stays consistent even when some titles don't resolve cleanly or include
    // repeated movies.
    function countValidGenreMovies(movieHubClusters) {
        let genreMovies = 0;
        (movieHubClusters || []).forEach(function (c) {
            if (!c) return;
            if (String(c.kind || '').toLowerCase() !== 'genre') return;
            if (!Array.isArray(c.movies)) return;
            c.movies.forEach(function (m) {
                if (!m) return;
                const title = (m.title || m.movie_title || '').toString().trim();
                if (!title) return;
                genreMovies += 1;
            });
        });
        return genreMovies;
    }

        try {
            // Fast path: use PLAYGROUND for the automatic hub population to keep latency low.
            // If we fail to get usable `movieHubClusters`, retry with the Real Agent (when enabled)
            // so the LLM can reliably follow the genre-bucket formatting contract.
            const hubTimeoutMs = Math.max(1000, Math.floor(_cfgNumber('hubAutoQueryTimeoutMs', 12000)));
            // Real Agent hub retries can be expensive; only try it once (on the first retry)
            // to avoid starving other UI features like "Where to Watch".
            const useRealAgentForHub = (attempt === 2 && appState && appState.useRealAgent) ? true : false;
            abortActiveHubRequests();
            activeHubAutoLoadController = new AbortController();
            const result = await sendQuery(outgoingText, useRealAgentForHub, {
                timeoutMs: hubTimeoutMs,
                signal: activeHubAutoLoadController.signal
            });
            activeHubAutoLoadController = null;
        // Only apply if user is still on the same sub-conversation.
        if (appState.activeSubConversationId !== requestedSubId) return;
        if (!(result && Array.isArray(result.movieHubClusters))) {
            throw new Error('movieHubClusters missing or invalid');
        }

        // On retries, enforce "next set differs from original" by filtering out
        // anything already returned in the previous attempt.
        let clustersForApply = result.movieHubClusters;
        if (attempt > 1 && priorAvoidSet.size > 0) {
            clustersForApply = (result.movieHubClusters || []).map(function (cl) {
                if (!cl || String(cl.kind || '').toLowerCase() !== 'genre') return cl;
                const movies = Array.isArray(cl.movies) ? cl.movies : [];
                const filteredMovies = movies.filter(function (m) {
                    if (!m) return false;
                    const title = (m.title || m.movie_title || '').toString().trim();
                    const titleKey = title ? title.toLowerCase() : '';
                    const tmdbIdRaw = (m.tmdbId != null ? m.tmdbId : (m.tmdb_id != null ? m.tmdb_id : null));
                    const tmdbIdNum = tmdbIdRaw != null ? parseInt(String(tmdbIdRaw), 10) : NaN;
                    const tmdbAlreadyUsed = !isNaN(tmdbIdNum) && tmdbIdNum > 0 && priorTmdbSet.has(tmdbIdNum);
                    const titleAlreadyUsed = titleKey && priorAvoidSet.has(titleKey);
                    return !(tmdbAlreadyUsed || titleAlreadyUsed);
                });
                return Object.assign({}, cl, { movies: filteredMovies });
            });
        }

        // Keep last payload so we can render partial results if threshold isn't met.
        sub._hubClustersLastPayload = clustersForApply;

        // Must satisfy the hub contract: 20+ titles grouped by genre.
        const validGenreMovies = countValidGenreMovies(clustersForApply);

        if (validGenreMovies >= minRequiredGenreMovies) {
            // Threshold met: replace loading sign with actual movie posters.
            applyMovieHubClusters(clustersForApply);
            didApply = true;
            sub._hubClustersHasRendered = true;

            if (validGenreMovies >= targetGenreMovies) {
                markLoaded = true;
            } else if (attempt < maxAttempts) {
                // Backfill: keep "Updating hub" on and poster rows empty until the next attempt finishes.
                scheduleBackfill = true;
                setMovieHubUpdating(true);
                const backfillDelayMs = Math.max(150, Math.floor(_cfgNumber('hubAutoBackfillDelayMs', 1000)));
                setTimeout(function () {
                    if (sub && appState.activeSubConversationId === requestedSubId && !sub._hubClustersLoading && !sub._hubClustersLoaded) {
                        void maybeAutoLoadMovieHubClusters(sub);
                    }
                }, backfillDelayMs);
            } else {
                // Retries exhausted: render whatever we have.
                markLoaded = true;
            }
        } else if (attempt < maxAttempts) {
            // Keep loading sign active; retry until threshold is met or attempts complete.
            throw new Error('hub too few valid movies: ' + String(validGenreMovies));
        } else {
            // Retries exhausted with too-few titles. Route through catch so the TMDB
            // fallback path runs before we settle on sparse clusters.
            throw new Error('hub insufficient on final attempt: ' + String(validGenreMovies));
        }
    } catch (e) {
        activeHubAutoLoadController = null;
        const shouldTryEarlyFallback = attempt === 1;
        if (shouldTryEarlyFallback) {
            const thread = getActiveThread();
            const m = sub && sub.contextMovie ? sub.contextMovie : null;
            const tmdbId = m ? (m.tmdbId != null ? m.tmdbId : m.tmdb_id) : null;
            const canTrySimilar = thread && thread.sub && thread.sub.id === requestedSubId && m
                && (tmdbId != null && String(tmdbId).trim() !== '' || (m.title && String(m.title).trim()));
            if (canTrySimilar) {
                try {
                    activeHubFallbackController = new AbortController();
                    const sim = await fetchSimilarMovies(tmdbId, {
                        timeoutMs: 8000,
                        title: m.title,
                        year: m.year != null ? m.year : undefined,
                        mediaType: m.mediaType || m.media_type || 'movie',
                        signal: activeHubFallbackController.signal
                    });
                    activeHubFallbackController = null;
                    const clusters = sim && (sim.clusters || sim.movieHubClusters);
                    if (Array.isArray(clusters) && countValidGenreMovies(clusters) >= minRequiredGenreMovies) {
                        applyMovieHubClusters(clusters);
                        sub._hubClustersHasRendered = true;
                        didApply = true;
                        // Keep trying in background for richer clusters when we have attempts left.
                        if (attempt < maxAttempts) {
                            const backfillDelayMs = Math.max(150, Math.floor(_cfgNumber('hubAutoBackfillDelayMs', 1000)));
                            setTimeout(function () {
                                if (sub && appState.activeSubConversationId === requestedSubId && !sub._hubClustersLoading && !sub._hubClustersLoaded) {
                                    void maybeAutoLoadMovieHubClusters(sub);
                                }
                            }, backfillDelayMs);
                        } else {
                            markLoaded = true;
                        }
                        return;
                    }
                } catch (_) {
                    activeHubFallbackController = null;
                }
            }
        }
        // Silent failure; mini-hero remains visible.
        if (attempt < maxAttempts) {
            // Retry after a short delay; transient LLM/network/TMDB timing issues are expected.
            const retryDelayMs = Math.max(150, Math.floor(_cfgNumber('hubAutoRetryDelayMs', 500)));
            setTimeout(function () {
                // Re-check: if we've switched to another sub, do nothing.
                if (sub && appState.activeSubConversationId === requestedSubId) {
                    // Reset per-attempt flags; keep _hubClustersLoaded false so we can retry.
                    sub._hubClustersLoading = false;
                    void maybeAutoLoadMovieHubClusters(sub);
                }
            }, retryDelayMs);
        } else {
            // Retries exhausted: prefer TMDB similar-movies API (`build_similar_movie_clusters`).
            // Pass title/year/mediaType so labels match the anchor; if tmdbId is missing, path `_` + title resolves id.
            const thread = getActiveThread();
            const m = sub && sub.contextMovie ? sub.contextMovie : null;
            const tmdbId = m ? (m.tmdbId != null ? m.tmdbId : m.tmdb_id) : null;
            const canTrySimilar = thread && thread.sub && thread.sub.id === requestedSubId && m
                && (tmdbId != null && String(tmdbId).trim() !== '' || (m.title && String(m.title).trim()));
            if (canTrySimilar) {
                try {
                    activeHubFallbackController = new AbortController();
                    const sim = await fetchSimilarMovies(tmdbId, {
                        timeoutMs: 12000,
                        title: m.title,
                        year: m.year != null ? m.year : undefined,
                        mediaType: m.mediaType || m.media_type || 'movie',
                        signal: activeHubFallbackController.signal
                    });
                    activeHubFallbackController = null;
                    const clusters = sim && (sim.clusters || sim.movieHubClusters);
                    if (Array.isArray(clusters) && clusters.length) {
                        applyMovieHubClusters(clusters);
                        sub._hubClustersHasRendered = true;
                        sub._hubClustersLoaded = true;
                        return;
                    }
                } catch (_) {
                    activeHubFallbackController = null;
                    /* ignore */
                }
            }
            if (thread && thread.sub && thread.sub.id === requestedSubId) {
                updateMovieHub(thread);
                sub._hubClustersLoaded = true;
            }
        }
    } finally {
        activeHubAutoLoadController = null;
        activeHubFallbackController = null;
        sub._hubClustersLoading = false;
        if (didApply && markLoaded) sub._hubClustersLoaded = true;
        // Only touch the shared DOM indicator if this invocation still owns the active sub.
        // Otherwise a stale finally run can hide the spinner during the new sub's load or leave it stuck on after a switch.
        if (appState.activeSubConversationId === requestedSubId && !scheduleBackfill) {
            setMovieHubUpdating(false);
        }
    }
}

/* ── Header ── */

export function updateHeaderTitle() {
    const thread = getActiveThread();
    if (conversationTitle) conversationTitle.textContent = thread.title || 'New conversation';
}

export function updateHeaderForView() {
    if (!headerMainView || !headerSubView) return;
    if (mainEl) mainEl.classList.toggle('sub-conversation-view', appState.conversationView === 'sub');
    if (appState.conversationView === 'sub') {
        headerMainView.classList.add('hidden');
        headerSubView.classList.remove('hidden');
        const thread = getActiveThread();
        const main = getActiveConversation();
        const parentName = (main && main.title) ? main.title : 'New conversation';
        const movieLabel = thread.sub && thread.sub.contextMovie
            ? (thread.sub.contextMovie.title || '') + (thread.sub.contextMovie.year != null ? ' (' + thread.sub.contextMovie.year + ')' : '')
            : (thread.title || '');
        if (headerBreadcrumb) headerBreadcrumb.textContent = parentName + ' \u2192 ' + (movieLabel || 'Sub');
        updateMovieHub(thread);
        if (subConversationMovieBadge) {
            subConversationMovieBadge.classList.remove('hidden');
            subConversationMovieBadge.setAttribute('aria-hidden', 'false');
            const movie = thread.sub && thread.sub.contextMovie;
            const imgUrl = movie && movie.imageUrl && String(movie.imageUrl).trim();
            if (imgUrl) {
                const existing = subConversationMovieBadge.querySelector('img');
                if (existing) {
                    existing.src = imgUrl;
                } else {
                    const placeholder = subConversationMovieBadge.querySelector('.sub-conversation-badge-placeholder');
                    if (placeholder) placeholder.remove();
                    const img = document.createElement('img');
                    img.src = imgUrl;
                    img.alt = movie.title ? (movie.title + (movie.year != null ? ' (' + movie.year + ')' : '')) : 'Movie';
                    subConversationMovieBadge.appendChild(img);
                }
            } else {
                const im = subConversationMovieBadge.querySelector('img');
                if (im) im.remove();
                if (!subConversationMovieBadge.querySelector('.sub-conversation-badge-placeholder')) {
                    const span = document.createElement('span');
                    span.className = 'sub-conversation-badge-placeholder';
                    span.textContent = '\uD83C\uDFAC';
                    subConversationMovieBadge.appendChild(span);
                }
            }
        }
    } else {
        headerMainView.classList.remove('hidden');
        headerSubView.classList.add('hidden');
        const t = getActiveThread();
        if (conversationTitle) conversationTitle.textContent = t.title || 'New conversation';
        if (movieHubView) movieHubView.classList.add('hidden');
        if (messageList) messageList.classList.remove('hidden');
        if (subConversationMovieBadge) {
            subConversationMovieBadge.classList.add('hidden');
            subConversationMovieBadge.setAttribute('aria-hidden', 'true');
        }
    }
}

/**
 * Apply backend-produced Movie Hub clusters to the active sub-conversation.
 * This is used for question-driven narrowing within the same context movie anchor.
 *
 * @param {Array} movieHubClusters - Array of { kind, label, movies } clusters (same shape as /api/movies/{id}/similar)
 */
export function applyMovieHubClusters(movieHubClusters) {
    if (!Array.isArray(movieHubClusters)) return;
    if (appState.conversationView !== 'sub') return;

    const thread = getActiveThread();
    const sub = thread && thread.sub ? thread.sub : null;
    if (!sub) return;

    const dedupedClusters = dedupeMovieHubClusters(movieHubClusters, { maxTotal: 20 });
    if (!Array.isArray(dedupedClusters) || dedupedClusters.length === 0) return;

    // Replace the clusters used to render the hub.
    sub.similarClusters = dedupedClusters;

    // Baseline hub for reset / replay-after-delete (first non-empty apply only).
    if (!sub.hubOriginalClusters) {
        const titles = candidateTitlesFromClusters(dedupedClusters);
        if (titles.length > 0) {
            sub.hubOriginalClusters = cloneMovieHubClusters(dedupedClusters);
        }
    }

    renderMovieHubCluster(movieHubSimilarByGenre, dedupedClusters, 'genre');
    renderMovieHubCluster(movieHubSimilarByTone, dedupedClusters, 'tone');
    renderMovieHubCluster(movieHubSimilarByCast, dedupedClusters, 'cast');

    if (movieHubView) movieHubView.classList.remove('hidden');
    if (_renderMessages) _renderMessages();
}

/**
 * Re-apply hub filtering from remaining chat turns: start from hubOriginalClusters,
 * then sequentially POST each user→assistant pair (same contract as live send).
 * @param {object} sub — active sub-conversation
 * @param {boolean} useRealAgent
 * @returns {Promise<void>}
 */
export async function recomputeHubFromMessages(sub, useRealAgent) {
    if (!sub || !Array.isArray(sub.messages)) return;
    const orig = cloneMovieHubClusters(sub.hubOriginalClusters);
    if (!orig) return;
    applyMovieHubClusters(orig);
    const msgs = sub.messages;
    let i;
    for (i = 0; i < msgs.length; i++) {
        if (msgs[i].role !== 'user') continue;
        const assistant = msgs[i + 1];
        if (!assistant || assistant.role !== 'assistant') continue;
        const userText = msgs[i].content != null ? String(msgs[i].content) : '';
        if (!String(userText).trim()) {
            i++;
            continue;
        }
        const history = buildHubConversationHistory(msgs, i);
        const candidates = candidateTitlesFromClusters(sub.similarClusters);
        const outgoing = prefixMovieHubContextQuery(userText, sub.contextMovie, candidates);
        try {
            const result = await sendQuery(outgoing, useRealAgent, { hubConversationHistory: history });
            if (result && Array.isArray(result.movieHubClusters)) {
                applyMovieHubClusters(result.movieHubClusters);
                if (assistant.meta && typeof assistant.meta === 'object') {
                    const snap = cloneMovieHubClusters(result.movieHubClusters);
                    assistant.meta.hubSnapshot = snap;
                    assistant.meta.movieHubClusters = snap;
                }
            }
        } catch (e) {
            if (typeof console !== 'undefined' && console.warn) console.warn('Hub replay step failed', e);
        }
        i++;
    }
}

function getRelatedMoviesForHub(movie) {
    if (!movie) return [];
    if (Array.isArray(movie.relatedMovies)) return movie.relatedMovies;
    if (Array.isArray(movie.similar)) return movie.similar;
    return [];
}

function updateMovieHub(thread) {
    if (!movieHubView) return;
    const sub = thread && thread.sub;
    const movie = sub && sub.contextMovie;
    if (!sub || !movie) {
        movieHubView.classList.add('hidden');
        if (chatColumn) chatColumn.classList.remove('hidden');
        return;
    }

    const title = (movie.title && String(movie.title).trim()) || '';
    const year = movie.year != null ? String(movie.year) : '';
    const label = year ? (title + ' (' + year + ')') : title;
    if (movieHubSelectedTitle) {
        movieHubSelectedTitle.textContent = label || 'This movie';
    }
    if (movieHubSelectedPoster) {
        movieHubSelectedPoster.innerHTML = '';
        const imgUrl = movie.imageUrl && String(movie.imageUrl).trim();
        if (imgUrl) {
            const img = document.createElement('img');
            img.src = imgUrl;
            img.alt = label || 'Movie';
            img.loading = 'lazy';
            movieHubSelectedPoster.appendChild(img);
        }
    }
    if (movieHubSelectedTagline) {
        const tagline = (movie.tagline && String(movie.tagline).trim()) || '';
        movieHubSelectedTagline.textContent = tagline;
        movieHubSelectedTagline.classList.toggle('hidden', !tagline);
    }
    // Keep the chat column active but marked as non-empty so the hub sits above it.
    if (chatColumn) {
        chatColumn.classList.remove('empty');
    }

    // First try to reuse any related/similar movies already on the contextMovie.
    const hubMovies = getRelatedMoviesForHub(movie);
    if (hubMovies.length > 0) {
        const baseLabel = label && String(label).trim() ? label : 'This movie';
        sub.similarClusters = [{
            kind: 'genre',
            label: 'Similar by genre to ' + baseLabel,
            movies: hubMovies
        }];
        if (!sub.hubOriginalClusters && candidateTitlesFromClusters(sub.similarClusters).length > 0) {
            sub.hubOriginalClusters = cloneMovieHubClusters(sub.similarClusters);
        }
        renderMovieHubCluster(movieHubSimilarByGenre, sub.similarClusters, 'genre');
        // Tone/cast clusters are reserved for richer future data.
        if (movieHubSimilarByTone) movieHubSimilarByTone.classList.add('hidden');
        if (movieHubSimilarByCast) movieHubSimilarByCast.classList.add('hidden');
    } else if (!sub.similarClusters) {
        // No local related data yet; genre/tone/cast will be populated by the
        // LLM-driven auto-fetch on sub-context entry.
        if (movieHubSimilarByGenre) movieHubSimilarByGenre.classList.add('hidden');
        if (movieHubSimilarByTone) movieHubSimilarByTone.classList.add('hidden');
        if (movieHubSimilarByCast) movieHubSimilarByCast.classList.add('hidden');
    } else {
        const clusters = Array.isArray(sub.similarClusters) ? sub.similarClusters : [];
        if (!sub.hubOriginalClusters && candidateTitlesFromClusters(clusters).length > 0) {
            sub.hubOriginalClusters = cloneMovieHubClusters(clusters);
        }
        renderMovieHubCluster(movieHubSimilarByGenre, clusters, 'genre');
        renderMovieHubCluster(movieHubSimilarByTone, clusters, 'tone');
        renderMovieHubCluster(movieHubSimilarByCast, clusters, 'cast');
    }

    movieHubView.classList.remove('hidden');
}

function renderMovieHubCluster(container, clusters, kind) {
    if (!container) return;
    container.innerHTML = '';
    const matchingClusters = (clusters || []).filter(function (c) {
        return (c && String(c.kind || '').toLowerCase()) === kind;
    });

    if (!matchingClusters.length) {
        container.classList.add('hidden');
        return;
    }

    let anyRendered = false;

    matchingClusters.forEach(function (cluster) {
        if (!cluster || !Array.isArray(cluster.movies) || cluster.movies.length === 0) return;

        const titleText = cluster.label && String(cluster.label).trim()
            ? cluster.label
            : (kind === 'genre'
                ? 'Similar by genre'
                : kind === 'tone'
                    ? 'Similar by tone or theme'
                    : 'Similar by cast or crew');

        const titleEl = document.createElement('h3');
        titleEl.className = 'movie-hub-cluster-title';
        titleEl.textContent = titleText;
        container.appendChild(titleEl);

        const strip = document.createElement('div');
        strip.className = 'movie-hub-cluster-strip';

        cluster.movies.forEach(function (movie) {
            if (!movie) return;
            const card = createHeroCard({
                movie_title: movie.movie_title || movie.title,
                title: movie.title,
                year: movie.year,
                primary_image_url: movie.primary_image_url || movie.imageUrl,
                page_url: movie.page_url || movie.pageUrl,
                tmdbId: movie.tmdbId || movie.tmdb_id,
                mediaType: movie.mediaType || movie.media_type,
                // Ensure "Talk More About This" stays anchored to the same hub universe.
                relatedMovies: cluster.movies
            }, { link: true });
            if (card) strip.appendChild(card);
        });

        if (strip.children.length) {
            container.appendChild(strip);
            anyRendered = true;
        } else {
            // If a given cluster rendered no cards, remove its heading.
            if (titleEl && titleEl.parentNode === container) container.removeChild(titleEl);
        }
    });

    if (!anyRendered) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
}

/* ── Scope ── */

export function getScopeDisplayName(scope) {
    if (!scope || scope === 'This Conversation') return 'This Conversation';
    if (String(scope).indexOf('project:') === 0) {
        const id = String(scope).slice(8);
        for (let i = 0; i < appState.projects.length; i++) {
            if (appState.projects[i].id === id) return appState.projects[i].name;
        }
        return scope;
    }
    return scope;
}

export function updateRightPanelScope() {
    const scopeLabel = document.getElementById('rightPanelScope');
    const dropdown = document.getElementById('rightPanelDropdown');
    const conv = getActiveConversation();
    const scope = (conv && conv.activeScope != null && conv.activeScope !== '') ? conv.activeScope : 'This Conversation';
    if (conv && (conv.activeScope == null || conv.activeScope === '')) conv.activeScope = 'This Conversation';
    if (scopeLabel) scopeLabel.textContent = getScopeDisplayName(scope);
    if (dropdown) {
        dropdown.querySelectorAll('.right-panel-dropdown-item').forEach(btn => {
            const itemScope = btn.getAttribute('data-scope') || btn.textContent.trim();
            btn.classList.toggle('is-active', itemScope === scope);
        });
    }
    const isProjectScope = scope && String(scope).indexOf('project:') === 0;
    const projectId = isProjectScope ? String(scope).slice(8) : '';
    const collectionsEl = document.getElementById('collectionList');
    const projectAssetsEl = document.getElementById('rightPanelProjectAssets');
    if (collectionsEl) collectionsEl.classList.toggle('hidden', isProjectScope);
    if (projectAssetsEl) projectAssetsEl.classList.toggle('hidden', !isProjectScope);
    if (isProjectScope && projectId) loadProjectAssets(projectId);
    else if (_renderCollectionPanel) _renderCollectionPanel();
}

/* ── Project assets (internal) ── */

export function loadProjectAssets(projectId) {
    const strip = document.getElementById('rightPanelProjectAssetsList');
    if (!strip) return;
    strip.innerHTML = '';
    getProject(projectId, { timeoutMs: 12000 })
        .then(project => {
            const assets = (project && project.assets) ? project.assets : [];
            appState.currentProjectId = projectId;
            appState.currentProjectAssets = assets;
            renderProjectAssetsStack();
        })
        .catch(() => {
            strip.innerHTML = '';
            appState.currentProjectId = null;
            appState.currentProjectAssets = [];
        });
}

function renderProjectAssetsStack() {
    const strip = document.getElementById('rightPanelProjectAssetsList');
    if (!strip) return;
    strip._stackUpdate = null;
    stackNavigationState = null;
    const items = appState.currentProjectAssets;
    if (items.length === 0) {
        strip.innerHTML = '';
        const empty = document.createElement('p');
        empty.className = 'right-panel-stack-empty';
        empty.textContent = 'No saved posters in this project yet.';
        strip.appendChild(empty);
        return;
    }
    const list = document.createElement('div');
    list.className = 'right-panel-collection-list';
    const projectId = appState.currentProjectId;
    items.forEach((item, idx) => {
        const title = String((item && item.title) || '').trim() || 'Unnamed';
        const imageUrl = (item && item.storedRef && String(item.storedRef).trim())
            ? item.storedRef.trim()
            : (item && item.posterImageUrl && String(item.posterImageUrl).trim())
                ? item.posterImageUrl.trim()
                : '';
        const card = document.createElement('div');
        card.className = 'right-panel-collection-item';
        card.setAttribute('data-index', String(idx));
        const posterWrap = document.createElement('div');
        posterWrap.className = 'right-panel-collection-item-poster-wrap';
        if (imageUrl) {
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = title;
            img.loading = 'lazy';
            posterWrap.appendChild(img);
        } else {
            const ph = document.createElement('div');
            ph.className = 'right-panel-collection-placeholder';
            ph.textContent = '?';
            posterWrap.appendChild(ph);
        }
        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'right-panel-collection-item-remove';
        removeBtn.setAttribute('aria-label', 'Remove from project');
        removeBtn.setAttribute('title', 'Remove from project');
        removeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
        removeBtn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            const i = parseInt(card.getAttribute('data-index'), 10);
            if (!projectId || isNaN(i) || i < 0) return;
            deleteProjectAsset(projectId, String(i), { timeoutMs: 12000 })
                .then(() => { loadProjectAssets(projectId); })
                .catch(() => { showFallbackToast('Could not remove from project.'); });
        });
        posterWrap.appendChild(removeBtn);
        card.appendChild(posterWrap);
        const titleEl = document.createElement('span');
        titleEl.className = 'right-panel-collection-item-title';
        titleEl.textContent = title;
        card.appendChild(titleEl);
        list.appendChild(card);
    });
    strip.innerHTML = '';
    strip.appendChild(list);
}

/* ── Projects dropdown ── */

export function loadProjects() {
    getProjects({ timeoutMs: 12000 })
        .then(data => {
            appState.projects = Array.isArray(data) ? data : [];
            renderProjectsDropdown();
            updateRightPanelScope();
        })
        .catch(() => {
            appState.projects = [];
            renderProjectsDropdown();
        });
}

export function renderProjectsDropdown() {
    const container = document.getElementById('rightPanelProjectsList');
    if (!container) return;
    container.innerHTML = '';
    appState.projects.forEach(p => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'right-panel-dropdown-item';
        btn.setAttribute('role', 'menuitem');
        btn.setAttribute('data-scope', 'project:' + (p.id || ''));
        btn.textContent = p.name || 'Unnamed';
        container.appendChild(btn);
    });
}

/* ── Conversation list (left panel) ── */

export function updateConversationList() {
    if (!conversationList) return;
    conversationList.innerHTML = '';
    appState.conversations.forEach(mainConv => {
        const group = document.createElement('div');
        group.className = 'conversation-group';

        const mainActive = mainConv.id === appState.activeConversationId && !appState.activeSubConversationId;
        const mainItem = document.createElement('div');
        const mainLabel = mainConv.title || 'New conversation';
        mainItem.className = 'conversation-item' + (mainActive ? ' active' : '');
        mainItem.textContent = mainLabel.length > 36 ? mainLabel.slice(0, 36) + '\u2026' : mainLabel;
        mainItem.setAttribute('title', mainLabel);
        mainItem.setAttribute('data-thread-type', 'parent');
        mainItem.setAttribute('data-main-id', mainConv.id);
        mainItem.addEventListener('click', () => { switchConversation(mainConv.id); });
        group.appendChild(mainItem);

        const subs = mainConv.subConversations && Array.isArray(mainConv.subConversations)
            ? mainConv.subConversations.filter(s => !s.archived)
            : [];
        subs.forEach(sub => {
            const subActive = mainConv.id === appState.activeConversationId && sub.id === appState.activeSubConversationId;
            const subEl = document.createElement('div');
            const subLabel = sub.title || 'Re: ' + (sub.contextMovie && sub.contextMovie.title) || 'Sub';
            subEl.className = 'conversation-item conversation-item-sub' + (subActive ? ' active' : '');
            subEl.setAttribute('title', subLabel);
            subEl.setAttribute('data-thread-type', 'sub');
            subEl.setAttribute('data-main-id', mainConv.id);
            subEl.setAttribute('data-sub-id', sub.id);
            subEl.addEventListener('click', () => { switchConversation(mainConv.id, sub.id); });

            const thumbWrap = document.createElement('span');
            thumbWrap.className = 'conversation-item-sub-thumb';
            const imgUrl = sub.contextMovie && sub.contextMovie.imageUrl && String(sub.contextMovie.imageUrl).trim();
            if (imgUrl) {
                const thumbImg = document.createElement('img');
                thumbImg.src = imgUrl;
                thumbImg.alt = '';
                thumbImg.loading = 'lazy';
                thumbWrap.appendChild(thumbImg);
            } else {
                thumbWrap.classList.add('conversation-item-sub-thumb-icon');
                thumbWrap.innerHTML = filmIconSvg;
            }
            subEl.appendChild(thumbWrap);

            const labelSpan = document.createElement('span');
            labelSpan.className = 'conversation-item-sub-label';
            labelSpan.textContent = subLabel.length > 32 ? subLabel.slice(0, 32) + '\u2026' : subLabel;
            subEl.appendChild(labelSpan);

            group.appendChild(subEl);
        });

        conversationList.appendChild(group);
    });
}

/* ── Retrieving indicator ── */

export function showRetrieving() {
    if (appState.conversationView === 'sub' && movieHubRetrieving) {
        movieHubRetrieving.classList.remove('hidden');
        if (retrievingRow) retrievingRow.classList.add('hidden');
        clearHubPosterStripsForLoading();
    } else if (retrievingRow) {
        retrievingRow.classList.remove('hidden');
        if (movieHubRetrieving) movieHubRetrieving.classList.add('hidden');
    }
    if (chatColumn) chatColumn.scrollTo({ top: appState.conversationView === 'sub' ? 0 : chatColumn.scrollHeight, behavior: 'smooth' });
}

export function hideRetrieving() {
    if (retrievingRow) retrievingRow.classList.add('hidden');
    if (movieHubRetrieving) movieHubRetrieving.classList.add('hidden');
    if (appState.conversationView === 'sub') {
        const thread = getActiveThread();
        if (thread && thread.sub) updateMovieHub(thread);
    }
}

/* ── Navigation helpers ── */

export function startNewChat() {
    addConversation();
}

export function navigateBackToParentConversation() {
    const main = getActiveConversation();
    if (!main || appState.conversationView !== 'sub') return;
    abortActiveHubRequests();
    hideRetrieving();
    appState.lastViewByConversationId[main.id] = { view: 'main', subId: null };
    appState.conversationView = 'main';
    appState.restoreScrollTop = appState.mainScrollTopByConversationId[main.id] != null
        ? appState.mainScrollTopByConversationId[main.id] : 0;
    appState.activeSubConversationId = null;
    updateConversationList();
    if (_renderMessages) _renderMessages();
    if (_renderCollectionPanel) _renderCollectionPanel();
    updateHeaderForView();
    updateRightPanelScope();
}

export function renameSubConversation() {
    const thread = getActiveThread();
    if (!thread.sub) return;
    const current = thread.sub.title || (thread.sub.contextMovie && thread.sub.contextMovie.title) || 'Re: movie';
    const newTitle = typeof prompt === 'function' ? prompt('Rename sub-conversation', current) : null;
    if (newTitle != null && String(newTitle).trim() !== '') {
        thread.sub.title = String(newTitle).trim();
        updateConversationList();
        updateHeaderForView();
    }
}

export function closeSubConversation() {
    const thread = getActiveThread();
    const main = getActiveConversation();
    if (!thread.sub || !main) return;
    thread.sub.archived = true;
    switchConversation(main.id);
}

/* ── Real-agent modal ── */

export function showRealAgentConfirmModal() {
    const modal = document.getElementById('realAgentConfirmModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    const cancelBtn = modal.querySelector('.real-agent-modal-cancel');
    if (cancelBtn) cancelBtn.focus();
}

export function hideRealAgentConfirmModal() {
    const modal = document.getElementById('realAgentConfirmModal');
    if (modal) modal.classList.add('hidden');
}

export function updateHeaderRealAgentIndicator() {
    if (modeBadge) {
        modeBadge.classList.toggle('real-agent-active', appState.useRealAgent);
    }
}

/* ── Init: wire all event listeners ── */

export function initLayout() {
    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
    if (rightPanelToggle) rightPanelToggle.addEventListener('click', toggleRightPanel);

    document.addEventListener('keydown', e => {
        if (!rightPanel || !rightPanel.contains(document.activeElement)) return;
        const isPrev = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
        const isNext = e.key === 'ArrowDown' || e.key === 'ArrowRight';
        if (!isPrev && !isNext) return;
        if (!stackNavigationState) return;
        e.preventDefault();
        if (isPrev) stackNavigationState.onPrev();
        else stackNavigationState.onNext();
    });

    (function setupRightPanelHamburger() {
        const hamburger = document.getElementById('rightPanelHamburger');
        const dropdown = document.getElementById('rightPanelDropdown');
        if (!hamburger || !dropdown) return;

        function closeDropdown() {
            dropdown.classList.remove('is-open');
            hamburger.setAttribute('aria-expanded', 'false');
            dropdown.setAttribute('aria-hidden', 'true');
        }
        function openDropdown() {
            updateRightPanelScope();
            dropdown.classList.add('is-open');
            hamburger.setAttribute('aria-expanded', 'true');
            dropdown.setAttribute('aria-hidden', 'false');
        }
        function toggleDropdown() {
            if (dropdown.classList.contains('is-open')) closeDropdown();
            else openDropdown();
        }

        hamburger.addEventListener('click', e => {
            e.stopPropagation();
            toggleDropdown();
        });
        document.addEventListener('click', e => {
            if (!dropdown.classList.contains('is-open')) return;
            if (dropdown.contains(e.target) || hamburger.contains(e.target)) return;
            closeDropdown();
        });
        dropdown.addEventListener('click', e => {
            const btn = e.target && e.target.closest && e.target.closest('.right-panel-dropdown-item');
            if (!btn) return;
            e.preventDefault();
            const conv = getActiveConversation();
            const scope = btn.getAttribute('data-scope') || btn.textContent.trim();
            if (conv) conv.activeScope = scope;
            updateRightPanelScope();
            closeDropdown();
        });
    })();

    if (newChatBtn) newChatBtn.addEventListener('click', startNewChat);
    if (projectsPageBtn) {
        projectsPageBtn.addEventListener('click', function () {
            window.location.href = 'projects.html';
        });
    }
    if (headerBackBtn) headerBackBtn.addEventListener('click', navigateBackToParentConversation);
    if (headerSubRenameBtn) headerSubRenameBtn.addEventListener('click', renameSubConversation);
    if (headerSubCloseBtn) headerSubCloseBtn.addEventListener('click', closeSubConversation);

    if (movieHubResetBtn) {
        movieHubResetBtn.addEventListener('click', function () {
            const thread = getActiveThread();
            const sub = thread && thread.sub;
            if (!sub || !sub.hubOriginalClusters) return;
            const restored = cloneMovieHubClusters(sub.hubOriginalClusters);
            if (restored) applyMovieHubClusters(restored);
            if (_renderMessages) _renderMessages();
        });
    }

    if (useRealAgentToggle) {
        useRealAgentToggle.checked = appState.useRealAgent;
        useRealAgentToggle.addEventListener('change', () => {
            if (useRealAgentToggle.checked && !appState.realAgentConfirmedThisSession) {
                useRealAgentToggle.checked = false;
                showRealAgentConfirmModal();
                return;
            }
            appState.useRealAgent = useRealAgentToggle.checked;
            try { sessionStorage.setItem('cinemind_useRealAgent', appState.useRealAgent ? '1' : '0'); } catch (e) { /* ignore */ }
            updateHeaderRealAgentIndicator();
        });
    }

    (function setupRealAgentConfirmModal() {
        const modal = document.getElementById('realAgentConfirmModal');
        const cancelBtn = document.getElementById('realAgentConfirmCancel');
        const continueBtn = document.getElementById('realAgentConfirmContinue');
        const backdrop = modal && modal.querySelector('.real-agent-modal-backdrop');
        if (!modal || !cancelBtn || !continueBtn) return;
        function onConfirm() {
            appState.realAgentConfirmedThisSession = true;
            appState.useRealAgent = true;
            if (useRealAgentToggle) useRealAgentToggle.checked = true;
            try { sessionStorage.setItem('cinemind_useRealAgent', '1'); } catch (e) { /* ignore */ }
            hideRealAgentConfirmModal();
            updateHeaderRealAgentIndicator();
        }
        function onCancel() {
            hideRealAgentConfirmModal();
        }
        cancelBtn.addEventListener('click', onCancel);
        continueBtn.addEventListener('click', onConfirm);
        if (backdrop) backdrop.addEventListener('click', onCancel);
        modal.addEventListener('keydown', e => {
            if (e.key === 'Escape') onCancel();
            if (e.key === 'Enter' && e.target === continueBtn) onConfirm();
        });
    })();
}
