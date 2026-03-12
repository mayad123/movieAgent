/** @module state — Mutable application state, constants, and pure state helpers. */

export const API_BASE = window.CINEMIND_CONFIG && window.CINEMIND_CONFIG.apiBase
    ? window.CINEMIND_CONFIG.apiBase
    : 'http://localhost:8000';

export const SEND_TIMEOUT_MS = 90000;

export const appState = {
    conversations: [],
    activeConversationId: null,
    activeSubConversationId: null,
    conversationView: 'main',
    lastViewByConversationId: {},
    mainScrollTopByConversationId: {},
    restoreScrollTop: null,
    isSending: false,
    useRealAgent: (function () {
        try {
            return sessionStorage.getItem('cinemind_useRealAgent') === '1';
        } catch (e) { return false; }
    })(),
    realAgentConfirmedThisSession: false,
    projects: [],
    savedAssetKeys: new Set(),
    currentProjectId: null,
    currentProjectAssets: [],
};
appState.realAgentConfirmedThisSession = appState.useRealAgent;

/* ── Pure helpers (no DOM dependencies) ── */

let _idCounter = 0;
export function nextId() {
    return 'conv_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
}

export function normalizeTitle(s) {
    return String(s || '').trim().toLowerCase().replace(/\s+/g, ' ');
}

export function pageIdFromUrl(url) {
    if (!url || typeof url !== 'string') return '';
    const m = /\/wiki\/([^/?#]+)/.exec(url);
    return m ? decodeURIComponent(m[1]) : '';
}

export function getAssetKey(title, imageUrl, pageUrl, pageId) {
    const pid = (pageId && String(pageId).trim()) || '';
    const url = (pageUrl && String(pageUrl).trim()) || '';
    if (pid) return 'id:' + pid;
    if (url) return 'url:' + url;
    const t = normalizeTitle(title);
    const img = (imageUrl && String(imageUrl).trim()) || '';
    return 'title:' + t + '|' + img;
}

export function collectionHasKey(collection, key) {
    if (!Array.isArray(collection) || !key) return false;
    for (let i = 0; i < collection.length; i++) {
        const item = collection[i];
        const itemKey = (item && item.assetKey) || getAssetKey(item.title, item.imageUrl, item.pageUrl, item.pageId);
        if (itemKey === key) return true;
    }
    return false;
}

export function getActiveConversation() {
    if (!appState.activeConversationId) return null;
    for (let i = 0; i < appState.conversations.length; i++) {
        if (appState.conversations[i].id === appState.activeConversationId) return appState.conversations[i];
    }
    return null;
}

export function getActiveThread() {
    const main = getActiveConversation();
    if (!main) return { main: null, sub: null, messages: [], title: 'New conversation' };
    if (!appState.activeSubConversationId) {
        return { main: main, sub: null, messages: main.messages, title: main.title || 'New conversation' };
    }
    const subs = main.subConversations && Array.isArray(main.subConversations) ? main.subConversations : [];
    for (let j = 0; j < subs.length; j++) {
        if (subs[j].id === appState.activeSubConversationId) {
            return {
                main: main,
                sub: subs[j],
                messages: subs[j].messages,
                title: subs[j].title || 'Re: ' + (subs[j].contextMovie && subs[j].contextMovie.title) || 'Sub'
            };
        }
    }
    appState.activeSubConversationId = null;
    return { main: main, sub: null, messages: main.messages, title: main.title || 'New conversation' };
}

/**
 * Whether the given poster is already in the active collection (same de-dupe key).
 * poster: { title, imageUrl, pageUrl?, pageId? }
 */
export function isPosterInActiveCollection(poster) {
    const conv = getActiveConversation();
    if (!conv) return false;
    const scope = (conv.activeScope != null && conv.activeScope !== '') ? conv.activeScope : 'This Conversation';
    const key = getAssetKey(poster.title, poster.imageUrl, poster.pageUrl, poster.pageId);
    if (!key) return false;
    if (scope === 'This Conversation') {
        const collection = (conv.collection) ? conv.collection : [];
        return collectionHasKey(collection, key);
    }
    if (String(scope).indexOf('project:') === 0) {
        const projectId = String(scope).slice(8);
        if (appState.currentProjectId !== projectId || !Array.isArray(appState.currentProjectAssets)) return false;
        for (let j = 0; j < appState.currentProjectAssets.length; j++) {
            const a = appState.currentProjectAssets[j];
            const assetKey = getAssetKey(a.title, (a.posterImageUrl || a.storedRef) || '', a.pageUrl, a.pageId);
            if (assetKey === key) return true;
        }
    }
    return false;
}

/**
 * Migrate flat sub-conversations (parentId + movieAnchor) into nested subConversations[].
 */
export function migrateConversationsToNested() {
    let i, j, conv, parent, sub;
    for (i = 0; i < appState.conversations.length; i++) {
        conv = appState.conversations[i];
        if (!conv.subConversations) conv.subConversations = [];
    }
    const flatSubs = [];
    for (i = 0; i < appState.conversations.length; i++) {
        conv = appState.conversations[i];
        if (conv.parentId && conv.movieAnchor) flatSubs.push(conv);
    }
    if (flatSubs.length === 0) return;
    for (j = 0; j < flatSubs.length; j++) {
        sub = flatSubs[j];
        parent = null;
        for (i = 0; i < appState.conversations.length; i++) {
            if (appState.conversations[i].id === sub.parentId) { parent = appState.conversations[i]; break; }
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
    appState.conversations = appState.conversations.filter(function (c) { return !c.parentId; });
    if (appState.activeConversationId) {
        for (j = 0; j < flatSubs.length; j++) {
            if (flatSubs[j].id === appState.activeConversationId) {
                appState.activeSubConversationId = appState.activeConversationId;
                appState.activeConversationId = flatSubs[j].parentId;
                break;
            }
        }
    }
}
