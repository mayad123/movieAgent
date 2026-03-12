/** @module layout — Sidebar, header, right panel, conversation list, and toast notifications. */

import {
    sidebar, sidebarToggle, rightPanel, rightPanelToggle,
    conversationList, conversationTitle, headerMainView, headerSubView,
    headerBreadcrumb, subConversationMovieBadge, mainEl,
    chatColumn, composerInput, retrievingRow, newChatBtn,
    useRealAgentToggle, modeBadge, app,
    headerBackBtn, headerSubRenameBtn, headerSubCloseBtn
} from './dom.js';

import {
    appState, getActiveConversation, getActiveThread, nextId, API_BASE
} from './state.js';

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
    if (subId != null && subId !== '') {
        appState.activeSubConversationId = subId;
        appState.conversationView = 'sub';
        appState.lastViewByConversationId[mainId] = { view: 'sub', subId };
    } else {
        appState.activeSubConversationId = null;
        appState.conversationView = 'main';
    }
    appState.restoreScrollTop = (appState.conversationView === 'main')
        ? (appState.mainScrollTopByConversationId[mainId] != null ? appState.mainScrollTopByConversationId[mainId] : null)
        : null;
    updateConversationList();
    if (_renderMessages) _renderMessages();
    if (_renderCollectionPanel) _renderCollectionPanel();
    updateHeaderForView();
    updateRightPanelScope();
}

export function addSubConversationFromPoster(movie) {
    const main = getActiveConversation();
    if (!main || !movie || !String(movie.title || '').trim()) return;
    const title = String(movie.title).trim();
    const subTitle = 'Re: ' + title + (movie.year != null ? ' (' + movie.year + ')' : '');
    const contextMovie = {
        title,
        year: movie.year,
        pageUrl: (movie.pageUrl && String(movie.pageUrl).trim()) || undefined,
        pageId: (movie.pageId && String(movie.pageId).trim()) || undefined,
        imageUrl: (movie.imageUrl && String(movie.imageUrl).trim()) || undefined
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
    appState.conversationView = 'sub';
    appState.lastViewByConversationId[main.id] = { view: 'sub', subId: sub.id };
    updateConversationList();
    if (_renderMessages) _renderMessages();
    if (_renderCollectionPanel) _renderCollectionPanel();
    updateHeaderForView();
    updateRightPanelScope();
    if (composerInput) composerInput.focus();
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
        if (subConversationMovieBadge) {
            subConversationMovieBadge.classList.add('hidden');
            subConversationMovieBadge.setAttribute('aria-hidden', 'true');
        }
    }
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
    let url = API_BASE + '/api/projects/' + encodeURIComponent(projectId);
    url += (url.indexOf('?') !== -1 ? '&' : '?') + '_=' + Date.now();
    fetch(url)
        .then(res => {
            if (!res.ok) throw new Error('Project not found');
            return res.json();
        })
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
            fetch(API_BASE + '/api/projects/' + encodeURIComponent(projectId) + '/assets/' + i, { method: 'DELETE' })
                .then(res => {
                    if (!res.ok) return Promise.reject(new Error('Failed to remove'));
                    return res.json();
                })
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
    fetch(API_BASE + '/api/projects')
        .then(res => res.ok ? res.json() : Promise.reject(new Error('Failed to load projects')))
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
    if (retrievingRow) retrievingRow.classList.remove('hidden');
    if (chatColumn) chatColumn.scrollTo({ top: chatColumn.scrollHeight, behavior: 'smooth' });
}

export function hideRetrieving() {
    if (retrievingRow) retrievingRow.classList.add('hidden');
}

/* ── Navigation helpers ── */

export function startNewChat() {
    addConversation();
}

export function navigateBackToParentConversation() {
    const main = getActiveConversation();
    if (!main || appState.conversationView !== 'sub') return;
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
    if (headerBackBtn) headerBackBtn.addEventListener('click', navigateBackToParentConversation);
    if (headerSubRenameBtn) headerSubRenameBtn.addEventListener('click', renameSubConversation);
    if (headerSubCloseBtn) headerSubCloseBtn.addEventListener('click', closeSubConversation);

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
