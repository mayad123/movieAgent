/**
 * CineMind — production app.
 * Depends on: js/config.js (window.CINEMIND_CONFIG.apiBase).
 * UI contract: web/UI_RESPONSE_CONTRACT.md (hero, gallery, placeholder, error handling).
 */
(function () {
    'use strict';

    var API_BASE = window.CINEMIND_CONFIG && window.CINEMIND_CONFIG.apiBase ? window.CINEMIND_CONFIG.apiBase : 'http://localhost:8000';

    /**
     * Normalize API result into a safe meta object for rendering.
     * Contract: UI_RESPONSE_CONTRACT.md. Never throws.
     */
    function normalizeMeta(meta) {
        if (meta == null || typeof meta !== 'object') return null;
        var out = {};
        out.content = String(meta.response != null ? meta.response : meta.answer != null ? meta.answer : '').trim();
        out.actualAgentMode = meta.actualAgentMode || meta.agent_mode || null;
        out.requestedAgentMode = meta.requestedAgentMode || null;
        out.modeFallback = !!meta.modeFallback;
        out.modeOverrideReason = meta.modeOverrideReason && String(meta.modeOverrideReason).trim() || null;
        out.toolsUsed = Array.isArray(meta.toolsUsed) ? meta.toolsUsed : null;
        if (meta.media_strip != null && typeof meta.media_strip === 'object') {
            var title = String(meta.media_strip.movie_title != null ? meta.media_strip.movie_title : '').trim();
            out.media_strip = title ? {
                movie_title: title,
                primary_image_url: meta.media_strip.primary_image_url && String(meta.media_strip.primary_image_url).trim(),
                page_url: meta.media_strip.page_url && String(meta.media_strip.page_url).trim(),
                year: typeof meta.media_strip.year === 'number' ? meta.media_strip.year : undefined,
                thumbnail_urls: Array.isArray(meta.media_strip.thumbnail_urls)
                    ? meta.media_strip.thumbnail_urls.slice(0, 3).map(function (u) { return u != null ? String(u).trim() : ''; }).filter(Boolean)
                    : []
            } : null;
        } else {
            out.media_strip = null;
        }
        out.media_gallery_label = meta.media_gallery_label && String(meta.media_gallery_label).trim() || null;
        if (Array.isArray(meta.media_candidates) && meta.media_candidates.length > 0) {
            out.media_candidates = meta.media_candidates
                .filter(function (c) { return c != null && typeof c === 'object'; })
                .map(function (c) {
                    var t = String(c.movie_title != null ? c.movie_title : '').trim();
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
        /* Attachments (P0): sections[] with type, title, items. Prefer when present; fallback to media_strip/media_candidates. */
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

    var sidebar = document.getElementById('sidebar');
    var sidebarToggle = document.getElementById('sidebarToggle');
    var rightPanel = document.getElementById('rightPanel');
    var whereToWatchDrawerEl = document.getElementById('whereToWatchDrawer');
    var whereToWatchDrawerTitle = document.getElementById('whereToWatchDrawerTitle');
    var whereToWatchDrawerClose = document.getElementById('whereToWatchDrawerClose');
    var whereToWatchDrawerContent = document.getElementById('whereToWatchDrawerContent');
    var whereToWatchDrawerLoading = document.getElementById('whereToWatchDrawerLoading');
    var whereToWatchDrawerResults = document.getElementById('whereToWatchDrawerResults');
    var whereToWatchDrawerEmpty = document.getElementById('whereToWatchDrawerEmpty');
    var whereToWatchDrawerError = document.getElementById('whereToWatchDrawerError');
    var whereToWatchDrawerErrorText = document.getElementById('whereToWatchDrawerErrorText');

    var whereToWatchDrawerState = {
        open: false,
        movie: null,
        status: 'idle',
        results: null,
        error: null
    };

    /**
     * Normalize Where to Watch error message: dedupe repeated sentences and use canonical phrasing.
     */
    function normalizeWhereToWatchErrorMessage(msg) {
        if (!msg || typeof msg !== 'string') return msg || '';
        var s = msg.trim();
        if (!s) return s;
        var canonical = 'Title not found. Try a different spelling or add the year.';
        if (s.indexOf(canonical) !== -1) return canonical;
        if (s.length % 2 === 0 && s.slice(0, s.length / 2) === s.slice(s.length / 2)) return s.slice(0, s.length / 2).trim();
        var parts = s.split(/\s*\.\s+/).filter(Boolean);
        var seen = {};
        var out = [];
        for (var i = 0; i < parts.length; i++) {
            var p = (parts[i] || '').trim();
            if (p && !seen[p]) { seen[p] = true; out.push(p); }
        }
        return out.length ? out.join('. ') + (s.slice(-1) === '.' ? '' : '') : s;
    }

    /**
     * Call GET /api/watch/where-to-watch and pass normalized result to callback.
     * movie: { title, year?, pageUrl?, pageId?, tmdbId?, mediaType? }. Uses tmdbId when present; otherwise title+year (backend does Watchmode name lookup).
     */
    function fetchWhereToWatch(movie, callback) {
        var tmdbId = (movie && (movie.tmdbId != null ? String(movie.tmdbId).trim() : (movie.pageId != null ? String(movie.pageId).trim() : ''))) || '';
        if (!tmdbId && movie && movie.pageUrl && typeof movie.pageUrl === 'string') {
            var m = /themoviedb\.org\/movie\/(\d+)/i.exec(movie.pageUrl);
            if (m) tmdbId = m[1];
        }
        var title = (movie && movie.title && String(movie.title).trim()) || '';
        if (!tmdbId && !title) {
            callback(new Error('Movie title or ID is required to find where to watch.'));
            return;
        }
        var mediaType = (movie.mediaType && String(movie.mediaType).trim()) || 'movie';
        var country = (movie.country && String(movie.country).trim()) || 'US';
        var params = new URLSearchParams({ mediaType: mediaType, country: country });
        if (tmdbId) params.set('tmdbId', tmdbId);
        if (title) params.set('title', title);
        if (movie.year != null && movie.year !== '') params.set('year', String(movie.year));
        var url = API_BASE + '/api/watch/where-to-watch?' + params.toString();
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

    function closeWhereToWatchDrawer() {
        whereToWatchDrawerState.open = false;
        whereToWatchDrawerState.movie = null;
        whereToWatchDrawerState.status = 'idle';
        whereToWatchDrawerState.results = null;
        whereToWatchDrawerState.error = null;
        if (whereToWatchDrawerEl) {
            whereToWatchDrawerEl.classList.remove('open');
            whereToWatchDrawerEl.setAttribute('aria-hidden', 'true');
        }
    }

    function renderWhereToWatchDrawerContent() {
        var s = whereToWatchDrawerState;
        if (!whereToWatchDrawerLoading || !whereToWatchDrawerResults || !whereToWatchDrawerEmpty || !whereToWatchDrawerError || !whereToWatchDrawerErrorText) return;
        whereToWatchDrawerLoading.classList.add('hidden');
        whereToWatchDrawerResults.classList.add('hidden');
        whereToWatchDrawerEmpty.classList.add('hidden');
        whereToWatchDrawerError.classList.add('hidden');
        if (s.status === 'loading') {
            whereToWatchDrawerLoading.classList.remove('hidden');
            return;
        }
        if (s.status === 'error') {
            whereToWatchDrawerError.classList.remove('hidden');
            whereToWatchDrawerErrorText.textContent = s.error || 'Something went wrong.';
            return;
        }
        var hasOffers = s.results && Array.isArray(s.results.offers) && s.results.offers.length > 0;
        var hasGroups = s.results && Array.isArray(s.results.groups) && s.results.groups.length > 0;
        if (s.status === 'empty' || (s.status === 'success' && !hasOffers && !hasGroups)) {
            whereToWatchDrawerEmpty.classList.remove('hidden');
            return;
        }
        if (s.status === 'success' && s.results && (hasOffers || hasGroups)) {
            whereToWatchDrawerResults.classList.remove('hidden');
            whereToWatchDrawerResults.innerHTML = '';
            if (hasOffers) {
                var accessOrder = ['subscription', 'free', 'rent', 'buy', 'tve', 'unknown'];
                var byType = {};
                s.results.offers.forEach(function (offer) {
                    var at = (offer.accessType || 'unknown').toLowerCase();
                    if (!byType[at]) byType[at] = [];
                    byType[at].push(offer);
                });
                accessOrder.forEach(function (at) {
                    if (!byType[at] || byType[at].length === 0) return;
                    var groupTitle = document.createElement('div');
                    groupTitle.className = 'where-to-watch-group-title';
                    groupTitle.textContent = at.charAt(0).toUpperCase() + at.slice(1);
                    whereToWatchDrawerResults.appendChild(groupTitle);
                    var list = document.createElement('ul');
                    list.className = 'where-to-watch-offer-list';
                    byType[at].forEach(function (offer) {
                        var li = document.createElement('li');
                        li.className = 'where-to-watch-offer';
                        var info = document.createElement('div');
                        info.className = 'where-to-watch-offer-info';
                        var provider = document.createElement('div');
                        provider.className = 'where-to-watch-offer-provider';
                        provider.textContent = (offer.provider && offer.provider.name) || 'Provider';
                        info.appendChild(provider);
                        if (offer.quality && String(offer.quality).trim()) {
                            var quality = document.createElement('span');
                            quality.className = 'where-to-watch-offer-quality';
                            quality.textContent = String(offer.quality).trim();
                            info.appendChild(quality);
                        }
                        if (offer.price && typeof offer.price.amount === 'number') {
                            var price = document.createElement('div');
                            price.className = 'where-to-watch-offer-price';
                            price.textContent = (offer.price.currency || 'USD') + ' ' + Number(offer.price.amount);
                            info.appendChild(price);
                        }
                        li.appendChild(info);
                        var url = (offer.webUrl && offer.webUrl.trim()) || (offer.iosUrl && offer.iosUrl.trim()) || (offer.androidUrl && offer.androidUrl.trim());
                        if (url) {
                            var openLink = document.createElement('a');
                            openLink.className = 'where-to-watch-offer-open';
                            openLink.href = url;
                            openLink.target = '_blank';
                            openLink.rel = 'noopener';
                            openLink.textContent = 'Open';
                            li.appendChild(openLink);
                        }
                        list.appendChild(li);
                    });
                    whereToWatchDrawerResults.appendChild(list);
                });
            } else {
                s.results.groups.forEach(function (group) {
                    var groupTitle = document.createElement('div');
                    groupTitle.className = 'where-to-watch-group-title';
                    groupTitle.textContent = group.label || group.accessType || 'Watch';
                    whereToWatchDrawerResults.appendChild(groupTitle);
                    var list = document.createElement('ul');
                    list.className = 'where-to-watch-offer-list';
                    (group.offers || []).forEach(function (offer) {
                        var li = document.createElement('li');
                        li.className = 'where-to-watch-offer';
                        var info = document.createElement('div');
                        info.className = 'where-to-watch-offer-info';
                        var provider = document.createElement('div');
                        provider.className = 'where-to-watch-offer-provider';
                        provider.textContent = offer.providerName || (offer.provider && offer.provider.name) || 'Provider';
                        info.appendChild(provider);
                        if (offer.price && typeof offer.price.amount === 'number') {
                            var price = document.createElement('div');
                            price.className = 'where-to-watch-offer-price';
                            price.textContent = (offer.price.currency || 'USD') + ' ' + Number(offer.price.amount);
                            info.appendChild(price);
                        }
                        li.appendChild(info);
                        var url = offer.webUrl || offer.deeplink;
                        if (url) {
                            var openLink = document.createElement('a');
                            openLink.className = 'where-to-watch-offer-open';
                            openLink.href = url;
                            openLink.target = '_blank';
                            openLink.rel = 'noopener';
                            openLink.textContent = 'Open';
                            li.appendChild(openLink);
                        }
                        list.appendChild(li);
                    });
                    whereToWatchDrawerResults.appendChild(list);
                });
            }
        }
    }

    function openWhereToWatchDrawer(movie) {
        if (!movie || !movie.title) return;
        whereToWatchDrawerState.open = true;
        whereToWatchDrawerState.movie = movie;
        whereToWatchDrawerState.status = 'loading';
        whereToWatchDrawerState.results = null;
        whereToWatchDrawerState.error = null;
        if (whereToWatchDrawerEl) {
            whereToWatchDrawerEl.classList.add('open');
            whereToWatchDrawerEl.setAttribute('aria-hidden', 'false');
        }
        if (whereToWatchDrawerTitle) {
            whereToWatchDrawerTitle.textContent = 'Where to watch: ' + (movie.title + (movie.year != null ? ' (' + movie.year + ')' : ''));
        }
        renderWhereToWatchDrawerContent();
        if (typeof fetchWhereToWatch === 'function') {
            fetchWhereToWatch(movie, function (err, data) {
                if (err) {
                    whereToWatchDrawerState.status = 'error';
                    whereToWatchDrawerState.error = normalizeWhereToWatchErrorMessage(err.message || String(err));
                } else if (!data) {
                    whereToWatchDrawerState.status = 'empty';
                    whereToWatchDrawerState.results = null;
                } else {
                    var hasOffers = Array.isArray(data.offers) && data.offers.length > 0;
                    var hasGroups = Array.isArray(data.groups) && data.groups.length > 0;
                    if (hasOffers || hasGroups) {
                        whereToWatchDrawerState.status = 'success';
                        whereToWatchDrawerState.results = data;
                    } else {
                        whereToWatchDrawerState.status = 'empty';
                        whereToWatchDrawerState.results = data;
                    }
                }
                renderWhereToWatchDrawerContent();
            });
        } else {
            setTimeout(function () {
                whereToWatchDrawerState.status = 'empty';
                renderWhereToWatchDrawerContent();
            }, 600);
        }
    }

    function onWhereToWatch(movie) {
        openWhereToWatchDrawer(movie);
    }

    if (whereToWatchDrawerClose) {
        whereToWatchDrawerClose.addEventListener('click', function () { closeWhereToWatchDrawer(); });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && whereToWatchDrawerState.open) {
            closeWhereToWatchDrawer();
        }
    });

    var rightPanelToggle = document.getElementById('rightPanelToggle');
    var conversationList = document.getElementById('conversationList');
    var conversationTitle = document.getElementById('conversationTitle');
    var headerMainView = document.getElementById('headerMainView');
    var headerSubView = document.getElementById('headerSubView');
    var headerBreadcrumb = document.getElementById('headerBreadcrumb');
    var subConversationMovieBadge = document.getElementById('subConversationMovieBadge');
    var mainEl = document.querySelector('main.main');
    var chatColumn = document.getElementById('chatColumn');
    var messageList = document.getElementById('messageList');
    var retrievingRow = document.getElementById('retrievingRow');
    var composerInput = document.getElementById('composerInput');
    var sendBtn = document.getElementById('sendBtn');
    var newChatBtn = document.getElementById('newChatBtn');
    var useRealAgentToggle = document.getElementById('useRealAgentToggle');
    var modeBadge = document.getElementById('modeBadge');

    /**
     * Agent mode is SESSION-SCOPED (app-level), not per conversation.
     * Do not store mode on conversation objects. Switching conversations does not change mode.
     * Outgoing requests always use this session value; changing mode affects subsequent requests only.
     */
    var useRealAgent = (function () {
        try {
            return sessionStorage.getItem('cinemind_useRealAgent') === '1';
        } catch (e) { return false; }
    })();

    /** Session-only: user has confirmed Real Agent this session (no modal again until reload). */
    var realAgentConfirmedThisSession = useRealAgent;

    /**
     * Conversation state: main tabs only; each can have sub-threads.
     * conversations[] = main conversations only.
     * Each: { id, title, messages, collection, activeScope, subConversations: [ { id, title, contextMovie, messages } ] }.
     * activeConversationId = main conversation id.
     * activeSubConversationId = null (main thread) or sub-conversation id (sub thread).
     */
    var conversations = [];
    var activeConversationId = null;
    var activeSubConversationId = null;
    /** 'main' = parent conversation screen; 'sub' = dedicated sub-conversation screen (SubConversationView). */
    var conversationView = 'main';
    /** Per main conversation: last-opened view so switching tabs preserves parent vs sub. */
    var lastViewByConversationId = {};
    /** Scroll position of main thread when user navigated to sub; restored on Back. */
    var mainScrollTopByConversationId = {};
    /** When set, renderMessages will restore this scroll instead of scrolling to bottom. */
    var restoreScrollTop = null;
    var isSending = false;
    var app = document.getElementById('app');

    /** Projects from server (id, name, createdAt, description). Populated on init. */
    var projects = [];

    /** Client-side de-dupe: keys we have already sent for asset capture (projectId|conversationId|msgIndex|urlOrTitle). */
    var savedAssetKeys = new Set();

    /** Canonical key for de-duplication: pageId > pageUrl > normalized title + image URL. */
    function getAssetKey(title, imageUrl, pageUrl, pageId) {
        var pid = (pageId && String(pageId).trim()) || '';
        var url = (pageUrl && String(pageUrl).trim()) || '';
        if (pid) return 'id:' + pid;
        if (url) return 'url:' + url;
        var t = normalizeTitle(title);
        var img = (imageUrl && String(imageUrl).trim()) || '';
        return 'title:' + t + '|' + img;
    }
    function normalizeTitle(s) {
        return String(s || '').trim().toLowerCase().replace(/\s+/g, ' ');
    }
    function pageIdFromUrl(url) {
        if (!url || typeof url !== 'string') return '';
        var m = /\/wiki\/([^/?#]+)/.exec(url);
        return m ? decodeURIComponent(m[1]) : '';
    }
    function collectionHasKey(collection, key) {
        if (!Array.isArray(collection) || !key) return false;
        for (var i = 0; i < collection.length; i++) {
            var item = collection[i];
            var itemKey = (item && item.assetKey) || getAssetKey(item.title, item.imageUrl, item.pageUrl, item.pageId);
            if (itemKey === key) return true;
        }
        return false;
    }

    /**
     * Whether the given poster is already in the active collection (same de-dupe key).
     * Active collection = conversation collection when scope is "This Conversation",
     * or the current project's assets when scope is a project. Uses getActiveConversation()
     * so behavior is identical on main and sub-conversation screens.
     * poster: { title, imageUrl, pageUrl?, pageId? }
     */
    function isPosterInActiveCollection(poster) {
        var conv = getActiveConversation();
        if (!conv) return false;
        var scope = (conv.activeScope != null && conv.activeScope !== '') ? conv.activeScope : 'This Conversation';
        var key = getAssetKey(poster.title, poster.imageUrl, poster.pageUrl, poster.pageId);
        if (!key) return false;
        if (scope === 'This Conversation') {
            var collection = (conv.collection) ? conv.collection : [];
            return collectionHasKey(collection, key);
        }
        if (String(scope).indexOf('project:') === 0) {
            var projectId = String(scope).slice(8);
            if (currentProjectId !== projectId || !Array.isArray(currentProjectAssets)) return false;
            for (var j = 0; j < currentProjectAssets.length; j++) {
                var a = currentProjectAssets[j];
                var assetKey = getAssetKey(a.title, (a.posterImageUrl || a.storedRef) || '', a.pageUrl, a.pageId);
                if (assetKey === key) return true;
            }
        }
        return false;
    }

    function addToCollection(title, imageUrl, pageUrl, pageId) {
        var conv = getActiveConversation();
        if (!conv || !title) return;
        var poster = { title: title, imageUrl: imageUrl, pageUrl: pageUrl, pageId: pageId };
        if (isPosterInActiveCollection(poster)) {
            showAlreadyAddedToast();
            return;
        }
        var scope = (conv.activeScope != null && conv.activeScope !== '') ? conv.activeScope : 'This Conversation';
        if (String(scope).indexOf('project:') === 0) {
            var projectId = String(scope).slice(8);
            var assetPayload = {
                title: String(title).trim(),
                posterImageUrl: (imageUrl && String(imageUrl).trim()) || undefined,
                pageUrl: (pageUrl && String(pageUrl).trim()) || undefined,
                pageId: (pageId && String(pageId).trim()) || undefined,
                conversationId: (conv.id && String(conv.id).trim()) || undefined
            };
            if (conversationView === 'sub' && activeSubConversationId) assetPayload.subConversationId = activeSubConversationId;
            var payload = { assets: [assetPayload] };
            fetch(API_BASE + '/api/projects/' + encodeURIComponent(projectId) + '/assets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(function (res) {
                    if (!res.ok) return Promise.reject(new Error('Failed to save'));
                    return res.json();
                })
                .then(function (result) {
                    var proj = projects.filter(function (p) { return p.id === projectId; })[0];
                    showSavedToProjectToast(proj ? proj.name : null);
                    loadProjectAssets(projectId);
                    updateRightPanelScope();
                })
                .catch(function () {
                    showFallbackToast('Could not add to project. Check that the server supports projects.');
                });
            return;
        }
        if (!conv.collection) conv.collection = [];
        var key = getAssetKey(title, imageUrl, pageUrl, pageId);
        var item = {
            title: String(title).trim(),
            imageUrl: (imageUrl && String(imageUrl).trim()) || '',
            assetKey: key
        };
        if (pageUrl && String(pageUrl).trim()) item.pageUrl = String(pageUrl).trim();
        if (pageId && String(pageId).trim()) item.pageId = String(pageId).trim();
        if (conversationView === 'sub' && activeSubConversationId) item.addedFromSubConversationId = activeSubConversationId;
        conv.collection.push(item);
        renderCollectionPanel();
        /* Do not re-render messages: it tears down the carousel DOM and breaks subsequent "Add to Collection" clicks. */
    }

    /** Max stack layers (above/below active) from panel height for adaptive layout. */
    function getMaxStackLayers(container) {
        if (!container || !container.offsetParent) return 2;
        var h = container.clientHeight || 0;
        var rem = typeof getComputedStyle !== 'undefined' && document.documentElement
            ? parseFloat(getComputedStyle(document.documentElement).fontSize) || 16 : 16;
        var heightRem = h / rem;
        if (heightRem < 18) return 1;
        if (heightRem < 26) return 2;
        return 3;
    }

    /** Layer class from distance to active (delta). Arrows disable at ends; no wrap. */
    function getStackLayerClass(delta) {
        if (delta === 0) return 'stack-layer-active';
        if (delta < 0) return 'stack-layer-above-' + Math.min(Math.abs(delta), 3);
        return 'stack-layer-below-' + Math.min(delta, 3);
    }

    function createOneStackItem(item, index, layerClass, onActiveChange) {
        var title = String((item && item.title) || '').trim() || 'Unnamed';
        var imageUrl = (item && item.imageUrl) && String(item.imageUrl).trim() ? item.imageUrl : '';
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'right-panel-stack-item ' + layerClass;
        btn.setAttribute('data-index', String(index));
        btn.setAttribute('aria-label', title);
        btn.setAttribute('title', title);
        btn.addEventListener('click', function () {
            if (typeof onActiveChange === 'function') onActiveChange(index);
        });
        var poster = document.createElement('div');
        poster.className = 'stack-item-poster';
        if (imageUrl) {
            var img = document.createElement('img');
            img.src = imageUrl;
            img.alt = title;
            img.loading = 'lazy';
            poster.appendChild(img);
        } else {
            var ph = document.createElement('div');
            ph.className = 'stack-item-placeholder';
            ph.textContent = '?';
            poster.appendChild(ph);
        }
        btn.appendChild(poster);
        var titleEl = document.createElement('span');
        titleEl.className = 'stack-item-title';
        titleEl.textContent = title;
        titleEl.setAttribute('title', title);
        btn.appendChild(titleEl);
        var savedBadge = document.createElement('span');
        savedBadge.className = 'stack-item-saved';
        savedBadge.textContent = 'Saved';
        savedBadge.setAttribute('aria-hidden', 'true');
        btn.appendChild(savedBadge);
        return btn;
    }

    /**
     * Render a layered poster stack in the right panel. Center = activeIndex (largest).
     * items: array of { title, imageUrl }. onActiveChange(index) when selection changes.
     * Arrows at ends are disabled (no wrap). Keyboard Up/Down when panel focused.
     */
    function renderPosterStack(container, items, activeIndex, onActiveChange) {
        if (!container) return;
        container.innerHTML = '';
        container._stackUpdate = null;
        stackNavigationState = null;
        if (!Array.isArray(items) || items.length === 0) {
            var empty = document.createElement('p');
            empty.className = 'right-panel-stack-empty';
            empty.textContent = 'No posters yet. Add from the conversation.';
            container.appendChild(empty);
            return;
        }
        var count = items.length;
        var active = Math.max(0, Math.min(activeIndex, count - 1));
        var maxLayers = getMaxStackLayers(container);
        var start = Math.max(0, active - maxLayers);
        var end = Math.min(count - 1, active + maxLayers);

        var wrapper = document.createElement('div');
        wrapper.className = 'right-panel-stack-wrapper';

        var upBtn = document.createElement('button');
        upBtn.type = 'button';
        upBtn.className = 'right-panel-stack-arrow right-panel-stack-arrow-up';
        upBtn.setAttribute('aria-label', 'Previous poster');
        upBtn.setAttribute('title', 'Previous poster');
        upBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>';
        upBtn.disabled = active <= 0;
        upBtn.addEventListener('click', function () {
            if (active > 0 && typeof onActiveChange === 'function') onActiveChange(active - 1);
        });

        var stackView = document.createElement('div');
        stackView.className = 'right-panel-stack-view';
        var rail = document.createElement('div');
        rail.className = 'right-panel-stack-rail';
        for (var i = start; i <= end; i++) {
            var layerClass = getStackLayerClass(i - active);
            rail.appendChild(createOneStackItem(items[i], i, layerClass, onActiveChange));
        }
        stackView.appendChild(rail);

        var downBtn = document.createElement('button');
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
            var newActive = Math.max(0, Math.min(newIndex, count - 1));
            var newStart = Math.max(0, newActive - maxLayers);
            var newEnd = Math.min(count - 1, newActive + maxLayers);
            var existing = {};
            var idx;
            for (idx = 0; idx < rail.children.length; idx++) {
                var el = rail.children[idx];
                var di = parseInt(el.getAttribute('data-index'), 10);
                existing[di] = el;
            }
            for (idx = newStart; idx <= newEnd; idx++) {
                var layerClass = getStackLayerClass(idx - newActive);
                if (existing[idx]) {
                    existing[idx].className = 'right-panel-stack-item ' + layerClass;
                } else {
                    rail.appendChild(createOneStackItem(items[idx], idx, layerClass, onActiveChange));
                }
            }
            var toRemove = [];
            for (var k in existing) {
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

    var stackNavigationState = null;

    function renderCollectionPanel() {
        var container = document.getElementById('collectionList');
        if (!container) return;
        container._stackUpdate = null;
        stackNavigationState = null;
        var conv = getActiveConversation();
        var items = (conv && conv.collection) ? conv.collection : [];
        if (items.length === 0) {
            container.innerHTML = '';
            var empty = document.createElement('p');
            empty.className = 'right-panel-stack-empty';
            empty.textContent = 'No posters yet. Add from the conversation.';
            container.appendChild(empty);
            return;
        }
        var list = document.createElement('div');
        list.className = 'right-panel-collection-list';
        items.forEach(function (item, idx) {
            var title = String((item && item.title) || '').trim() || 'Unnamed';
            var imageUrl = (item && item.imageUrl) && String(item.imageUrl).trim() ? item.imageUrl : '';
            var card = document.createElement('div');
            card.className = 'right-panel-collection-item';
            card.setAttribute('data-index', String(idx));
            var posterWrap = document.createElement('div');
            posterWrap.className = 'right-panel-collection-item-poster-wrap';
            if (imageUrl) {
                var img = document.createElement('img');
                img.src = imageUrl;
                img.alt = title;
                img.loading = 'lazy';
                posterWrap.appendChild(img);
            } else {
                var ph = document.createElement('div');
                ph.className = 'right-panel-collection-placeholder';
                ph.textContent = '?';
                posterWrap.appendChild(ph);
            }
            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'right-panel-collection-item-remove';
            removeBtn.setAttribute('aria-label', 'Remove from collection');
            removeBtn.setAttribute('title', 'Remove from collection');
            removeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
            removeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var i = parseInt(card.getAttribute('data-index'), 10);
                if (conv && conv.collection && !isNaN(i) && i >= 0 && i < conv.collection.length) {
                    conv.collection.splice(i, 1);
                    renderCollectionPanel();
                }
            });
            posterWrap.appendChild(removeBtn);
            card.appendChild(posterWrap);
            var titleEl = document.createElement('span');
            titleEl.className = 'right-panel-collection-item-title';
            titleEl.textContent = title;
            card.appendChild(titleEl);
            list.appendChild(card);
        });
        container.innerHTML = '';
        container.appendChild(list);
    }

    function nextId() {
        return 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
    }

    /**
     * Create a sub-conversation (child thread) anchored to a movie and switch the UI to it.
     * movie: { title, year?, pageUrl?, pageId?, imageUrl? }
     * Sub is stored under the active main conversation's subConversations[].
     */
    function addSubConversationFromPoster(movie) {
        var main = getActiveConversation();
        if (!main || !movie || !String(movie.title || '').trim()) return;
        var title = String(movie.title).trim();
        var subTitle = 'Re: ' + title + (movie.year != null ? ' (' + movie.year + ')' : '');
        var contextMovie = {
            title: title,
            year: movie.year,
            pageUrl: (movie.pageUrl && String(movie.pageUrl).trim()) || undefined,
            pageId: (movie.pageId && String(movie.pageId).trim()) || undefined,
            imageUrl: (movie.imageUrl && String(movie.imageUrl).trim()) || undefined
        };
        var sub = {
            id: nextId(),
            title: subTitle,
            contextMovie: contextMovie,
            messages: []
        };
        if (!main.subConversations) main.subConversations = [];
        main.subConversations.unshift(sub);
        if (conversationView === 'main' && chatColumn) mainScrollTopByConversationId[main.id] = chatColumn.scrollTop;
        activeSubConversationId = sub.id;
        conversationView = 'sub';
        lastViewByConversationId[main.id] = { view: 'sub', subId: sub.id };
        updateConversationList();
        renderMessages();
        renderCollectionPanel();
        updateHeaderForView();
        updateRightPanelScope();
        if (composerInput) composerInput.focus();
    }

    /** Return the active main conversation (for collection, scope, etc.). */
    function getActiveConversation() {
        if (!activeConversationId) return null;
        for (var i = 0; i < conversations.length; i++) {
            if (conversations[i].id === activeConversationId) return conversations[i];
        }
        return null;
    }

    /**
     * Return the currently active thread: either main or a sub-conversation.
     * { main, sub, messages, title } so callers can read/write messages and title.
     */
    function getActiveThread() {
        var main = getActiveConversation();
        if (!main) return { main: null, sub: null, messages: [], title: 'New conversation' };
        if (!activeSubConversationId) {
            return { main: main, sub: null, messages: main.messages, title: main.title || 'New conversation' };
        }
        var subs = main.subConversations && Array.isArray(main.subConversations) ? main.subConversations : [];
        for (var j = 0; j < subs.length; j++) {
            if (subs[j].id === activeSubConversationId) {
                return {
                    main: main,
                    sub: subs[j],
                    messages: subs[j].messages,
                    title: subs[j].title || 'Re: ' + (subs[j].contextMovie && subs[j].contextMovie.title) || 'Sub'
                };
            }
        }
        activeSubConversationId = null;
        return { main: main, sub: null, messages: main.messages, title: main.title || 'New conversation' };
    }

    function addConversation() {
        var id = nextId();
        conversations.unshift({
            id: id,
            title: 'New conversation',
            messages: [],
            collection: [],
            activeScope: 'This Conversation',
            subConversations: []
        });
        activeConversationId = id;
        activeSubConversationId = null;
        conversationView = 'main';
        lastViewByConversationId[id] = { view: 'main', subId: null };
        composerInput.value = '';
        updateConversationList();
        renderMessages();
        renderCollectionPanel();
        updateHeaderForView();
        updateRightPanelScope();
        if (composerInput) composerInput.focus();
    }

    /**
     * Switch to a thread: parent (main) or sub-conversation. Left-panel navigation.
     * Parent click → parent conversation screen (main view). Sub click → SubConversationView (sub view).
     * Saves scroll when leaving main view. Persists last-opened sub per parent when opening a sub.
     * mainId: main conversation id. subId: optional sub-conversation id (undefined/null = open parent screen).
     */
    function switchConversation(mainId, subId) {
        if (mainId === activeConversationId && (subId == null ? !activeSubConversationId : subId === activeSubConversationId)) return;
        if (conversationView === 'main' && chatColumn && activeConversationId) mainScrollTopByConversationId[activeConversationId] = chatColumn.scrollTop;
        activeConversationId = mainId;
        if (subId != null && subId !== '') {
            activeSubConversationId = subId;
            conversationView = 'sub';
            lastViewByConversationId[mainId] = { view: 'sub', subId: subId };
        } else {
            activeSubConversationId = null;
            conversationView = 'main';
        }
        restoreScrollTop = (conversationView === 'main') ? (mainScrollTopByConversationId[mainId] != null ? mainScrollTopByConversationId[mainId] : null) : null;
        updateConversationList();
        renderMessages();
        renderCollectionPanel();
        updateHeaderForView();
        updateRightPanelScope();
    }

    function updateHeaderTitle() {
        var thread = getActiveThread();
        conversationTitle.textContent = thread.title || 'New conversation';
    }

    /**
     * Update header for current view: main (title only) or sub (back + breadcrumb "Parent → Movie (year)").
     * Call after changing conversationView, activeConversationId, or activeSubConversationId.
     */
    function updateHeaderForView() {
        if (!headerMainView || !headerSubView) return;
        if (mainEl) mainEl.classList.toggle('sub-conversation-view', conversationView === 'sub');
        if (conversationView === 'sub') {
            headerMainView.classList.add('hidden');
            headerSubView.classList.remove('hidden');
            var thread = getActiveThread();
            var main = getActiveConversation();
            var parentName = (main && (main.title || 'New conversation')) ? (main.title || 'New conversation') : 'New conversation';
            var movieLabel = thread.sub && thread.sub.contextMovie
                ? (thread.sub.contextMovie.title || '') + (thread.sub.contextMovie.year != null ? ' (' + thread.sub.contextMovie.year + ')' : '')
                : (thread.title || '');
            if (headerBreadcrumb) headerBreadcrumb.textContent = parentName + ' → ' + (movieLabel || 'Sub');
            if (subConversationMovieBadge) {
                subConversationMovieBadge.classList.remove('hidden');
                subConversationMovieBadge.setAttribute('aria-hidden', 'false');
                var movie = thread.sub && thread.sub.contextMovie;
                var imgUrl = movie && movie.imageUrl && String(movie.imageUrl).trim();
                if (imgUrl) {
                    var existing = subConversationMovieBadge.querySelector('img');
                    if (existing) existing.src = imgUrl;
                    else {
                        var placeholder = subConversationMovieBadge.querySelector('.sub-conversation-badge-placeholder');
                        if (placeholder) placeholder.remove();
                        var img = document.createElement('img');
                        img.src = imgUrl;
                        img.alt = movie.title ? (movie.title + (movie.year != null ? ' (' + movie.year + ')' : '')) : 'Movie';
                        subConversationMovieBadge.appendChild(img);
                    }
                } else {
                    var im = subConversationMovieBadge.querySelector('img');
                    if (im) im.remove();
                    if (!subConversationMovieBadge.querySelector('.sub-conversation-badge-placeholder')) {
                        var span = document.createElement('span');
                        span.className = 'sub-conversation-badge-placeholder';
                        span.textContent = '\uD83C\uDFAC';
                        subConversationMovieBadge.appendChild(span);
                    }
                }
            }
        } else {
            headerMainView.classList.remove('hidden');
            headerSubView.classList.add('hidden');
            var t = getActiveThread();
            if (conversationTitle) conversationTitle.textContent = t.title || 'New conversation';
            if (subConversationMovieBadge) {
                subConversationMovieBadge.classList.add('hidden');
                subConversationMovieBadge.setAttribute('aria-hidden', 'true');
            }
        }
    }

    /** Sync right-panel scope label and dropdown highlight from the active conversation’s activeScope (UI-only, per-tab). */
    function getScopeDisplayName(scope) {
        if (!scope || scope === 'This Conversation') return 'This Conversation';
        if (String(scope).indexOf('project:') === 0) {
            var id = String(scope).slice(8);
            for (var i = 0; i < projects.length; i++) {
                if (projects[i].id === id) return projects[i].name;
            }
            return scope;
        }
        return scope;
    }

    /** Sync right-panel scope label and dropdown highlight from the active conversation's activeScope (UI-only, per-tab). */
    function updateRightPanelScope() {
        var scopeLabel = document.getElementById('rightPanelScope');
        var dropdown = document.getElementById('rightPanelDropdown');
        var conv = getActiveConversation();
        var scope = (conv && conv.activeScope != null && conv.activeScope !== '') ? conv.activeScope : 'This Conversation';
        if (conv && (conv.activeScope == null || conv.activeScope === '')) conv.activeScope = 'This Conversation';
        if (scopeLabel) scopeLabel.textContent = getScopeDisplayName(scope);
        if (dropdown) {
            dropdown.querySelectorAll('.right-panel-dropdown-item').forEach(function (btn) {
                var itemScope = btn.getAttribute('data-scope') || btn.textContent.trim();
                btn.classList.toggle('is-active', itemScope === scope);
            });
        }
        var isProjectScope = scope && String(scope).indexOf('project:') === 0;
        var projectId = isProjectScope ? String(scope).slice(8) : '';
        var collectionsEl = document.getElementById('collectionList');
        var projectAssetsEl = document.getElementById('rightPanelProjectAssets');
        if (collectionsEl) collectionsEl.classList.toggle('hidden', isProjectScope);
        if (projectAssetsEl) projectAssetsEl.classList.toggle('hidden', !isProjectScope);
        if (isProjectScope && projectId) loadProjectAssets(projectId);
        else renderCollectionPanel();
    }

    var projectAssetsActiveIndex = {};
    var currentProjectAssets = [];
    var currentProjectId = null;

    /** Load one project by id and render its assets as a poster stack. */
    function loadProjectAssets(projectId) {
        var strip = document.getElementById('rightPanelProjectAssetsList');
        if (!strip) return;
        strip.innerHTML = '';
        var url = API_BASE + '/api/projects/' + encodeURIComponent(projectId);
        url += (url.indexOf('?') !== -1 ? '&' : '?') + '_=' + Date.now();
        fetch(url)
            .then(function (res) {
                if (!res.ok) throw new Error('Project not found');
                return res.json();
            })
            .then(function (project) {
                var assets = (project && project.assets) ? project.assets : [];
                currentProjectId = projectId;
                currentProjectAssets = assets;
                renderProjectAssetsStack();
            })
            .catch(function () {
                strip.innerHTML = '';
                currentProjectId = null;
                currentProjectAssets = [];
            });
    }

    /** Render the current project's assets as a simple poster + title list (same style as "This Conversation" collection). */
    function renderProjectAssetsStack() {
        var strip = document.getElementById('rightPanelProjectAssetsList');
        if (!strip) return;
        strip._stackUpdate = null;
        stackNavigationState = null;
        var items = currentProjectAssets;
        if (items.length === 0) {
            strip.innerHTML = '';
            var empty = document.createElement('p');
            empty.className = 'right-panel-stack-empty';
            empty.textContent = 'No saved posters in this project yet.';
            strip.appendChild(empty);
            return;
        }
        var list = document.createElement('div');
        list.className = 'right-panel-collection-list';
        var projectId = currentProjectId;
        items.forEach(function (item, idx) {
            var title = String((item && item.title) || '').trim() || 'Unnamed';
            var imageUrl = (item && item.storedRef && String(item.storedRef).trim()) ? item.storedRef.trim() : (item && item.posterImageUrl && String(item.posterImageUrl).trim()) ? item.posterImageUrl.trim() : '';
            var card = document.createElement('div');
            card.className = 'right-panel-collection-item';
            card.setAttribute('data-index', String(idx));
            var posterWrap = document.createElement('div');
            posterWrap.className = 'right-panel-collection-item-poster-wrap';
            if (imageUrl) {
                var img = document.createElement('img');
                img.src = imageUrl;
                img.alt = title;
                img.loading = 'lazy';
                posterWrap.appendChild(img);
            } else {
                var ph = document.createElement('div');
                ph.className = 'right-panel-collection-placeholder';
                ph.textContent = '?';
                posterWrap.appendChild(ph);
            }
            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'right-panel-collection-item-remove';
            removeBtn.setAttribute('aria-label', 'Remove from project');
            removeBtn.setAttribute('title', 'Remove from project');
            removeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
            removeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var i = parseInt(card.getAttribute('data-index'), 10);
                if (!projectId || isNaN(i) || i < 0) return;
                fetch(API_BASE + '/api/projects/' + encodeURIComponent(projectId) + '/assets/' + i, { method: 'DELETE' })
                    .then(function (res) {
                        if (!res.ok) return Promise.reject(new Error('Failed to remove'));
                        return res.json();
                    })
                    .then(function () { loadProjectAssets(projectId); })
                    .catch(function () { showFallbackToast('Could not remove from project.'); });
            });
            posterWrap.appendChild(removeBtn);
            card.appendChild(posterWrap);
            var titleEl = document.createElement('span');
            titleEl.className = 'right-panel-collection-item-title';
            titleEl.textContent = title;
            card.appendChild(titleEl);
            list.appendChild(card);
        });
        strip.innerHTML = '';
        strip.appendChild(list);
    }

    /** Load projects from API and populate dropdown. Call on app init. */
    function loadProjects() {
        fetch(API_BASE + '/api/projects')
            .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error('Failed to load projects')); })
            .then(function (data) {
                projects = Array.isArray(data) ? data : [];
                renderProjectsDropdown();
                updateRightPanelScope();
            })
            .catch(function () {
                projects = [];
                renderProjectsDropdown();
            });
    }

    /** Fill the Projects section of the dropdown with buttons (data-scope="project:<id>"). */
    function renderProjectsDropdown() {
        var container = document.getElementById('rightPanelProjectsList');
        if (!container) return;
        container.innerHTML = '';
        projects.forEach(function (p) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'right-panel-dropdown-item';
            btn.setAttribute('role', 'menuitem');
            btn.setAttribute('data-scope', 'project:' + (p.id || ''));
            btn.textContent = p.name || 'Unnamed';
            container.appendChild(btn);
        });
    }

    /** Show a short confirmation that assets were saved to a project (does not spam chat). */
    function showSavedToProjectToast(projectName) {
        var el = document.getElementById('rightPanelSavedToast');
        if (!el) return;
        el.textContent = 'Saved to ' + (projectName || 'Project');
        el.classList.add('is-visible');
        clearTimeout(showSavedToProjectToast._hideId);
        showSavedToProjectToast._hideId = setTimeout(function () {
            el.classList.remove('is-visible');
        }, 2500);
    }

    /** Show "Already Added" toast (single toast, no stacking). */
    function showAlreadyAddedToast() {
        var el = document.getElementById('rightPanelSavedToast');
        if (!el) return;
        el.textContent = 'Already Added';
        el.classList.add('is-visible');
        clearTimeout(showAlreadyAddedToast._hideId);
        showAlreadyAddedToast._hideId = setTimeout(function () {
            el.classList.remove('is-visible');
        }, 2000);
    }

    /** Show fallback reason when real agent failed and playground was used (no silent crash). */
    function showFallbackToast(message) {
        var el = document.getElementById('rightPanelSavedToast');
        if (!el) return;
        el.textContent = message && message.length > 60 ? message.slice(0, 57) + '\u2026' : (message || 'Switched to Playground.');
        el.classList.add('is-visible', 'toast-fallback');
        clearTimeout(showFallbackToast._hideId);
        showFallbackToast._hideId = setTimeout(function () {
            el.classList.remove('is-visible', 'toast-fallback');
        }, 4500);
    }

    /**
     * When project scope is active, capture media items from this message into the project.
     * Auto-save on render; de-duplicated so the same poster does not save on every re-render.
     * Asset contract: posterImageUrl, title, pageUrl, conversationId (timestamp set by server).
     */
    function captureAssetsForProjectScope(conversationId, msgIndex, norm) {
        var conv = getActiveConversation();
        if (!conv || !norm) return;
        var scope = conv.activeScope;
        if (!scope || String(scope).indexOf('project:') !== 0) return;
        var projectId = String(scope).slice(8);
        if (!projectId) return;

        var items = [];
        if (norm.media_strip && norm.media_strip.movie_title) items.push(norm.media_strip);
        if (Array.isArray(norm.media_candidates)) items.push.apply(items, norm.media_candidates);

        var batch = [];
        var keysToMark = [];
        for (var j = 0; j < items.length; j++) {
            var it = items[j];
            var title = String((it.movie_title || it.title || '')).trim();
            var pageUrl = (it.page_url && String(it.page_url).trim()) || '';
            var posterUrl = (it.primary_image_url && String(it.primary_image_url).trim()) || '';
            var key = projectId + '|' + (conversationId || '') + '|' + msgIndex + '|' + (pageUrl || posterUrl || title);
            if (savedAssetKeys.has(key)) continue;
            batch.push({
                posterImageUrl: posterUrl || undefined,
                title: title || 'Unnamed',
                pageUrl: pageUrl || undefined,
                conversationId: conversationId || undefined
            });
            keysToMark.push(key);
        }
        if (batch.length === 0) return;

        fetch(API_BASE + '/api/projects/' + encodeURIComponent(projectId) + '/assets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ assets: batch })
        })
            .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error('Failed to save assets')); })
            .then(function (result) {
                keysToMark.forEach(function (k) { savedAssetKeys.add(k); });
                var added = (result && result.added) || 0;
                if (added > 0) {
                    var proj = projects.filter(function (p) { return p.id === projectId; })[0];
                    showSavedToProjectToast(proj ? proj.name : null);
                    loadProjectAssets(projectId);
                }
            })
            .catch(function () { /* ignore */ });
    }

    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
        app.classList.toggle('sidebar-collapsed', sidebar.classList.contains('collapsed'));
    }
    function toggleRightPanel() {
        if (rightPanel) rightPanel.classList.toggle('collapsed');
        app.classList.toggle('right-panel-open', rightPanel && !rightPanel.classList.contains('collapsed'));
    }
    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
    if (rightPanelToggle) rightPanelToggle.addEventListener('click', toggleRightPanel);

    (function setupStackKeyboard() {
        document.addEventListener('keydown', function (e) {
            if (!rightPanel || !rightPanel.contains(document.activeElement)) return;
            var isPrev = e.key === 'ArrowUp' || e.key === 'ArrowLeft';
            var isNext = e.key === 'ArrowDown' || e.key === 'ArrowRight';
            if (!isPrev && !isNext) return;
            if (!stackNavigationState) return;
            e.preventDefault();
            if (isPrev) stackNavigationState.onPrev();
            else stackNavigationState.onNext();
        });
    })();

    (function setupRightPanelHamburger() {
        var hamburger = document.getElementById('rightPanelHamburger');
        var dropdown = document.getElementById('rightPanelDropdown');
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
            var isOpen = dropdown.classList.contains('is-open');
            if (isOpen) closeDropdown();
            else openDropdown();
        }

        hamburger.addEventListener('click', function (e) {
            e.stopPropagation();
            toggleDropdown();
        });

        document.addEventListener('click', function (e) {
            if (!dropdown.classList.contains('is-open')) return;
            if (dropdown.contains(e.target) || hamburger.contains(e.target)) return;
            closeDropdown();
        });

        dropdown.addEventListener('click', function (e) {
            var btn = e.target && e.target.closest && e.target.closest('.right-panel-dropdown-item');
            if (!btn) return;
            e.preventDefault();
            var conv = getActiveConversation();
            var scope = btn.getAttribute('data-scope') || btn.textContent.trim();
            if (conv) conv.activeScope = scope;
            updateRightPanelScope();
            closeDropdown();
        });
    })();

    function startNewChat() {
        addConversation();
    }
    if (newChatBtn) newChatBtn.addEventListener('click', startNewChat);

    function navigateBackToParentConversation() {
        var main = getActiveConversation();
        if (!main || conversationView !== 'sub') return;
        lastViewByConversationId[main.id] = { view: 'main', subId: null };
        conversationView = 'main';
        restoreScrollTop = mainScrollTopByConversationId[main.id] != null ? mainScrollTopByConversationId[main.id] : 0;
        activeSubConversationId = null;
        updateConversationList();
        renderMessages();
        renderCollectionPanel();
        updateHeaderForView();
        updateRightPanelScope();
    }
    var headerBackBtn = document.getElementById('headerBackBtn');
    if (headerBackBtn) headerBackBtn.addEventListener('click', navigateBackToParentConversation);

    function renameSubConversation() {
        var thread = getActiveThread();
        if (!thread.sub) return;
        var current = thread.sub.title || (thread.sub.contextMovie && thread.sub.contextMovie.title) || 'Re: movie';
        var newTitle = typeof prompt === 'function' ? prompt('Rename sub-conversation', current) : null;
        if (newTitle != null && String(newTitle).trim() !== '') {
            thread.sub.title = String(newTitle).trim();
            updateConversationList();
            updateHeaderForView();
        }
    }
    /**
     * Close = hide from list only. Sets sub.archived = true; data (messages, etc.) is not deleted.
     * Navigates to parent so the user is not left on a hidden sub. State remains stable across tab switching.
     */
    function closeSubConversation() {
        var thread = getActiveThread();
        var main = getActiveConversation();
        if (!thread.sub || !main) return;
        thread.sub.archived = true;
        switchConversation(main.id);
    }
    var headerSubRenameBtn = document.getElementById('headerSubRenameBtn');
    var headerSubCloseBtn = document.getElementById('headerSubCloseBtn');
    if (headerSubRenameBtn) headerSubRenameBtn.addEventListener('click', renameSubConversation);
    if (headerSubCloseBtn) headerSubCloseBtn.addEventListener('click', closeSubConversation);

    var filmIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></svg>';

    /**
     * Left panel: parent conversations with nested sub-conversations. Parent row = main thread id;
     * sub rows = sub thread ids. Click parent → parent conversation screen; click sub → SubConversationView.
     * Active highlight reflects current screen/thread (mainActive when on main view, subActive when on that sub).
     */
    function updateConversationList() {
        if (!conversationList) return;
        conversationList.innerHTML = '';
        conversations.forEach(function (mainConv) {
            var group = document.createElement('div');
            group.className = 'conversation-group';

            var mainActive = mainConv.id === activeConversationId && !activeSubConversationId;
            var mainEl = document.createElement('div');
            var mainLabel = mainConv.title || 'New conversation';
            mainEl.className = 'conversation-item' + (mainActive ? ' active' : '');
            mainEl.textContent = mainLabel.length > 36 ? mainLabel.slice(0, 36) + '\u2026' : mainLabel;
            mainEl.setAttribute('title', mainLabel);
            mainEl.setAttribute('data-thread-type', 'parent');
            mainEl.setAttribute('data-main-id', mainConv.id);
            mainEl.addEventListener('click', function () { switchConversation(mainConv.id); });
            group.appendChild(mainEl);

            var subs = mainConv.subConversations && Array.isArray(mainConv.subConversations)
                ? mainConv.subConversations.filter(function (s) { return !s.archived; })
                : [];
            subs.forEach(function (sub) {
                var subActive = mainConv.id === activeConversationId && sub.id === activeSubConversationId;
                var subEl = document.createElement('div');
                var subLabel = sub.title || 'Re: ' + (sub.contextMovie && sub.contextMovie.title) || 'Sub';
                subEl.className = 'conversation-item conversation-item-sub' + (subActive ? ' active' : '');
                subEl.setAttribute('title', subLabel);
                subEl.setAttribute('data-thread-type', 'sub');
                subEl.setAttribute('data-main-id', mainConv.id);
                subEl.setAttribute('data-sub-id', sub.id);
                subEl.addEventListener('click', function () { switchConversation(mainConv.id, sub.id); });

                var thumbWrap = document.createElement('span');
                thumbWrap.className = 'conversation-item-sub-thumb';
                var imgUrl = sub.contextMovie && sub.contextMovie.imageUrl && String(sub.contextMovie.imageUrl).trim();
                if (imgUrl) {
                    var thumbImg = document.createElement('img');
                    thumbImg.src = imgUrl;
                    thumbImg.alt = '';
                    thumbImg.loading = 'lazy';
                    thumbWrap.appendChild(thumbImg);
                } else {
                    thumbWrap.classList.add('conversation-item-sub-thumb-icon');
                    thumbWrap.innerHTML = filmIconSvg;
                }
                subEl.appendChild(thumbWrap);

                var labelSpan = document.createElement('span');
                labelSpan.className = 'conversation-item-sub-label';
                labelSpan.textContent = subLabel.length > 32 ? subLabel.slice(0, 32) + '\u2026' : subLabel;
                subEl.appendChild(labelSpan);

                group.appendChild(subEl);
            });

            conversationList.appendChild(group);
        });
    }

    function showRetrieving() {
        if (retrievingRow) retrievingRow.classList.remove('hidden');
        if (chatColumn) chatColumn.scrollTo({ top: chatColumn.scrollHeight, behavior: 'smooth' });
    }
    function hideRetrieving() {
        if (retrievingRow) retrievingRow.classList.add('hidden');
    }

    function appendMessage(role, content, meta) {
        var thread = getActiveThread();
        if (!thread.messages) return;
        thread.messages.push({ role: role, content: content, meta: meta || null });
        if (thread.messages.length === 1 && role === 'user') {
            var title = content.length > 40 ? content.slice(0, 40) + '\u2026' : content;
            if (thread.sub) thread.sub.title = title;
            else if (thread.main) thread.main.title = title;
            updateHeaderForView();
            updateConversationList();
        }
        renderMessages();
    }

    function escapeHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    var addIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>';
    var messageIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    var whereToWatchIconSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>';

    /* One hero-sized card: poster + overlay (add / add to conversation) + label. */
    function createHeroCard(item, options) {
        options = options || {};
        var title = String((item.movie_title || item.title || '')).trim();
        if (!title) return null;
        var labelText = title;
        if (item.year != null) labelText += ' (' + item.year + ')';
        var imgUrl = (item.primary_image_url && item.primary_image_url.trim()) || '';
        var href = (item.page_url && item.page_url.trim()) || '';
        var isLink = !!href && options.link !== false;

        var card = isLink ? document.createElement('a') : document.createElement('div');
        card.className = 'media-strip-card';
        if (isLink) {
            card.href = href;
            card.target = '_blank';
            card.rel = 'noopener';
        }

        var poster = document.createElement('div');
        poster.className = 'media-strip-card-poster';
        if (imgUrl) {
            var inner = document.createElement('div');
            inner.className = 'media-strip-card-poster-inner';
            poster.classList.add('media-strip-skeleton');
            var img = document.createElement('img');
            img.src = imgUrl;
            img.alt = title;
            img.loading = 'lazy';
            img.onload = function () { poster.classList.remove('media-strip-skeleton'); };
            img.onerror = function () {
                poster.classList.remove('media-strip-skeleton');
                var ph = document.createElement('div');
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

        var topRightOverlay = document.createElement('div');
        topRightOverlay.className = 'media-strip-card-overlay media-strip-card-overlay--top-right';
        var whereToWatchBtn = document.createElement('button');
        whereToWatchBtn.type = 'button';
        whereToWatchBtn.className = 'media-strip-card-action media-strip-card-action--tooltip-below';
        whereToWatchBtn.setAttribute('data-tooltip', 'Where to watch');
        whereToWatchBtn.setAttribute('title', 'Where to watch');
        whereToWatchBtn.setAttribute('aria-label', 'Where to watch');
        whereToWatchBtn.innerHTML = whereToWatchIconSvg;
        whereToWatchBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            onWhereToWatch({
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

        var overlay = document.createElement('div');
        overlay.className = 'media-strip-card-overlay';
        var pageUrl = href || '';
        var pageId = pageIdFromUrl(pageUrl);
        var isInCollection = isPosterInActiveCollection({ title: title, imageUrl: imgUrl, pageUrl: pageUrl, pageId: pageId });
        var addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'media-strip-card-action' + (isInCollection ? ' is-added' : '');
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
            return false;
        });
        var msgBtn = document.createElement('button');
        msgBtn.type = 'button';
        msgBtn.className = 'media-strip-card-action';
        msgBtn.setAttribute('data-tooltip', 'Add to Conversation');
        msgBtn.setAttribute('title', 'Add to Conversation');
        msgBtn.setAttribute('aria-label', 'Add to Conversation');
        msgBtn.innerHTML = messageIconSvg;
        msgBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (typeof addSubConversationFromPoster === 'function') {
                addSubConversationFromPoster({
                    title: title,
                    year: item.year,
                    pageUrl: pageUrl || undefined,
                    pageId: pageId || undefined,
                    imageUrl: imgUrl || undefined
                });
            }
        });
        overlay.appendChild(addBtn);
        overlay.appendChild(msgBtn);
        if (isInCollection) {
            var addedLabel = document.createElement('span');
            addedLabel.className = 'media-strip-card-already-added';
            addedLabel.textContent = 'Already Added';
            overlay.appendChild(addedLabel);
        }
        poster.appendChild(overlay);
        card.appendChild(poster);

        var lbl = document.createElement('span');
        lbl.className = 'media-strip-card-label';
        lbl.textContent = labelText;
        card.appendChild(lbl);
        return card;
    }

    /* Small candidate card for "Did you mean?": poster + label (uses .media-candidates-card CSS). */
    function createCandidateCard(item, options) {
        options = options || {};
        var title = String((item.movie_title || item.title || '')).trim();
        if (!title) return null;
        var labelText = title;
        if (item.year != null) labelText += ' (' + item.year + ')';
        var imgUrl = (item.primary_image_url && item.primary_image_url.trim()) || (item.imageUrl && String(item.imageUrl).trim()) || '';
        var href = (item.page_url && item.page_url.trim()) || (item.sourceUrl && String(item.sourceUrl).trim()) || '';
        var isLink = !!href && options.link !== false;

        var card = isLink ? document.createElement('a') : document.createElement('div');
        card.className = 'media-candidates-card';
        if (isLink) {
            card.href = href;
            card.target = '_blank';
            card.rel = 'noopener';
        }

        if (imgUrl) {
            var img = document.createElement('img');
            img.src = imgUrl;
            img.alt = title;
            img.loading = 'lazy';
            card.appendChild(img);
        } else {
            var ph = document.createElement('div');
            ph.className = 'media-candidates-placeholder';
            ph.textContent = title;
            card.appendChild(ph);
        }

        var lbl = document.createElement('span');
        lbl.className = 'media-candidates-card-label';
        lbl.textContent = labelText;
        card.appendChild(lbl);
        return card;
    }

    /* Attachment item (movie card) -> same shape as createHeroCard expects for reuse. */
    function attachmentItemToHeroShape(item) {
        var title = (item.title != null && String(item.title).trim()) || '';
        if (!title) return null;
        return {
            movie_title: title,
            year: typeof item.year === 'number' ? item.year : undefined,
            primary_image_url: (item.imageUrl && String(item.imageUrl).trim()) || '',
            page_url: (item.sourceUrl && String(item.sourceUrl).trim()) || '',
            tmdbId: item.tmdbId || item.tmdb_id || undefined,
            mediaType: item.mediaType || item.media_type || undefined
        };
    }

    var arrowLeftSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>';
    var arrowRightSvg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>';

    /**
     * Reusable Poster Carousel Wheel (cover-flow style).
     * @param {Array<{title: string, year?: number, imageUrl?: string, sourceUrl?: string}>} items - Poster items.
     * @param {number} activeIndex - Current center index (0-based).
     * @param {function(number)} onChangeIndex - Called when center changes (newIndex).
     * @param {{ visibleWindow?: number }} options - visibleWindow = items to show each side of center (default 2).
     * @returns {HTMLElement} Root container (class: poster-carousel-wheel).
     */
    function PosterCarouselWheel(items, activeIndex, onChangeIndex, options) {
        options = options || {};
        var visibleWindow = typeof options.visibleWindow === 'number' ? options.visibleWindow : 2;

        var root = document.createElement('div');
        root.className = 'poster-carousel-wheel';
        var inner = document.createElement('div');
        inner.className = 'poster-carousel-wheel-inner';
        var track = document.createElement('div');
        track.className = 'poster-carousel-wheel-track';

        var currentIndex = Math.max(0, Math.min(activeIndex, items.length - 1));
        if (items.length === 0) return root;

        /** Read wheel scale/opacity tokens from CSS (rem/ratio-based; same for all wheel contexts). */
        function readWheelTokens() {
            var s = root.isConnected ? window.getComputedStyle(root) : (document.documentElement ? window.getComputedStyle(document.documentElement) : null);
            if (!s) {
                return { centerScale: 1, neighborScale: 0.82, farScale: 0.65, centerOpacity: 1, neighborOpacity: 0.88, farOpacity: 0.55 };
            }
            var parseNum = function (val, fallback) { var n = parseFloat(String(val).trim()); return isNaN(n) ? fallback : n; };
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
            var d = Math.abs(distance);
            if (d === 0) return { scale: tokens.centerScale, opacity: tokens.centerOpacity };
            if (d === 1) return { scale: tokens.neighborScale, opacity: tokens.neighborOpacity };
            return { scale: tokens.farScale, opacity: tokens.farOpacity };
        }

        function applyTransforms() {
            var tokens = readWheelTokens();
            var n = itemEls.length;
            for (var i = 0; i < n; i++) {
                var distance = i - currentIndex;
                var so = getScaleAndOpacity(distance, tokens);
                var z = 10 + visibleWindow - Math.abs(distance);
                itemEls[i].style.setProperty('--carousel-offset', String(distance));
                itemEls[i].style.setProperty('--carousel-item-scale', String(so.scale));
                itemEls[i].style.setProperty('--carousel-item-opacity', String(so.opacity));
                itemEls[i].style.zIndex = z;
                itemEls[i].setAttribute('aria-current', i === currentIndex ? 'true' : 'false');
            }
            leftBtn.disabled = currentIndex <= 0;
            rightBtn.disabled = currentIndex >= n - 1;
        }

        var itemEls = [];
        items.forEach(function (it, idx) {
            var title = (it.title != null && String(it.title).trim()) || '';
            if (!title) return;
            var labelText = title;
            if (typeof it.year === 'number') labelText += ' (' + it.year + ')';
            var imgUrl = (it.imageUrl && String(it.imageUrl).trim()) || '';
            var href = (it.sourceUrl && String(it.sourceUrl).trim()) || '';

            var el = href ? document.createElement('a') : document.createElement('div');
            el.className = 'poster-carousel-wheel-item';
            el.setAttribute('data-index', idx);
            if (href) {
                el.href = href;
                el.target = '_blank';
                el.rel = 'noopener';
            }
            var posterWrap = document.createElement('div');
            posterWrap.className = 'poster-carousel-wheel-poster-wrap';
            if (imgUrl) {
                var img = document.createElement('img');
                img.src = imgUrl;
                img.alt = title;
                img.loading = 'lazy';
                posterWrap.appendChild(img);
            } else {
                var ph = document.createElement('div');
                ph.className = 'poster-carousel-wheel-item-placeholder';
                ph.textContent = title;
                posterWrap.appendChild(ph);
            }
            var pageUrl = href || '';
            var pageId = (it.pageId != null && String(it.pageId).trim()) ? String(it.pageId).trim() : undefined;
            var isInCollection = typeof isPosterInActiveCollection === 'function' && isPosterInActiveCollection({ title: title, imageUrl: imgUrl, pageUrl: pageUrl, pageId: pageId });
            var topRightOverlayCarousel = document.createElement('div');
            topRightOverlayCarousel.className = 'poster-carousel-wheel-overlay poster-carousel-wheel-overlay--top-right';
            var whereToWatchEl = document.createElement('button');
            whereToWatchEl.type = 'button';
            whereToWatchEl.className = 'poster-carousel-wheel-action poster-carousel-wheel-action--tooltip-below';
            whereToWatchEl.setAttribute('data-tooltip', 'Where to watch');
            whereToWatchEl.setAttribute('title', 'Where to watch');
            whereToWatchEl.setAttribute('aria-label', 'Where to watch');
            whereToWatchEl.innerHTML = whereToWatchIconSvg;
            whereToWatchEl.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                onWhereToWatch({
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

            var overlay = document.createElement('div');
            overlay.className = 'poster-carousel-wheel-overlay';
            var addBtn = document.createElement('button');
            addBtn.type = 'button';
            addBtn.className = 'poster-carousel-wheel-action' + (isInCollection ? ' is-added' : '');
            addBtn.setAttribute('data-tooltip', isInCollection ? 'Already Added' : 'Add to Collection');
            addBtn.setAttribute('title', isInCollection ? 'Already Added' : 'Add to Collection');
            addBtn.setAttribute('aria-label', isInCollection ? 'Already Added' : 'Add to Collection');
            if (isInCollection) addBtn.disabled = true;
            addBtn.innerHTML = addIconSvg;
            (function (itemTitle, itemImgUrl, itemPageUrl, itemPageId, itemInCollection) {
                addBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (itemInCollection) return;
                    if (typeof addToCollection === 'function') addToCollection(itemTitle, itemImgUrl, itemPageUrl || undefined, itemPageId);
                });
            })(title, imgUrl, pageUrl, pageId, isInCollection);
            var msgBtn = document.createElement('button');
            msgBtn.type = 'button';
            msgBtn.className = 'poster-carousel-wheel-action';
            msgBtn.setAttribute('data-tooltip', 'Add to Conversation');
            msgBtn.setAttribute('title', 'Add to Conversation');
            msgBtn.setAttribute('aria-label', 'Add to Conversation');
            msgBtn.innerHTML = messageIconSvg;
            (function (itemTitle, itemYear, itemPageUrl, itemPageId, itemImgUrl) {
                msgBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (typeof addSubConversationFromPoster === 'function') {
                        addSubConversationFromPoster({
                            title: itemTitle,
                            year: itemYear,
                            pageUrl: itemPageUrl || undefined,
                            pageId: itemPageId || undefined,
                            imageUrl: itemImgUrl || undefined
                        });
                    }
                });
            })(title, typeof it.year === 'number' ? it.year : undefined, pageUrl, pageId, imgUrl);
            overlay.appendChild(addBtn);
            overlay.appendChild(msgBtn);
            posterWrap.appendChild(overlay);
            el.appendChild(posterWrap);
            var lbl = document.createElement('span');
            lbl.className = 'poster-carousel-wheel-item-label';
            lbl.textContent = labelText;
            el.appendChild(lbl);

            el.addEventListener('click', function (e) {
                var i = parseInt(el.getAttribute('data-index'), 10);
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

        var leftBtn = document.createElement('button');
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

        var rightBtn = document.createElement('button');
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

    /* Scene item: imageUrl, caption?, sourceUrl? */
    function createSceneCard(item) {
        var imageUrl = (item.imageUrl && String(item.imageUrl).trim()) || '';
        if (!imageUrl) return null;
        var caption = (item.caption && String(item.caption).trim()) || '';
        var sourceUrl = (item.sourceUrl && String(item.sourceUrl).trim()) || '';
        var wrap = document.createElement('div');
        wrap.className = 'media-strip-card attachment-scene-card';
        var inner = document.createElement('div');
        inner.className = 'media-strip-card-poster';
        var img = document.createElement('img');
        img.src = imageUrl;
        img.alt = caption || 'Scene';
        img.loading = 'lazy';
        inner.appendChild(img);
        wrap.appendChild(inner);
        if (caption) {
            var capEl = document.createElement('span');
            capEl.className = 'media-strip-card-label attachment-scene-caption';
            capEl.textContent = caption;
            wrap.appendChild(capEl);
        }
        if (sourceUrl) {
            var link = document.createElement('a');
            link.href = sourceUrl;
            link.target = '_blank';
            link.rel = 'noopener';
            link.className = 'media-strip-card';
            link.appendChild(wrap.cloneNode(true));
            return link;
        }
        return wrap;
    }

    /* Render attachments.sections (primary_movie, movie_list, did_you_mean, scenes). Backward compat: fallback to media_strip/media_candidates. */
    function createAttachmentsFromSections(sections) {
        if (!sections || sections.length === 0) return null;
        var wrap = document.createElement('div');
        wrap.className = 'attachments';
        sections.forEach(function (section) {
            var type = (section.type && String(section.type).trim()) || 'movie_list';
            var title = (section.title && String(section.title).trim()) || 'Movies';
            var items = Array.isArray(section.items) ? section.items : [];
            if (items.length === 0) return;

            var sectionEl = document.createElement('div');
            sectionEl.className = 'attachments-section attachments-section-' + type.replace(/_/g, '-');
            sectionEl.setAttribute('data-section-type', type);
            var heading = document.createElement('div');
            heading.className = 'attachments-section-title';
            heading.textContent = title;
            sectionEl.appendChild(heading);

            if (type === 'primary_movie') {
                var carouselItems = items.map(function (it) {
                    return {
                        title: (it.title != null && String(it.title).trim()) || '',
                        year: typeof it.year === 'number' ? it.year : undefined,
                        imageUrl: (it.imageUrl && String(it.imageUrl).trim()) || '',
                        sourceUrl: (it.sourceUrl && String(it.sourceUrl).trim()) || '',
                        tmdbId: it.tmdbId || it.tmdb_id || undefined,
                        mediaType: it.mediaType || it.media_type || undefined,
                        pageId: it.pageId || it.page_id || undefined
                    };
                }).filter(function (it) { return it.title; });
                if (carouselItems.length > 0) {
                    var carousel = PosterCarouselWheel(carouselItems, 0, function () {}, { visibleWindow: 2 });
                    sectionEl.appendChild(carousel);
                }
            } else if (type === 'did_you_mean' || type === 'movie_list') {
                var layout = document.createElement('div');
                layout.className = 'media-strip-layout';
                items.forEach(function (it) {
                    var heroShape = attachmentItemToHeroShape(it);
                    if (heroShape) {
                        var card = createHeroCard(heroShape, { link: !!heroShape.page_url });
                        if (card) layout.appendChild(card);
                    }
                });
                sectionEl.appendChild(layout);
            } else if (type === 'scenes') {
                var layout = document.createElement('div');
                layout.className = 'media-strip-layout';
                items.forEach(function (it) {
                    var card = createSceneCard(it);
                    if (card) layout.appendChild(card);
                });
                sectionEl.appendChild(layout);
            } else {
                var carouselItemsOther = items.map(function (it) {
                    var heroShape = attachmentItemToHeroShape(it);
                    if (!heroShape) return null;
                    return {
                        title: heroShape.movie_title || '',
                        year: heroShape.year,
                        imageUrl: heroShape.primary_image_url || '',
                        sourceUrl: heroShape.page_url || ''
                    };
                }).filter(function (it) { return it && it.title; });
                if (carouselItemsOther.length > 0) {
                    var carouselOther = PosterCarouselWheel(carouselItemsOther, 0, function () {}, { visibleWindow: 2 });
                    sectionEl.appendChild(carouselOther);
                }
            }
            wrap.appendChild(sectionEl);
        });
        if (wrap.children.length === 0) return null;
        return wrap;
    }

    /* Unified movie strip: hero + candidates in one horizontal row, all hero-sized. (Legacy when attachments not present.) */
    function createUnifiedMovieStrip(norm) {
        var hasStrip = norm.media_strip && norm.media_strip.movie_title;
        var candidates = Array.isArray(norm.media_candidates) ? norm.media_candidates : [];
        var hasCandidates = candidates.length > 0;
        if (!hasStrip && !hasCandidates) return null;

        var wrap = document.createElement('div');
        wrap.className = 'media-strip';
        var layout = document.createElement('div');
        layout.className = 'media-strip-layout';

        if (hasStrip) {
            var heroCard = createHeroCard(norm.media_strip, { link: !!norm.media_strip.page_url });
            if (heroCard) layout.appendChild(heroCard);
        }
        candidates.forEach(function (c) {
            var card = createHeroCard(c, { link: true });
            if (card) layout.appendChild(card);
        });

        wrap.appendChild(layout);
        return wrap;
    }

    /**
     * Renders the active thread's messages and attachments. Used by both main conversation
     * and SubConversationView: thread is determined by getActiveThread() (main or sub).
     * Same message component, attachment sections (primary_movie, movie_list, did_you_mean,
     * scenes), Add to Collection / Already Added use isPosterInActiveCollection and
     * addToCollection (getActiveConversation() for scope); behavior is identical on both screens.
     */
    function renderMessages() {
        if (!messageList) return;
        messageList.innerHTML = '';
        var thread = getActiveThread();
        var messages = thread.messages || [];
        chatColumn.classList.toggle('empty', messages.length === 0);
        messages.forEach(function (msg, i) {
            try {
                var wrap = document.createElement('div');
                wrap.className = 'message ' + msg.role;
                wrap.setAttribute('data-msg-index', i);
                var avatar = document.createElement('div');
                avatar.className = 'message-avatar';
                avatar.textContent = msg.role === 'user' ? 'U' : 'C';
                var content = document.createElement('div');
                content.className = 'message-content';
                var bubble = document.createElement('div');
                bubble.className = 'message-bubble';

                var displayContent = msg.content != null ? String(msg.content) : '';
                var movieStrip = null;
                if (msg.role === 'assistant') {
                    var norm = normalizeMeta(msg.meta);
                    if (norm) {
                        displayContent = norm.content;
                        try {
                            movieStrip = (norm.attachments && norm.attachments.sections && norm.attachments.sections.length)
                                ? createAttachmentsFromSections(norm.attachments.sections)
                                : createUnifiedMovieStrip(norm);
                        } catch (_) { /* ignore */ }
                        if (norm.media_strip || (norm.media_candidates && norm.media_candidates.length)) {
                            captureAssetsForProjectScope(getActiveConversation() && getActiveConversation().id, i, norm);
                        }
                    }
                }
                if (movieStrip) bubble.appendChild(movieStrip);
                bubble.appendChild(document.createTextNode(displayContent));

                content.appendChild(bubble);
                if (msg.role === 'assistant' && msg.meta && (msg.meta.actualAgentMode || msg.meta.agent_mode)) {
                    var modeBadgeWrap = document.createElement('div');
                    modeBadgeWrap.className = 'message-mode-badge-wrap';
                    var modeLabel = msg.meta.modeFallback ? 'Playground (fallback)' : (msg.meta.actualAgentMode || msg.meta.agent_mode) === 'REAL_AGENT' ? 'Real Agent' : 'Playground';
                    var badge = document.createElement('span');
                    badge.className = 'message-mode-badge';
                    badge.textContent = modeLabel;
                    var titleParts = [];
                    if (msg.meta.toolsUsed && msg.meta.toolsUsed.length) titleParts.push('Tools: ' + msg.meta.toolsUsed.join(', '));
                    if (msg.meta.modeOverrideReason) titleParts.push(msg.meta.modeOverrideReason);
                    if (titleParts.length) badge.setAttribute('title', titleParts.join('\n'));
                    modeBadgeWrap.appendChild(badge);
                    content.appendChild(modeBadgeWrap);
                }
                if (msg.meta && msg.role === 'assistant') {
                    var metaRow = document.createElement('div');
                    metaRow.className = 'message-meta';
                    var toggle = document.createElement('button');
                    toggle.type = 'button';
                    toggle.className = 'metadata-toggle-btn';
                    toggle.textContent = 'Raw response';
                    var metaBlock = document.createElement('pre');
                    metaBlock.className = 'message-metadata hidden';
                    metaBlock.textContent = typeof msg.meta === 'string' ? msg.meta : JSON.stringify(msg.meta, null, 2);
                    toggle.addEventListener('click', function () { metaBlock.classList.toggle('hidden'); });
                    metaRow.appendChild(toggle);
                    content.appendChild(metaRow);
                    content.appendChild(metaBlock);
                }
                wrap.appendChild(avatar);
                wrap.appendChild(content);
                messageList.appendChild(wrap);
            } catch (err) {
                var fallback = document.createElement('div');
                fallback.className = 'message ' + msg.role;
                fallback.setAttribute('data-msg-index', i);
                fallback.innerHTML = '<div class="message-avatar">' + (msg.role === 'user' ? 'U' : 'C') + '</div><div class="message-content"><div class="message-bubble">' + escapeHtml(msg.content != null ? String(msg.content) : 'Something went wrong.') + '</div></div>';
                messageList.appendChild(fallback);
            }
        });
        if (chatColumn) {
            if (restoreScrollTop != null) {
                chatColumn.scrollTop = restoreScrollTop;
                restoreScrollTop = null;
            } else {
                var scrollToBottom = function () {
                    chatColumn.scrollTo({ top: chatColumn.scrollHeight, behavior: 'smooth' });
                };
                scrollToBottom();
                requestAnimationFrame(scrollToBottom);
            }
        }
    }

    var SEND_TIMEOUT_MS = 90000;

    async function sendMessage() {
        var text = composerInput.value.trim();
        if (!text || isSending) return;
        var conv = getActiveConversation();
        if (!conv) return;
        isSending = true;
        sendBtn.disabled = true;
        composerInput.value = '';
        composerInput.style.height = 'auto';

        function resetSendState() {
            isSending = false;
            if (sendBtn) sendBtn.disabled = false;
            if (composerInput) composerInput.focus();
        }
        try {
            appendMessage('user', text);
            showRetrieving();
            var controller = new AbortController();
            var timeoutId = setTimeout(function () { controller.abort(); }, SEND_TIMEOUT_MS);
            var response;
            try {
                response = await fetch(API_BASE + '/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_query: text,
                        requestedAgentMode: useRealAgent ? 'REAL_AGENT' : 'PLAYGROUND'  // session-level; same for all conversations
                    }),
                    signal: controller.signal
                });
            } finally {
                clearTimeout(timeoutId);
            }
            if (!response.ok) {
                var errMsg = 'HTTP ' + response.status;
                try {
                    var errBody = await response.json();
                    if (errBody && errBody.detail) {
                        if (typeof errBody.detail === 'string') errMsg = errBody.detail;
                        else if (errBody.detail.error) errMsg = errBody.detail.error;
                    }
                } catch (_) { /* ignore */ }
                throw new Error(errMsg);
            }
            var result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error('Invalid response from server');
            }
            var responseText = (result && (result.response || result.answer)) ? String(result.response || result.answer) : 'No response.';
            hideRetrieving();
            appendMessage('assistant', responseText, result);
            if (modeBadge && result && result.agent_mode) {
                if (result.modeFallback) {
                    modeBadge.textContent = 'Mode: Playground (fallback)';
                    modeBadge.setAttribute('title', result.fallback_reason || 'Real agent failed; switched to Playground.');
                    if (result.fallback_reason) showFallbackToast(result.fallback_reason);
                } else if (result.modeOverrideReason) {
                    modeBadge.textContent = 'Mode: Playground';
                    modeBadge.setAttribute('title', result.modeOverrideReason);
                    showFallbackToast(result.modeOverrideReason);
                } else {
                    modeBadge.textContent = result.agent_mode === 'REAL_AGENT' ? 'Mode: Real Agent' : 'Mode: Playground';
                    modeBadge.removeAttribute('title');
                }
            }
            updateHeaderRealAgentIndicator();
        } catch (err) {
            hideRetrieving();
            var active = getActiveConversation();
            if (active) {
                var msg = err.name === 'AbortError' ? 'Request timed out. Please try again.' : ('Error: ' + (err.message || String(err)));
                appendMessage('assistant', msg, null);
            }
        } finally {
            try {
                resetSendState();
            } catch (_) { /* ensure we never throw from finally */ }
        }
    }

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (composerInput) {
        composerInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        composerInput.addEventListener('input', function () {
            var el = composerInput;
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 200) + 'px';
        });
    }

    if (composerInput) composerInput.focus();

    function showRealAgentConfirmModal() {
        var modal = document.getElementById('realAgentConfirmModal');
        if (!modal) return;
        modal.classList.remove('hidden');
        modal.querySelector('.real-agent-modal-cancel').focus();
    }
    function hideRealAgentConfirmModal() {
        var modal = document.getElementById('realAgentConfirmModal');
        if (modal) modal.classList.add('hidden');
    }
    function updateHeaderRealAgentIndicator() {
        if (modeBadge) {
            modeBadge.classList.toggle('real-agent-active', useRealAgent);
        }
    }

    if (useRealAgentToggle) {
        useRealAgentToggle.checked = useRealAgent;
        useRealAgentToggle.addEventListener('change', function () {
            if (useRealAgentToggle.checked && !realAgentConfirmedThisSession) {
                useRealAgentToggle.checked = false;
                showRealAgentConfirmModal();
                return;
            }
            useRealAgent = useRealAgentToggle.checked;
            try { sessionStorage.setItem('cinemind_useRealAgent', useRealAgent ? '1' : '0'); } catch (e) { /* ignore */ }
            updateHeaderRealAgentIndicator();
        });
    }

    (function setupRealAgentConfirmModal() {
        var modal = document.getElementById('realAgentConfirmModal');
        var cancelBtn = document.getElementById('realAgentConfirmCancel');
        var continueBtn = document.getElementById('realAgentConfirmContinue');
        var backdrop = modal && modal.querySelector('.real-agent-modal-backdrop');
        if (!modal || !cancelBtn || !continueBtn) return;
        function onConfirm() {
            realAgentConfirmedThisSession = true;
            useRealAgent = true;
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
        modal.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') onCancel();
            if (e.key === 'Enter' && e.target === continueBtn) onConfirm();
        });
    })();

    /**
     * Migrate flat sub-conversations (parentId + movieAnchor) into nested subConversations[].
     * Ensures state is consistent and restores activeThread (main + sub) after tab switch.
     */
    function migrateConversationsToNested() {
        var i, j, conv, parent, sub;
        for (i = 0; i < conversations.length; i++) {
            conv = conversations[i];
            if (!conv.subConversations) conv.subConversations = [];
        }
        var flatSubs = [];
        for (i = 0; i < conversations.length; i++) {
            conv = conversations[i];
            if (conv.parentId && conv.movieAnchor) flatSubs.push(conv);
        }
        if (flatSubs.length === 0) return;
        for (j = 0; j < flatSubs.length; j++) {
            sub = flatSubs[j];
            parent = null;
            for (i = 0; i < conversations.length; i++) {
                if (conversations[i].id === sub.parentId) { parent = conversations[i]; break; }
            }
            if (!parent) continue;
            if (!parent.subConversations) parent.subConversations = [];
            parent.subConversations.push({
                id: sub.id,
                title: sub.title || 'Re: ' + (sub.movieAnchor && sub.movieAnchor.title),
                contextMovie: sub.movieAnchor || {},
                messages: Array.isArray(sub.messages) ? sub.messages : []
            });
        }
        conversations = conversations.filter(function (c) { return !c.parentId; });
        if (activeConversationId) {
            for (j = 0; j < flatSubs.length; j++) {
                if (flatSubs[j].id === activeConversationId) {
                    activeSubConversationId = activeConversationId;
                    activeConversationId = flatSubs[j].parentId;
                    break;
                }
            }
        }
    }

    migrateConversationsToNested();
    loadProjects();
    updateHeaderRealAgentIndicator();
    if (conversations.length === 0) addConversation();
    else {
        updateConversationList();
        updateHeaderForView();
        updateRightPanelScope();
    }
})();
