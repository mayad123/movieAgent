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
        return out;
    }

    var sidebar = document.getElementById('sidebar');
    var sidebarToggle = document.getElementById('sidebarToggle');
    var rightPanel = document.getElementById('rightPanel');
    var rightPanelToggle = document.getElementById('rightPanelToggle');
    var conversationList = document.getElementById('conversationList');
    var conversationTitle = document.getElementById('conversationTitle');
    var chatColumn = document.getElementById('chatColumn');
    var messageList = document.getElementById('messageList');
    var retrievingRow = document.getElementById('retrievingRow');
    var composerInput = document.getElementById('composerInput');
    var sendBtn = document.getElementById('sendBtn');
    var newChatBtn = document.getElementById('newChatBtn');

    /** Conversation state: list of { id, title, messages } and active id. */
    var conversations = [];
    var activeConversationId = null;
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

    function addToCollection(title, imageUrl, pageUrl, pageId) {
        var conv = getActiveConversation();
        if (!conv || !title) return;
        if (!conv.collection) conv.collection = [];
        var key = getAssetKey(title, imageUrl, pageUrl, pageId);
        if (collectionHasKey(conv.collection, key)) {
            showAlreadyAddedToast();
            return;
        }
        var item = {
            title: String(title).trim(),
            imageUrl: (imageUrl && String(imageUrl).trim()) || '',
            assetKey: key
        };
        if (pageUrl && String(pageUrl).trim()) item.pageUrl = String(pageUrl).trim();
        if (pageId && String(pageId).trim()) item.pageId = String(pageId).trim();
        conv.collection.push(item);
        renderCollectionPanel();
        renderMessages();
    }

    function renderCollectionPanel() {
        var container = document.getElementById('collectionList');
        if (!container) return;
        var conv = getActiveConversation();
        var items = (conv && conv.collection) ? conv.collection : [];
        container.innerHTML = '';
        items.forEach(function (item) {
            var wrap = document.createElement('div');
            wrap.className = 'right-panel-collection-item';
            if (item.imageUrl) {
                var img = document.createElement('img');
                img.src = item.imageUrl;
                img.alt = item.title;
                wrap.appendChild(img);
            } else {
                var ph = document.createElement('div');
                ph.className = 'right-panel-collection-placeholder';
                ph.textContent = '?';
                wrap.appendChild(ph);
            }
            var titleEl = document.createElement('span');
            titleEl.className = 'right-panel-collection-item-title';
            titleEl.textContent = item.title;
            wrap.appendChild(titleEl);
            container.appendChild(wrap);
        });
    }

    function nextId() {
        return 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
    }

    function getActiveConversation() {
        if (!activeConversationId) return null;
        for (var i = 0; i < conversations.length; i++) {
            if (conversations[i].id === activeConversationId) return conversations[i];
        }
        return null;
    }

    function addConversation() {
        var id = nextId();
        conversations.unshift({
            id: id,
            title: 'New conversation',
            messages: [],
            collection: [],
            activeScope: 'This Conversation'
        });
        activeConversationId = id;
        composerInput.value = '';
        updateConversationList();
        renderMessages();
        renderCollectionPanel();
        updateHeaderTitle();
        updateRightPanelScope();
        if (composerInput) composerInput.focus();
    }

    function switchConversation(id) {
        if (id === activeConversationId) return;
        activeConversationId = id;
        updateConversationList();
        renderMessages();
        renderCollectionPanel();
        updateHeaderTitle();
        updateRightPanelScope();
    }

    function updateHeaderTitle() {
        var conv = getActiveConversation();
        conversationTitle.textContent = conv ? conv.title : 'New conversation';
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

    /** Load one project by id and render its assets in the right-panel Project Assets strip. */
    function loadProjectAssets(projectId) {
        var strip = document.getElementById('rightPanelProjectAssetsList');
        if (!strip) return;
        strip.innerHTML = '';
        fetch(API_BASE + '/api/projects/' + encodeURIComponent(projectId))
            .then(function (res) {
                if (!res.ok) throw new Error('Project not found');
                return res.json();
            })
            .then(function (project) {
                var assets = (project && project.assets) ? project.assets : [];
                renderProjectAssetsStrip(strip, assets);
            })
            .catch(function () {
                strip.innerHTML = '';
            });
    }

    /** Fill the Project Assets strip with small thumbnails (storedRef or posterImageUrl). */
    function renderProjectAssetsStrip(container, assets) {
        if (!container || !Array.isArray(assets)) return;
        container.innerHTML = '';
        assets.forEach(function (a) {
            var wrap = document.createElement('div');
            wrap.className = 'right-panel-project-asset';
            var imgUrl = (a.storedRef && String(a.storedRef).trim()) || (a.posterImageUrl && String(a.posterImageUrl).trim()) || '';
            if (imgUrl) {
                var img = document.createElement('img');
                img.src = imgUrl;
                img.alt = a.title || '';
                wrap.appendChild(img);
            } else {
                var ph = document.createElement('div');
                ph.className = 'right-panel-project-asset-placeholder';
                ph.textContent = '?';
                wrap.appendChild(ph);
            }
            var titleEl = document.createElement('span');
            titleEl.className = 'right-panel-project-asset-title';
            titleEl.textContent = a.title || 'Unnamed';
            wrap.appendChild(titleEl);
            container.appendChild(wrap);
        });
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

    function updateConversationList() {
        if (!conversationList) return;
        conversationList.innerHTML = '';
        conversations.forEach(function (conv) {
            var el = document.createElement('div');
            el.className = 'conversation-item' + (conv.id === activeConversationId ? ' active' : '');
            var label = conv.title || 'New conversation';
            el.textContent = label.length > 36 ? label.slice(0, 36) + '\u2026' : label;
            el.addEventListener('click', function () { switchConversation(conv.id); });
            conversationList.appendChild(el);
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
        var conv = getActiveConversation();
        if (!conv) return;
        conv.messages.push({ role: role, content: content, meta: meta || null });
        if (conv.messages.length === 1 && role === 'user') {
            conv.title = content.length > 40 ? content.slice(0, 40) + '\u2026' : content;
            updateHeaderTitle();
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

        var overlay = document.createElement('div');
        overlay.className = 'media-strip-card-overlay';
        var pageUrl = href || '';
        var pageId = pageIdFromUrl(pageUrl);
        var conv = getActiveConversation();
        var collection = (conv && conv.collection) ? conv.collection : [];
        var assetKey = getAssetKey(title, imgUrl, pageUrl, pageId);
        var isInCollection = collectionHasKey(collection, assetKey);
        var addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'media-strip-card-action' + (isInCollection ? ' is-added' : '');
        addBtn.setAttribute('data-tooltip', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.setAttribute('title', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.setAttribute('aria-label', isInCollection ? 'Already Added' : 'Add to Collection');
        addBtn.innerHTML = addIconSvg;
        addBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            addToCollection(title, imgUrl, pageUrl || undefined, pageId || undefined);
            return false;
        });
        var msgBtn = document.createElement('button');
        msgBtn.type = 'button';
        msgBtn.className = 'media-strip-card-action';
        msgBtn.setAttribute('data-tooltip', 'Add to conversation');
        msgBtn.setAttribute('title', 'Add to conversation');
        msgBtn.setAttribute('aria-label', 'Add to conversation');
        msgBtn.innerHTML = messageIconSvg;
        msgBtn.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); });
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

    /* Unified movie strip: hero + candidates in one horizontal row, all hero-sized. */
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

    function renderMessages() {
        if (!messageList) return;
        messageList.innerHTML = '';
        var messages = getActiveConversation() ? getActiveConversation().messages : [];
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
                        try { movieStrip = createUnifiedMovieStrip(norm); } catch (_) { /* ignore */ }
                        if (norm.media_strip || (norm.media_candidates && norm.media_candidates.length)) {
                            captureAssetsForProjectScope(getActiveConversation() && getActiveConversation().id, i, norm);
                        }
                    }
                }
                if (movieStrip) bubble.appendChild(movieStrip);
                bubble.appendChild(document.createTextNode(displayContent));

                content.appendChild(bubble);
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
            var scrollToBottom = function () {
                chatColumn.scrollTo({ top: chatColumn.scrollHeight, behavior: 'smooth' });
            };
            scrollToBottom();
            requestAnimationFrame(scrollToBottom);
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
                    body: JSON.stringify({ user_query: text }),
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

    loadProjects();
    if (conversations.length === 0) addConversation();
    else updateRightPanelScope();
})();
