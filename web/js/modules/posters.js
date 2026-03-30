/** @module posters — Poster/card rendering, carousel, and collection management. */

import { app, rightPanel, composerInput } from './dom.js';
import {
    appState, getActiveConversation, getAssetKey, collectionHasKey,
    isPosterInActiveCollection, normalizeTitle, pageIdFromUrl
} from './state.js';
import { escapeHtml } from './normalize.js';
import { addProjectAssets } from './api.js';

/* ── Callback registry (breaks circular deps with layout/chat modules) ── */

let _openWhereToWatch = null;
let _openMovieDetails = null;
let _addSubConversation = null;
let _openRightPanelToCollection = null;
let _showSavedToCollectionToast = null;
let _showSavedToProjectToast = null;
let _showAlreadyAddedToast = null;
let _showFallbackToast = null;
let _loadProjectAssets = null;
let _updateRightPanelScope = null;

export function setPosterCallbacks({
    openWhereToWatch, openMovieDetails, addSubConversation, openRightPanelToCollection,
    showSavedToCollectionToast, showSavedToProjectToast,
    showAlreadyAddedToast, showFallbackToast,
    loadProjectAssets, updateRightPanelScope
}) {
    _openWhereToWatch = openWhereToWatch;
    _openMovieDetails = openMovieDetails;
    _addSubConversation = addSubConversation;
    _openRightPanelToCollection = openRightPanelToCollection;
    _showSavedToCollectionToast = showSavedToCollectionToast;
    _showSavedToProjectToast = showSavedToProjectToast;
    _showAlreadyAddedToast = showAlreadyAddedToast;
    _showFallbackToast = showFallbackToast;
    _loadProjectAssets = loadProjectAssets;
    _updateRightPanelScope = updateRightPanelScope;
}

function buildMovieDetailsPayloadFromItem(item, title, imgUrl, href) {
    const pageUrl = (href && String(href).trim()) || (item.page_url && String(item.page_url).trim()) || '';
    const tmdbId = item.tmdbId || item.tmdb_id || undefined;
    const mediaType = item.mediaType || item.media_type || undefined;
    const runtime = item.runtime_minutes || item.runtimeMinutes || item.runtime;
    const genres = Array.isArray(item.genres)
        ? item.genres
        : Array.isArray(item.genre_names) ? item.genre_names : undefined;
    const overview = item.overview || item.summary || item.plot;
    const rating = item.rating || item.vote_average || item.voteAverage;
    const voteCount = item.vote_count || item.voteCount;
    const language = item.language || item.original_language;
    const country = item.country || item.production_country;
    return {
        title: title,
        movie_title: item.movie_title || item.title || title,
        year: item.year != null ? item.year : undefined,
        primary_image_url: imgUrl || '',
        page_url: pageUrl || '',
        pageUrl: pageUrl || '',
        pageId: pageIdFromUrl(pageUrl || '') || undefined,
        tmdbId: tmdbId,
        mediaType: mediaType,
        runtime_minutes: runtime,
        genres: genres,
        overview: overview,
        rating: rating,
        vote_count: voteCount,
        language: language,
        country: country
    };
}

/* ── SVG icon constants ── */

const addIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
const messageIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
const whereToWatchIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
const infoIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>';
const arrowLeftSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>';
const arrowRightSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>';

/* ── Module-level state ── */

let stackNavigationState = null;

/* ── addToCollection ── */

export function addToCollection(title, imageUrl, pageUrl, pageId) {
    const conv = getActiveConversation();
    if (!conv || !title) return;
    const poster = { title: title, imageUrl: imageUrl, pageUrl: pageUrl, pageId: pageId };
    if (isPosterInActiveCollection(poster)) {
        if (_showAlreadyAddedToast) _showAlreadyAddedToast();
        return;
    }
    const scope = (conv.activeScope != null && conv.activeScope !== '') ? conv.activeScope : 'This Conversation';
    if (String(scope).indexOf('project:') === 0) {
        const projectId = String(scope).slice(8);
        const assetPayload = {
            title: String(title).trim(),
            posterImageUrl: (imageUrl && String(imageUrl).trim()) || undefined,
            pageUrl: (pageUrl && String(pageUrl).trim()) || undefined,
            pageId: (pageId && String(pageId).trim()) || undefined,
            conversationId: (conv.id && String(conv.id).trim()) || undefined
        };
        if (appState.conversationView === 'sub' && appState.activeSubConversationId) {
            assetPayload.subConversationId = appState.activeSubConversationId;
        }
        const payload = { assets: [assetPayload] };
        addProjectAssets(projectId, payload.assets, { timeoutMs: 12000 })
            .then(function (result) {
                const proj = appState.projects.filter(function (p) { return p.id === projectId; })[0];
                if (_showSavedToProjectToast) _showSavedToProjectToast(proj ? proj.name : null);
                if (_loadProjectAssets) _loadProjectAssets(projectId);
                if (_updateRightPanelScope) _updateRightPanelScope();
                if (rightPanel && rightPanel.classList.contains('collapsed')) {
                    rightPanel.classList.remove('collapsed');
                    app.classList.add('right-panel-open');
                }
            })
            .catch(function () {
                if (_showFallbackToast) _showFallbackToast('Could not add to project. Check that the server supports projects.');
            });
        return;
    }
    if (!conv.collection) conv.collection = [];
    const key = getAssetKey(title, imageUrl, pageUrl, pageId);
    const item = {
        title: String(title).trim(),
        imageUrl: (imageUrl && String(imageUrl).trim()) || '',
        assetKey: key
    };
    if (pageUrl && String(pageUrl).trim()) item.pageUrl = String(pageUrl).trim();
    if (pageId && String(pageId).trim()) item.pageId = String(pageId).trim();
    if (appState.conversationView === 'sub' && appState.activeSubConversationId) {
        item.addedFromSubConversationId = appState.activeSubConversationId;
    }
    conv.collection.push(item);
    renderCollectionPanel();
    if (_openRightPanelToCollection) _openRightPanelToCollection();
    /* Do not re-render messages: it tears down the carousel DOM and breaks subsequent "Add to Collection" clicks. */
}

/* ── Stack helpers ── */

function getMaxStackLayers(container) {
    if (!container || !container.offsetParent) return 2;
    const h = container.clientHeight || 0;
    const rem = typeof getComputedStyle !== 'undefined' && document.documentElement
        ? parseFloat(getComputedStyle(document.documentElement).fontSize) || 16 : 16;
    const heightRem = h / rem;
    if (heightRem < 18) return 1;
    if (heightRem < 26) return 2;
    return 3;
}

function getStackLayerClass(delta) {
    if (delta === 0) return 'stack-layer-active';
    if (delta < 0) return 'stack-layer-above-' + Math.min(Math.abs(delta), 3);
    return 'stack-layer-below-' + Math.min(delta, 3);
}

function createOneStackItem(item, index, layerClass, onActiveChange) {
    const title = String((item && item.title) || '').trim() || 'Unnamed';
    const imageUrl = (item && item.imageUrl) && String(item.imageUrl).trim() ? item.imageUrl : '';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'right-panel-stack-item ' + layerClass;
    btn.setAttribute('data-index', String(index));
    btn.setAttribute('aria-label', title);
    btn.setAttribute('title', title);
    btn.addEventListener('click', function () {
        if (typeof onActiveChange === 'function') onActiveChange(index);
    });
    const poster = document.createElement('div');
    poster.className = 'stack-item-poster';
    if (imageUrl) {
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = title;
        img.loading = 'lazy';
        poster.appendChild(img);
    } else {
        const ph = document.createElement('div');
        ph.className = 'stack-item-placeholder';
        ph.textContent = '?';
        poster.appendChild(ph);
    }
    btn.appendChild(poster);
    const titleEl = document.createElement('span');
    titleEl.className = 'stack-item-title';
    titleEl.textContent = title;
    titleEl.setAttribute('title', title);
    btn.appendChild(titleEl);
    const savedBadge = document.createElement('span');
    savedBadge.className = 'stack-item-saved';
    savedBadge.textContent = 'Saved';
    savedBadge.setAttribute('aria-hidden', 'true');
    btn.appendChild(savedBadge);
    return btn;
}

/* ── renderPosterStack ── */

export function renderPosterStack(container, items, activeIndex, onActiveChange) {
    if (!container) return;
    container.innerHTML = '';
    container._stackUpdate = null;
    stackNavigationState = null;
    if (!Array.isArray(items) || items.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'right-panel-stack-empty';
        empty.textContent = 'No posters yet. Add from the conversation.';
        container.appendChild(empty);
        return;
    }
    const count = items.length;
    let active = Math.max(0, Math.min(activeIndex, count - 1));
    const maxLayers = getMaxStackLayers(container);
    let start = Math.max(0, active - maxLayers);
    let end = Math.min(count - 1, active + maxLayers);

    const wrapper = document.createElement('div');
    wrapper.className = 'right-panel-stack-wrapper';

    const upBtn = document.createElement('button');
    upBtn.type = 'button';
    upBtn.className = 'right-panel-stack-arrow right-panel-stack-arrow-up';
    upBtn.setAttribute('aria-label', 'Previous poster');
    upBtn.setAttribute('title', 'Previous poster');
    upBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>';
    upBtn.disabled = active <= 0;
    upBtn.addEventListener('click', function () {
        if (active > 0 && typeof onActiveChange === 'function') onActiveChange(active - 1);
    });

    const stackView = document.createElement('div');
    stackView.className = 'right-panel-stack-view';
    const rail = document.createElement('div');
    rail.className = 'right-panel-stack-rail';
    for (let i = start; i <= end; i++) {
        const layerClass = getStackLayerClass(i - active);
        rail.appendChild(createOneStackItem(items[i], i, layerClass, onActiveChange));
    }
    stackView.appendChild(rail);

    const downBtn = document.createElement('button');
    downBtn.type = 'button';
    downBtn.className = 'right-panel-stack-arrow right-panel-stack-arrow-down';
    downBtn.setAttribute('aria-label', 'Next poster');
    downBtn.setAttribute('title', 'Next poster');
    downBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';
    downBtn.disabled = active >= count - 1;
    downBtn.addEventListener('click', function () {
        if (active < count - 1 && typeof onActiveChange === 'function') onActiveChange(active + 1);
    });

    wrapper.appendChild(upBtn);
    wrapper.appendChild(stackView);
    wrapper.appendChild(downBtn);
    container.appendChild(wrapper);

    function updateSelection(newIndex) {
        const newActive = Math.max(0, Math.min(newIndex, count - 1));
        const newStart = Math.max(0, newActive - maxLayers);
        const newEnd = Math.min(count - 1, newActive + maxLayers);
        const existing = {};
        let idx;
        for (idx = 0; idx < rail.children.length; idx++) {
            const el = rail.children[idx];
            const di = parseInt(el.getAttribute('data-index'), 10);
            existing[di] = el;
        }
        for (idx = newStart; idx <= newEnd; idx++) {
            const layerClass = getStackLayerClass(idx - newActive);
            if (existing[idx]) {
                existing[idx].className = 'right-panel-stack-item ' + layerClass;
            } else {
                rail.appendChild(createOneStackItem(items[idx], idx, layerClass, onActiveChange));
            }
        }
        const toRemove = [];
        for (const k in existing) {
            idx = parseInt(k, 10);
            if (idx < newStart || idx > newEnd) toRemove.push(existing[k]);
        }
        toRemove.forEach(function (el) { rail.removeChild(el); });
        upBtn.disabled = newActive <= 0;
        downBtn.disabled = newActive >= count - 1;
        active = newActive;
        start = newStart;
        end = newEnd;
        stackNavigationState = {
            activeIndex: newActive,
            count: count,
            onPrev: function () { if (newActive > 0) onActiveChange(newActive - 1); },
            onNext: function () { if (newActive < count - 1) onActiveChange(newActive + 1); }
        };
    }

    container._stackUpdate = updateSelection;
    stackNavigationState = {
        activeIndex: active,
        count: count,
        onPrev: function () { if (active > 0) onActiveChange(active - 1); },
        onNext: function () { if (active < count - 1) onActiveChange(active + 1); }
    };
}

/* ── renderCollectionPanel ── */

export function renderCollectionPanel() {
    const container = document.getElementById('collectionList');
    if (!container) return;
    container._stackUpdate = null;
    stackNavigationState = null;
    const conv = getActiveConversation();
    const items = (conv && conv.collection) ? conv.collection : [];
    if (items.length === 0) {
        container.innerHTML = '';
        const empty = document.createElement('p');
        empty.className = 'right-panel-stack-empty';
        empty.textContent = 'No posters yet. Add from the conversation.';
        container.appendChild(empty);
        return;
    }
    const list = document.createElement('div');
    list.className = 'right-panel-collection-list';
    items.forEach(function (item, idx) {
        const title = String((item && item.title) || '').trim() || 'Unnamed';
        const imageUrl = (item && item.imageUrl) && String(item.imageUrl).trim() ? item.imageUrl : '';
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
        removeBtn.setAttribute('aria-label', 'Remove from collection');
        removeBtn.setAttribute('title', 'Remove from collection');
        removeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
        removeBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const i = parseInt(card.getAttribute('data-index'), 10);
            if (conv && conv.collection && !isNaN(i) && i >= 0 && i < conv.collection.length) {
                conv.collection.splice(i, 1);
                renderCollectionPanel();
            }
        });
        posterWrap.appendChild(removeBtn);
        card.appendChild(posterWrap);
        const titleEl = document.createElement('span');
        titleEl.className = 'right-panel-collection-item-title';
        titleEl.textContent = title;
        card.appendChild(titleEl);
        list.appendChild(card);
    });
    container.innerHTML = '';
    container.appendChild(list);
}

/* ── captureAssetsForProjectScope ── */

export function captureAssetsForProjectScope(conversationId, msgIndex, norm) {
    const conv = getActiveConversation();
    if (!conv || !norm) return;
    const scope = conv.activeScope;
    if (!scope || String(scope).indexOf('project:') !== 0) return;
    const projectId = String(scope).slice(8);
    if (!projectId) return;

    const items = [];
    if (norm.media_strip && norm.media_strip.movie_title) items.push(norm.media_strip);
    if (Array.isArray(norm.media_candidates)) items.push.apply(items, norm.media_candidates);

    const batch = [];
    const keysToMark = [];
    for (let j = 0; j < items.length; j++) {
        const it = items[j];
        const title = String((it.movie_title || it.title || '')).trim();
        const pageUrl = (it.page_url && String(it.page_url).trim()) || '';
        const posterUrl = (it.primary_image_url && String(it.primary_image_url).trim()) || '';
        const key = projectId + '|' + (conversationId || '') + '|' + msgIndex + '|' + (pageUrl || posterUrl || title);
        if (appState.savedAssetKeys.has(key)) continue;
        batch.push({
            posterImageUrl: posterUrl || undefined,
            title: title || 'Unnamed',
            pageUrl: pageUrl || undefined,
            conversationId: conversationId || undefined
        });
        keysToMark.push(key);
    }
    if (batch.length === 0) return;

    addProjectAssets(projectId, batch, { timeoutMs: 12000 })
        .then(function (result) {
            keysToMark.forEach(function (k) { appState.savedAssetKeys.add(k); });
            const added = (result && result.added) || 0;
            if (added > 0) {
                const proj = appState.projects.filter(function (p) { return p.id === projectId; })[0];
                if (_showSavedToProjectToast) _showSavedToProjectToast(proj ? proj.name : null);
                if (_loadProjectAssets) _loadProjectAssets(projectId);
            }
        })
        .catch(function () { /* ignore */ });
}

/* ── createHeroCard ── */

export function createHeroCard(item, options) {
    options = options || {};
    const noOverlay = options.noOverlay === true;
    const title = String((item.movie_title || item.title || '')).trim();
    if (!title) return null;
    let labelText = title;
    if (item.year != null) labelText += ' (' + item.year + ')';
    const imgUrl = (item.primary_image_url && item.primary_image_url.trim()) || '';
    const href = (item.page_url && item.page_url.trim()) || '';
    const isLink = !!href && options.link !== false;

    const card = isLink ? document.createElement('a') : document.createElement('div');
    card.className = 'media-strip-card';
    if (isLink) {
        card.href = href;
        card.target = '_blank';
        card.rel = 'noopener';
    }

    const poster = document.createElement('div');
    poster.className = 'media-strip-card-poster';
    if (imgUrl) {
        const inner = document.createElement('div');
        inner.className = 'media-strip-card-poster-inner';
        poster.classList.add('media-strip-skeleton');
        const img = document.createElement('img');
        img.src = imgUrl;
        img.alt = title;
        img.loading = 'lazy';
        img.onload = function () { poster.classList.remove('media-strip-skeleton'); };
        img.onerror = function () {
            poster.classList.remove('media-strip-skeleton');
            const ph = document.createElement('div');
            ph.className = 'media-strip-placeholder media-strip-card-poster-placeholder';
            ph.innerHTML = '<span class="media-strip-placeholder-title">' + escapeHtml(title) + '</span><span class="media-strip-placeholder-caption">No image</span>';
            inner.innerHTML = '';
            inner.appendChild(ph);
        };
        inner.appendChild(img);
        poster.appendChild(inner);
    } else {
        poster.classList.add('media-strip-placeholder');
        poster.innerHTML = '<span class="media-strip-placeholder-title">' + escapeHtml(title) + '</span><span class="media-strip-placeholder-caption">No image</span>';
    }

    if (!noOverlay) {
        const topRightOverlay = document.createElement('div');
        topRightOverlay.className = 'media-strip-card-overlay media-strip-card-overlay--top-right';
        const whereToWatchBtn = document.createElement('button');
        whereToWatchBtn.type = 'button';
        whereToWatchBtn.className = 'media-strip-card-action media-strip-card-action--tooltip-below';
        whereToWatchBtn.setAttribute('data-tooltip', 'Where to watch');
        whereToWatchBtn.setAttribute('title', 'Where to watch');
        whereToWatchBtn.setAttribute('aria-label', 'Where to watch');
        whereToWatchBtn.innerHTML = whereToWatchIconSvg;
        whereToWatchBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (_openWhereToWatch) _openWhereToWatch({
                title: title,
                year: item.year,
                pageUrl: href || undefined,
                pageId: pageIdFromUrl(href || '') || undefined,
                tmdbId: item.tmdbId || item.tmdb_id || undefined,
                mediaType: item.mediaType || item.media_type || undefined
            });
        });
        topRightOverlay.appendChild(whereToWatchBtn);
        poster.appendChild(topRightOverlay);

        const overlay = document.createElement('div');
        overlay.className = 'media-strip-card-overlay';
        const pageUrl = href || '';
        const pageId = pageIdFromUrl(pageUrl);
        let isInCollection = isPosterInActiveCollection({ title: title, imageUrl: imgUrl, pageUrl: pageUrl, pageId: pageId });
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'media-strip-card-action media-strip-card-action--tooltip-below' + (isInCollection ? ' is-added' : '');
        addBtn.setAttribute('data-tooltip', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.setAttribute('title', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.setAttribute('aria-label', isInCollection ? 'Already Added' : 'Add to Collection');
        if (isInCollection) addBtn.disabled = true;
        addBtn.innerHTML = addIconSvg;
        addBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (isInCollection) return false;
            addToCollection(title, imgUrl, pageUrl || undefined, pageId || undefined);
            addBtn.classList.add('is-added');
            addBtn.setAttribute('data-tooltip', 'Already Added');
            addBtn.setAttribute('title', 'Already Added');
            addBtn.setAttribute('aria-label', 'Already Added');
            addBtn.disabled = true;
            isInCollection = true;
            return false;
        });
        // Swap positions: put "Add to Collection" in the top-right overlay with "Where to watch"
        topRightOverlay.appendChild(addBtn);

        const infoBtn = document.createElement('button');
        infoBtn.type = 'button';
        infoBtn.className = 'media-strip-card-action media-strip-card-action--tooltip-below media-strip-card-action--info';
        infoBtn.setAttribute('data-tooltip', 'More info');
        infoBtn.setAttribute('title', 'More info');
        infoBtn.setAttribute('aria-label', 'More info');
        infoBtn.innerHTML = infoIconSvg;
        infoBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (typeof _openMovieDetails === 'function') {
                const payload = buildMovieDetailsPayloadFromItem(item, title, imgUrl, href);
                _openMovieDetails(payload);
            } else if (href) {
                window.open(href, '_blank', 'noopener');
            }
        });
        const msgBtn = document.createElement('button');
        msgBtn.type = 'button';
        msgBtn.className = 'media-strip-card-action media-strip-card-action--tooltip-below';
        msgBtn.setAttribute('data-tooltip', 'Talk More About This');
        msgBtn.setAttribute('title', 'Talk More About This');
        msgBtn.setAttribute('aria-label', 'Talk More About This');
        msgBtn.innerHTML = messageIconSvg;
        msgBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            // In sub-context view, keep the current hub anchor/conversation stable.
            // "Talk More About This" should simply pre-fill the composer (minimal UX),
            // rather than spawning a new sub-conversation.
            if (appState && appState.conversationView === 'sub' && composerInput) {
                const promptLabel = labelText && String(labelText).trim()
                    ? String(labelText).trim()
                    : (title && String(title).trim() ? String(title).trim() : 'this movie');
                composerInput.value = 'Tell me more about ' + promptLabel;
                composerInput.focus();
                return;
            }
            if (_addSubConversation) {
                _addSubConversation({
                    title: title,
                    year: item.year,
                    pageUrl: pageUrl || undefined,
                    pageId: pageId || undefined,
                    imageUrl: imgUrl || undefined,
                    tmdbId: item.tmdbId || item.tmdb_id || undefined,
                    mediaType: item.mediaType || item.media_type || undefined,
                    relatedMovies: Array.isArray(item.relatedMovies) ? item.relatedMovies : undefined
                });
            }
        });
        // Bottom overlay now holds "More info" alongside the message action
        overlay.appendChild(infoBtn);
        overlay.appendChild(msgBtn);
        if (isInCollection) {
            const addedLabel = document.createElement('span');
            addedLabel.className = 'media-strip-card-already-added';
            addedLabel.textContent = 'Already Added';
            overlay.appendChild(addedLabel);
        }
        poster.appendChild(overlay);
    }
    card.appendChild(poster);

    const lbl = document.createElement('span');
    lbl.className = 'media-strip-card-label';
    lbl.textContent = labelText;
    card.appendChild(lbl);
    return card;
}

/* ── createCandidateCard ── */

export function createCandidateCard(item, options) {
    options = options || {};
    const title = String((item.movie_title || item.title || '')).trim();
    if (!title) return null;
    let labelText = title;
    if (item.year != null) labelText += ' (' + item.year + ')';
    const imgUrl = (item.primary_image_url && item.primary_image_url.trim()) || (item.imageUrl && String(item.imageUrl).trim()) || '';
    const href = (item.page_url && item.page_url.trim()) || (item.sourceUrl && String(item.sourceUrl).trim()) || '';
    const isLink = !!href && options.link !== false;

    const card = isLink ? document.createElement('a') : document.createElement('div');
    card.className = 'media-candidates-card';
    if (isLink) {
        card.href = href;
        card.target = '_blank';
        card.rel = 'noopener';
    }

    if (imgUrl) {
        const img = document.createElement('img');
        img.src = imgUrl;
        img.alt = title;
        img.loading = 'lazy';
        card.appendChild(img);
    } else {
        const ph = document.createElement('div');
        ph.className = 'media-candidates-placeholder';
        ph.textContent = title;
        card.appendChild(ph);
    }

    const lbl = document.createElement('span');
    lbl.className = 'media-candidates-card-label';
    lbl.textContent = labelText;
    card.appendChild(lbl);
    return card;
}

/* ── attachmentItemToHeroShape ── */

export function attachmentItemToHeroShape(item) {
    const title = (item.title != null && String(item.title).trim()) || '';
    if (!title) return null;
    return {
        movie_title: title,
        year: typeof item.year === 'number' ? item.year : undefined,
        primary_image_url: (item.imageUrl && String(item.imageUrl).trim()) || '',
        page_url: (item.sourceUrl && String(item.sourceUrl).trim()) || '',
        tmdbId: item.tmdbId || item.tmdb_id || undefined,
        mediaType: item.mediaType || item.media_type || undefined,
        relatedMovies: Array.isArray(item.relatedMovies) ? item.relatedMovies : undefined
    };
}

/* ── PosterCarouselWheel ── */

export function PosterCarouselWheel(items, activeIndex, onChangeIndex, options) {
    options = options || {};
    const visibleWindow = typeof options.visibleWindow === 'number' ? options.visibleWindow : 2;

    const root = document.createElement('div');
    root.className = 'poster-carousel-wheel';
    const inner = document.createElement('div');
    inner.className = 'poster-carousel-wheel-inner';
    const track = document.createElement('div');
    track.className = 'poster-carousel-wheel-track';

    let currentIndex = Math.max(0, Math.min(activeIndex, items.length - 1));
    if (items.length === 0) return root;

    function readWheelTokens() {
        const s = root.isConnected ? window.getComputedStyle(root) : (document.documentElement ? window.getComputedStyle(document.documentElement) : null);
        if (!s) {
            return { centerScale: 1, neighborScale: 0.82, farScale: 0.65, centerOpacity: 1, neighborOpacity: 0.88, farOpacity: 0.55 };
        }
        const parseNum = function (val, fallback) { const n = parseFloat(String(val).trim()); return isNaN(n) ? fallback : n; };
        return {
            centerScale: parseNum(s.getPropertyValue('--carousel-center-scale'), 1),
            neighborScale: parseNum(s.getPropertyValue('--carousel-neighbor-scale'), 0.82),
            farScale: parseNum(s.getPropertyValue('--carousel-far-scale'), 0.65),
            centerOpacity: parseNum(s.getPropertyValue('--carousel-center-opacity'), 1),
            neighborOpacity: parseNum(s.getPropertyValue('--carousel-neighbor-opacity'), 0.88),
            farOpacity: parseNum(s.getPropertyValue('--carousel-far-opacity'), 0.55)
        };
    }

    function getScaleAndOpacity(distance, tokens) {
        const d = Math.abs(distance);
        if (d === 0) return { scale: tokens.centerScale, opacity: tokens.centerOpacity };
        if (d === 1) return { scale: tokens.neighborScale, opacity: tokens.neighborOpacity };
        return { scale: tokens.farScale, opacity: tokens.farOpacity };
    }

    function applyTransforms() {
        const tokens = readWheelTokens();
        const n = itemEls.length;
        for (let i = 0; i < n; i++) {
            const distance = i - currentIndex;
            const so = getScaleAndOpacity(distance, tokens);
            const z = 10 + visibleWindow - Math.abs(distance);
            itemEls[i].style.setProperty('--carousel-offset', String(distance));
            itemEls[i].style.setProperty('--carousel-item-scale', String(so.scale));
            itemEls[i].style.setProperty('--carousel-item-opacity', String(so.opacity));
            itemEls[i].style.zIndex = z;
            itemEls[i].setAttribute('aria-current', i === currentIndex ? 'true' : 'false');
        }
        leftBtn.disabled = currentIndex <= 0;
        rightBtn.disabled = currentIndex >= n - 1;
    }

    const itemEls = [];
    items.forEach(function (it, idx) {
        const title = (it.title != null && String(it.title).trim()) || '';
        if (!title) return;
        let labelText = title;
        if (typeof it.year === 'number') labelText += ' (' + it.year + ')';
        const imgUrl = (it.imageUrl && String(it.imageUrl).trim()) || '';
        const href = (it.sourceUrl && String(it.sourceUrl).trim()) || '';

        const el = href ? document.createElement('a') : document.createElement('div');
        el.className = 'poster-carousel-wheel-item';
        el.setAttribute('data-index', idx);
        if (href) {
            el.href = href;
            el.target = '_blank';
            el.rel = 'noopener';
        }
        const posterWrap = document.createElement('div');
        posterWrap.className = 'poster-carousel-wheel-poster-wrap';
        const posterInner = document.createElement('div');
        posterInner.className = 'poster-carousel-wheel-poster-inner';
        if (imgUrl) {
            const img = document.createElement('img');
            img.src = imgUrl;
            img.alt = title;
            img.loading = 'lazy';
            posterInner.appendChild(img);
        } else {
            const ph = document.createElement('div');
            ph.className = 'poster-carousel-wheel-item-placeholder';
            ph.textContent = title;
            posterInner.appendChild(ph);
        }
        posterWrap.appendChild(posterInner);
        const pageUrl = href || '';
        const pageId = (it.pageId != null && String(it.pageId).trim()) ? String(it.pageId).trim() : undefined;
        const isInCollection = isPosterInActiveCollection({ title: title, imageUrl: imgUrl, pageUrl: pageUrl, pageId: pageId });
        const topRightOverlayCarousel = document.createElement('div');
        topRightOverlayCarousel.className = 'poster-carousel-wheel-overlay poster-carousel-wheel-overlay--top-right';
        const whereToWatchEl = document.createElement('button');
        whereToWatchEl.type = 'button';
        whereToWatchEl.className = 'poster-carousel-wheel-action poster-carousel-wheel-action--tooltip-below';
        whereToWatchEl.setAttribute('data-tooltip', 'Where to watch');
        whereToWatchEl.setAttribute('title', 'Where to watch');
        whereToWatchEl.setAttribute('aria-label', 'Where to watch');
        whereToWatchEl.innerHTML = whereToWatchIconSvg;
        whereToWatchEl.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (_openWhereToWatch) _openWhereToWatch({
                title: title,
                year: typeof it.year === 'number' ? it.year : undefined,
                pageUrl: href || undefined,
                pageId: pageId || undefined,
                tmdbId: it.tmdbId || it.tmdb_id || undefined,
                mediaType: it.mediaType || it.media_type || undefined
            });
        });
        topRightOverlayCarousel.appendChild(whereToWatchEl);
        posterWrap.appendChild(topRightOverlayCarousel);

        const overlay = document.createElement('div');
        overlay.className = 'poster-carousel-wheel-overlay';
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'poster-carousel-wheel-action poster-carousel-wheel-action--tooltip-below' + (isInCollection ? ' is-added' : '');
        addBtn.setAttribute('data-tooltip', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.setAttribute('title', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.setAttribute('aria-label', isInCollection ? 'Already Added' : 'Add to Collection');
        if (isInCollection) addBtn.disabled = true;
        addBtn.innerHTML = addIconSvg;
        (function (btn, itemTitle, itemImgUrl, itemPageUrl, itemPageId, itemInCollection) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (itemInCollection) return;
                addToCollection(itemTitle, itemImgUrl, itemPageUrl || undefined, itemPageId);
                btn.classList.add('is-added');
                btn.setAttribute('data-tooltip', 'Already Added');
                btn.setAttribute('title', 'Already Added');
                btn.setAttribute('aria-label', 'Already Added');
                btn.disabled = true;
            });
        })(addBtn, title, imgUrl, pageUrl, pageId, isInCollection);
        // Swap positions: put "Add to Collection" in the top-right overlay with "Where to watch"
        topRightOverlayCarousel.appendChild(addBtn);
        const msgBtn = document.createElement('button');
        msgBtn.type = 'button';
        msgBtn.className = 'poster-carousel-wheel-action poster-carousel-wheel-action--tooltip-below';
        msgBtn.setAttribute('data-tooltip', 'Talk More About This');
        msgBtn.setAttribute('title', 'Talk More About This');
        msgBtn.setAttribute('aria-label', 'Talk More About This');
        msgBtn.innerHTML = messageIconSvg;
        (function (itemTitle, itemYear, itemPageUrl, itemPageId, itemImgUrl, itemRelatedMovies) {
            msgBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                // Same sub-context behavior as `createHeroCard`:
                // pre-fill composer instead of switching sub-conversations.
                if (appState && appState.conversationView === 'sub' && composerInput) {
                    const promptLabel = itemYear != null
                        ? String(itemTitle || '').trim() + ' (' + itemYear + ')'
                        : String(itemTitle || '').trim();
                    composerInput.value = 'Tell me more about ' + (promptLabel || 'this movie');
                    composerInput.focus();
                    return;
                }
                if (_addSubConversation) {
                    _addSubConversation({
                        title: itemTitle,
                        year: itemYear,
                        pageUrl: itemPageUrl || undefined,
                        pageId: itemPageId || undefined,
                        imageUrl: itemImgUrl || undefined,
                        relatedMovies: Array.isArray(itemRelatedMovies) ? itemRelatedMovies : undefined
                    });
                }
            });
        })(title, typeof it.year === 'number' ? it.year : undefined, pageUrl, pageId, imgUrl, it.relatedMovies);
        const infoBtnCarousel = document.createElement('button');
        infoBtnCarousel.type = 'button';
        infoBtnCarousel.className = 'poster-carousel-wheel-action poster-carousel-wheel-action--tooltip-below poster-carousel-wheel-action--info';
        infoBtnCarousel.setAttribute('data-tooltip', 'More info');
        infoBtnCarousel.setAttribute('title', 'More info');
        infoBtnCarousel.setAttribute('aria-label', 'More info');
        infoBtnCarousel.innerHTML = infoIconSvg;
        infoBtnCarousel.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (typeof _openMovieDetails === 'function') {
                const payload = buildMovieDetailsPayloadFromItem(it, title, imgUrl, href);
                _openMovieDetails(payload);
            } else if (href) {
                window.open(href, '_blank', 'noopener');
            }
        });
        // Bottom overlay now holds "More info" alongside the message action
        overlay.appendChild(infoBtnCarousel);
        overlay.appendChild(msgBtn);
        posterWrap.appendChild(overlay);
        el.appendChild(posterWrap);
        const lbl = document.createElement('span');
        lbl.className = 'poster-carousel-wheel-item-label';
        lbl.textContent = labelText;
        el.appendChild(lbl);

        el.addEventListener('click', function (e) {
            const i = parseInt(el.getAttribute('data-index'), 10);
            if (i !== currentIndex) {
                e.preventDefault();
                currentIndex = i;
                applyTransforms();
                if (typeof onChangeIndex === 'function') onChangeIndex(currentIndex);
            }
        });
        track.appendChild(el);
        itemEls.push(el);
    });

    const leftBtn = document.createElement('button');
    leftBtn.type = 'button';
    leftBtn.className = 'poster-carousel-wheel-arrow poster-carousel-wheel-arrow-left';
    leftBtn.setAttribute('aria-label', 'Previous');
    leftBtn.innerHTML = arrowLeftSvg;
    leftBtn.addEventListener('click', function () {
        if (currentIndex <= 0) return;
        currentIndex--;
        applyTransforms();
        if (typeof onChangeIndex === 'function') onChangeIndex(currentIndex);
    });

    const rightBtn = document.createElement('button');
    rightBtn.type = 'button';
    rightBtn.className = 'poster-carousel-wheel-arrow poster-carousel-wheel-arrow-right';
    rightBtn.setAttribute('aria-label', 'Next');
    rightBtn.innerHTML = arrowRightSvg;
    rightBtn.addEventListener('click', function () {
        if (currentIndex >= items.length - 1) return;
        currentIndex++;
        applyTransforms();
        if (typeof onChangeIndex === 'function') onChangeIndex(currentIndex);
    });

    root.appendChild(leftBtn);
    root.appendChild(rightBtn);
    inner.appendChild(track);
    root.appendChild(inner);

    applyTransforms();
    requestAnimationFrame(function () {
        if (root.isConnected) {
            applyTransforms();
            requestAnimationFrame(function () {
                root.classList.add('poster-carousel-wheel--animated');
            });
        }
    });
    return root;
}

/* ── createSceneCard ── */

export function createSceneCard(item) {
    const imageUrl = (item.imageUrl && String(item.imageUrl).trim()) || '';
    if (!imageUrl) return null;
    const caption = (item.caption && String(item.caption).trim()) || '';
    const sourceUrl = (item.sourceUrl && String(item.sourceUrl).trim()) || '';
    const wrap = document.createElement('div');
    wrap.className = 'media-strip-card attachment-scene-card';
    const inner = document.createElement('div');
    inner.className = 'media-strip-card-poster';
    const img = document.createElement('img');
    img.src = imageUrl;
    img.alt = caption || 'Scene';
    img.loading = 'lazy';
    inner.appendChild(img);
    wrap.appendChild(inner);
    if (caption) {
        const capEl = document.createElement('span');
        capEl.className = 'media-strip-card-label attachment-scene-caption';
        capEl.textContent = caption;
        wrap.appendChild(capEl);
    }
    if (sourceUrl) {
        const link = document.createElement('a');
        link.href = sourceUrl;
        link.target = '_blank';
        link.rel = 'noopener';
        link.className = 'media-strip-card';
        link.appendChild(wrap.cloneNode(true));
        return link;
    }
    return wrap;
}

/* ── createHeroAndScenesCarousel ── */

export function createHeroAndScenesCarousel(items) {
    if (!items || items.length === 0) return null;
    const visibleWindow = 2;
    const root = document.createElement('div');
    root.className = 'hero-scenes-carousel-wrap';
    const inner = document.createElement('div');
    inner.className = 'hero-scenes-carousel-inner';
    const track = document.createElement('div');
    track.className = 'hero-scenes-carousel-track';

    let currentIndex = 0;
    const itemEls = [];

    function readWheelTokens() {
        const s = root.isConnected ? window.getComputedStyle(root) : (document.documentElement ? window.getComputedStyle(document.documentElement) : null);
        if (!s) {
            return { centerScale: 1, neighborScale: 0.82, farScale: 0.65, centerOpacity: 1, neighborOpacity: 0.88, farOpacity: 0.55 };
        }
        const parseNum = function (val, fallback) { const n = parseFloat(String(val).trim()); return isNaN(n) ? fallback : n; };
        return {
            centerScale: parseNum(s.getPropertyValue('--carousel-center-scale'), 1),
            neighborScale: parseNum(s.getPropertyValue('--carousel-neighbor-scale'), 0.82),
            farScale: parseNum(s.getPropertyValue('--carousel-far-scale'), 0.65),
            centerOpacity: parseNum(s.getPropertyValue('--carousel-center-opacity'), 1),
            neighborOpacity: parseNum(s.getPropertyValue('--carousel-neighbor-opacity'), 0.88),
            farOpacity: parseNum(s.getPropertyValue('--carousel-far-opacity'), 0.55)
        };
    }
    function getScaleAndOpacity(distance, tokens) {
        const d = Math.abs(distance);
        if (d === 0) return { scale: tokens.centerScale, opacity: tokens.centerOpacity };
        if (d === 1) return { scale: tokens.neighborScale, opacity: tokens.neighborOpacity };
        return { scale: tokens.farScale, opacity: tokens.farOpacity };
    }
    function applyTransforms() {
        const tokens = readWheelTokens();
        const n = itemEls.length;
        for (let i = 0; i < n; i++) {
            const distance = i - currentIndex;
            const so = getScaleAndOpacity(distance, tokens);
            const z = 10 + visibleWindow - Math.abs(distance);
            itemEls[i].style.setProperty('--carousel-offset', String(distance));
            itemEls[i].style.setProperty('--carousel-item-scale', String(so.scale));
            itemEls[i].style.setProperty('--carousel-item-opacity', String(so.opacity));
            itemEls[i].style.zIndex = z;
            itemEls[i].setAttribute('aria-current', i === currentIndex ? 'true' : 'false');
        }
        leftBtn.disabled = currentIndex <= 0;
        rightBtn.disabled = currentIndex >= n - 1;
    }

    let displayIndex = 0;
    items.forEach(function (it) {
        const kind = (it.kind && String(it.kind).trim()) || 'poster';
        const itemEl = document.createElement('div');
        const idx = displayIndex;
        itemEl.className = 'hero-scenes-wheel-item hero-scenes-wheel-item--' + kind;
        itemEl.setAttribute('data-index', String(idx));
        itemEl.setAttribute('aria-current', idx === 0 ? 'true' : 'false');
        if (kind === 'scene') {
            const imageUrl = (it.imageUrl && String(it.imageUrl).trim()) || '';
            if (!imageUrl) return;
            const caption = (it.caption && String(it.caption).trim()) || '';
            const sourceUrl = (it.sourceUrl && String(it.sourceUrl).trim()) || '';
            const card = document.createElement('div');
            card.className = 'attachment-scene-card attachment-scene-card--wheel';
            const imgWrap = document.createElement('div');
            imgWrap.className = 'attachment-scene-card-img-wrap';
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = caption || 'Scene';
            img.loading = 'lazy';
            imgWrap.appendChild(img);
            card.appendChild(imgWrap);
            if (caption) {
                const capEl = document.createElement('span');
                capEl.className = 'media-strip-card-label attachment-scene-caption';
                capEl.textContent = caption;
                card.appendChild(capEl);
            }
            if (sourceUrl) {
                const link = document.createElement('a');
                link.href = sourceUrl;
                link.target = '_blank';
                link.rel = 'noopener';
                link.className = 'hero-scenes-wheel-item-link';
                link.appendChild(card);
                itemEl.appendChild(link);
            } else {
                itemEl.appendChild(card);
            }
        } else {
            const heroShape = attachmentItemToHeroShape(it);
            if (!heroShape) return;
            const heroWrap = document.createElement('div');
            heroWrap.className = 'hero-scenes-wheel-poster-wrap';
            const heroCard = createHeroCard(heroShape, { link: !!heroShape.page_url });
            if (heroCard) heroWrap.appendChild(heroCard);
            itemEl.appendChild(heroWrap);
        }
        itemEl.addEventListener('click', function (e) {
            const i = parseInt(itemEl.getAttribute('data-index'), 10);
            if (i !== currentIndex) {
                e.preventDefault();
                currentIndex = i;
                applyTransforms();
            }
        });
        track.appendChild(itemEl);
        itemEls.push(itemEl);
        displayIndex++;
    });

    if (itemEls.length === 0) return root;

    const leftBtn = document.createElement('button');
    leftBtn.type = 'button';
    leftBtn.className = 'hero-scenes-carousel-arrow hero-scenes-carousel-arrow-left';
    leftBtn.setAttribute('aria-label', 'Previous');
    leftBtn.innerHTML = arrowLeftSvg;
    leftBtn.addEventListener('click', function () {
        if (currentIndex <= 0) return;
        currentIndex--;
        applyTransforms();
    });
    const rightBtn = document.createElement('button');
    rightBtn.type = 'button';
    rightBtn.className = 'hero-scenes-carousel-arrow hero-scenes-carousel-arrow-right';
    rightBtn.setAttribute('aria-label', 'Next');
    rightBtn.innerHTML = arrowRightSvg;
    rightBtn.addEventListener('click', function () {
        if (currentIndex >= itemEls.length - 1) return;
        currentIndex++;
        applyTransforms();
    });

    root.appendChild(leftBtn);
    root.appendChild(rightBtn);
    inner.appendChild(track);
    root.appendChild(inner);

    applyTransforms();
    requestAnimationFrame(function () {
        if (root.isConnected) {
            applyTransforms();
            requestAnimationFrame(function () {
                root.classList.add('hero-scenes-carousel-wrap--animated');
            });
        }
    });
    return root;
}

/* ── _attachmentItemToCarouselItem (internal) ── */

function _attachmentItemToCarouselItem(it) {
    const kind = (it.kind && String(it.kind).trim()) || '';
    if (kind === 'scene') return null;
    let title = (it.title != null && String(it.title).trim()) || '';
    if (!title) {
        const heroShape = attachmentItemToHeroShape(it);
        if (!heroShape) return null;
        title = heroShape.movie_title || '';
        if (!title) return null;
        return {
            title: title,
            year: heroShape.year,
            imageUrl: heroShape.primary_image_url || '',
            sourceUrl: heroShape.page_url || '',
            tmdbId: heroShape.tmdbId || undefined,
            mediaType: heroShape.mediaType || undefined,
            pageId: it.pageId || it.page_id || undefined
        };
    }
    return {
        title: title,
        year: typeof it.year === 'number' ? it.year : undefined,
        imageUrl: (it.imageUrl && String(it.imageUrl).trim()) || '',
        sourceUrl: (it.sourceUrl && String(it.sourceUrl).trim()) || '',
        tmdbId: it.tmdbId || it.tmdb_id || undefined,
        mediaType: it.mediaType || it.media_type || undefined,
        pageId: it.pageId || it.page_id || undefined
    };
}

/* ── createAttachmentsFromSections ── */

export function createAttachmentsFromSections(sections) {
    if (!sections || sections.length === 0) return null;
    const wrap = document.createElement('div');
    wrap.className = 'attachments';

    const allMovieItems = [];
    // Universe of "related movies" (non-hero) to anchor sub-context hubs.
    // These items are attached onto each carousel element so the click handler
    // can propagate a bounded candidate set into the created sub-conversation.
    const relatedMoviesUniverseItems = [];
    const sceneItems = [];
    let hasScenes = false;
    const heroSceneItems = [];

    sections.forEach(function (section) {
        const type = (section.type && String(section.type).trim()) || 'movie_list';
        const items = Array.isArray(section.items) ? section.items : [];
        if (items.length === 0) return;

        if (type === 'scenes') {
            const seenSceneUrls = {};
            items.forEach(function (it) {
                const url = (it.imageUrl && String(it.imageUrl).trim()) || '';
                if (url && !seenSceneUrls[url]) {
                    seenSceneUrls[url] = true;
                    const o = {}; for (const k in it) o[k] = it[k]; o.kind = 'scene';
                    sceneItems.push(o);
                }
            });
            return;
        }

        if (type === 'primary_movie') {
            const sectionHasScenes = items.some(function (it) { return (it.kind && String(it.kind).trim()) === 'scene'; });
            if (sectionHasScenes) {
                hasScenes = true;
                items.forEach(function (it) { heroSceneItems.push(it); });
                return;
            }
        }

        items.forEach(function (it) {
            const ci = _attachmentItemToCarouselItem(it);
            if (!ci) return;
            allMovieItems.push(ci);
            // Only non-hero movie lists become the hub universe.
            // `primary_movie` is the clicked/anchored context; `movie_list` / `did_you_mean`
            // are the candidate universe for related titles.
            if (type === 'movie_list' || type === 'did_you_mean') {
                relatedMoviesUniverseItems.push(ci);
            }
        });
    });

    const seenTitles = {};
    const uniqueMovieItems = allMovieItems.filter(function (it) {
        const key = it.title.toLowerCase();
        if (seenTitles[key]) return false;
        seenTitles[key] = true;
        return true;
    });

    // Convert candidate universe items into the shape expected by the Movie Hub.
    // (The hub/mini-hero rendering tolerates `imageUrl` and `pageUrl` shorthands.)
    const relatedSeen = {};
    const relatedMoviesUniverse = relatedMoviesUniverseItems
        .filter(function (it) {
            if (!it || !it.title) return false;
            const key = String(it.title).toLowerCase();
            if (relatedSeen[key]) return false;
            relatedSeen[key] = true;
            return true;
        })
        .map(function (it) {
            const pageUrl = (it.sourceUrl && String(it.sourceUrl).trim()) || '';
            return {
                title: it.title,
                year: it.year,
                imageUrl: it.imageUrl,
                // Provide both keys so hub rendering + where-to-watch can pick either.
                primary_image_url: it.imageUrl,
                pageUrl: pageUrl || undefined,
                page_url: pageUrl || undefined,
                pageId: it.pageId,
                tmdbId: it.tmdbId,
                mediaType: it.mediaType
            };
        })
        .filter(function (it) {
            return it && it.title;
        });

    // Attach the parent reply’s candidate universe to each carousel item (legacy / optional).
    // Sub-conversation hub **display** must not use this as `contextMovie.relatedMovies` —
    // that list is the same for every poster and is not “similar to the clicked title.”
    // `layout.addSubConversationFromPoster` ignores it when building the sub anchor.
    if (uniqueMovieItems.length && relatedMoviesUniverse.length) {
        uniqueMovieItems.forEach(function (it) {
            it.relatedMovies = relatedMoviesUniverse;
        });
    }

    if (hasScenes && heroSceneItems.length > 0) {
        const sectionEl = document.createElement('div');
        sectionEl.className = 'attachments-section attachments-section-primary-movie';
        sectionEl.setAttribute('data-section-type', 'primary_movie');
        const heroScenesCarousel = createHeroAndScenesCarousel(heroSceneItems);
        if (heroScenesCarousel) sectionEl.appendChild(heroScenesCarousel);
        wrap.appendChild(sectionEl);
    }

    if (uniqueMovieItems.length > 0) {
        const movieSection = document.createElement('div');
        movieSection.className = 'attachments-section attachments-section-primary-movie';
        movieSection.setAttribute('data-section-type', 'primary_movie');
        const carousel = PosterCarouselWheel(uniqueMovieItems, 0, function () {}, { visibleWindow: 2 });
        movieSection.appendChild(carousel);
        wrap.appendChild(movieSection);
    }

    if (sceneItems.length > 0) {
        const sceneSectionEl = document.createElement('div');
        sceneSectionEl.className = 'attachments-section attachments-section-scenes';
        sceneSectionEl.setAttribute('data-section-type', 'scenes');
        const scenesCarousel = createHeroAndScenesCarousel(sceneItems);
        if (scenesCarousel) sceneSectionEl.appendChild(scenesCarousel);
        wrap.appendChild(sceneSectionEl);
    }

    if (wrap.children.length === 0) return null;
    return wrap;
}

/* ── createUnifiedMovieStrip ── */

export function createUnifiedMovieStrip(norm) {
    const hasStrip = norm.media_strip && norm.media_strip.movie_title;
    const candidates = Array.isArray(norm.media_candidates) ? norm.media_candidates : [];
    const hasCandidates = candidates.length > 0;
    if (!hasStrip && !hasCandidates) return null;

    // When a hero strip and candidates are present, attach relatedMovies to the hero.
    // This lets sub-conversations reuse the same list for the Movie Hub without
    // another backend lookup.
    if (hasStrip && hasCandidates && !Array.isArray(norm.media_strip.relatedMovies)) {
        norm.media_strip.relatedMovies = candidates.map(function (c) {
            if (!c || typeof c !== 'object') return null;
            const title = String(c.movie_title != null ? c.movie_title : '').trim();
            if (!title) return null;
            const item = {
                title: title,
                year: typeof c.year === 'number' ? c.year : undefined
            };
            if (c.primary_image_url) item.primary_image_url = String(c.primary_image_url).trim();
            if (c.page_url) item.page_url = String(c.page_url).trim();
            return item;
        }).filter(function (m) { return m !== null; });
    }

    const wrap = document.createElement('div');
    wrap.className = 'media-strip';
    const layout = document.createElement('div');
    layout.className = 'media-strip-layout';

    if (hasStrip) {
        const heroCard = createHeroCard(norm.media_strip, { link: !!norm.media_strip.page_url });
        if (heroCard) layout.appendChild(heroCard);
    }
    candidates.forEach(function (c) {
        const card = createHeroCard(c, { link: true });
        if (card) layout.appendChild(card);
    });

    wrap.appendChild(layout);
    return wrap;
}

export function renderSimilarCluster(container, movies, options) {
    if (!container) return;
    container.innerHTML = '';
    options = options || {};
    const titleText = (options.title && String(options.title).trim())
        ? options.title.trim()
        : 'Similar titles';
    if (!Array.isArray(movies) || movies.length === 0) {
        container.classList.add('hidden');
        return;
    }
    const heading = document.createElement('h3');
    heading.className = 'movie-hub-cluster-title';
    heading.textContent = titleText;
    container.appendChild(heading);
    const strip = document.createElement('div');
    strip.className = 'movie-hub-cluster-strip';
    movies.forEach(function (m) {
        if (!m) return;
        const card = createHeroCard({
            movie_title: m.movie_title || m.title,
            title: m.title,
            year: m.year,
            primary_image_url: m.primary_image_url || m.imageUrl,
            page_url: m.page_url || m.pageUrl,
            tmdbId: m.tmdbId || m.tmdb_id,
            mediaType: m.mediaType || m.media_type
        }, { link: true });
        if (card) strip.appendChild(card);
    });
    if (!strip.children.length) {
        container.classList.add('hidden');
        return;
    }
    container.appendChild(strip);
    container.classList.remove('hidden');
}
