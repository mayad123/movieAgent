/** @module messages — Message rendering, appending, and sending. */

import { chatColumn, messageList, composerInput, sendBtn, modeBadge } from './dom.js';
import { appState, getActiveConversation, getActiveThread } from './state.js';
import { normalizeMeta, escapeHtml } from './normalize.js';
import { sendQuery } from './api.js';

/* ── Callback registry (breaks circular deps with layout/poster modules) ── */

let _showRetrieving = null;
let _hideRetrieving = null;
let _captureAssetsForProjectScope = null;
let _createHeroCard = null;
let _createCandidateCard = null;
let _createAttachmentsFromSections = null;
let _createUnifiedMovieStrip = null;
let _updateConversationList = null;
let _updateHeaderForView = null;
let _updateHeaderRealAgentIndicator = null;
let _showFallbackToast = null;

export function setMessageCallbacks({
    showRetrieving, hideRetrieving,
    captureAssetsForProjectScope,
    createHeroCard, createCandidateCard,
    createAttachmentsFromSections, createUnifiedMovieStrip,
    updateConversationList, updateHeaderForView,
    updateHeaderRealAgentIndicator, showFallbackToast
}) {
    _showRetrieving = showRetrieving;
    _hideRetrieving = hideRetrieving;
    _captureAssetsForProjectScope = captureAssetsForProjectScope;
    _createHeroCard = createHeroCard;
    _createCandidateCard = createCandidateCard;
    _createAttachmentsFromSections = createAttachmentsFromSections;
    _createUnifiedMovieStrip = createUnifiedMovieStrip;
    _updateConversationList = updateConversationList;
    _updateHeaderForView = updateHeaderForView;
    _updateHeaderRealAgentIndicator = updateHeaderRealAgentIndicator;
    _showFallbackToast = showFallbackToast;
}

/* ── appendMessage ── */

export function appendMessage(role, content, meta) {
    const thread = getActiveThread();
    if (!thread.messages) return;
    thread.messages.push({ role, content, meta: meta || null });
    if (thread.messages.length === 1 && role === 'user') {
        const title = content.length > 40 ? content.slice(0, 40) + '\u2026' : content;
        if (thread.sub) thread.sub.title = title;
        else if (thread.main) thread.main.title = title;
        if (_updateHeaderForView) _updateHeaderForView();
        if (_updateConversationList) _updateConversationList();
    }
    renderMessages();
}

/* ── renderMessages ── */

export function renderMessages() {
    if (!messageList) return;
    messageList.innerHTML = '';
    const thread = getActiveThread();
    const messages = thread.messages || [];
    chatColumn.classList.toggle('empty', messages.length === 0);
    messages.forEach(function (msg, i) {
        try {
            const wrap = document.createElement('div');
            wrap.className = 'message ' + msg.role;
            wrap.setAttribute('data-msg-index', i);
            const avatar = document.createElement('div');
            avatar.className = 'message-avatar';
            avatar.textContent = msg.role === 'user' ? 'U' : 'C';
            const content = document.createElement('div');
            content.className = 'message-content';
            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';

            let displayContent = msg.content != null ? String(msg.content) : '';
            let movieStrip = null;
            if (msg.role === 'assistant') {
                const norm = normalizeMeta(msg.meta);
                if (norm) {
                    displayContent = norm.content;
                    try {
                        movieStrip = (norm.attachments && norm.attachments.sections && norm.attachments.sections.length)
                            ? (_createAttachmentsFromSections && _createAttachmentsFromSections(norm.attachments.sections))
                            : (_createUnifiedMovieStrip && _createUnifiedMovieStrip(norm));
                    } catch (_) { /* ignore */ }
                    if (norm.media_strip || (norm.media_candidates && norm.media_candidates.length)) {
                        if (_captureAssetsForProjectScope) {
                            _captureAssetsForProjectScope(getActiveConversation() && getActiveConversation().id, i, norm);
                        }
                    }
                }
            }
            if (movieStrip) {
                content.appendChild(movieStrip);
            }
            bubble.appendChild(document.createTextNode(displayContent));

            content.appendChild(bubble);
            if (msg.role === 'assistant' && msg.meta && (msg.meta.actualAgentMode || msg.meta.agent_mode)) {
                const modeBadgeWrap = document.createElement('div');
                modeBadgeWrap.className = 'message-mode-badge-wrap';
                const modeLabel = msg.meta.modeFallback
                    ? 'Playground (fallback)'
                    : (msg.meta.actualAgentMode || msg.meta.agent_mode) === 'REAL_AGENT' ? 'Real Agent' : 'Playground';
                const badge = document.createElement('span');
                badge.className = 'message-mode-badge';
                badge.textContent = modeLabel;
                const titleParts = [];
                if (msg.meta.toolsUsed && msg.meta.toolsUsed.length) titleParts.push('Tools: ' + msg.meta.toolsUsed.join(', '));
                if (msg.meta.modeOverrideReason) titleParts.push(msg.meta.modeOverrideReason);
                if (titleParts.length) badge.setAttribute('title', titleParts.join('\n'));
                modeBadgeWrap.appendChild(badge);
                content.appendChild(modeBadgeWrap);
            }
            if (msg.meta && msg.role === 'assistant') {
                const metaRow = document.createElement('div');
                metaRow.className = 'message-meta';
                const toggle = document.createElement('button');
                toggle.type = 'button';
                toggle.className = 'metadata-toggle-btn';
                toggle.textContent = 'Raw response';
                const metaBlock = document.createElement('pre');
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
            const fallback = document.createElement('div');
            fallback.className = 'message ' + msg.role;
            fallback.setAttribute('data-msg-index', i);
            fallback.innerHTML = '<div class="message-avatar">' + (msg.role === 'user' ? 'U' : 'C') + '</div>'
                + '<div class="message-content"><div class="message-bubble">'
                + escapeHtml(msg.content != null ? String(msg.content) : 'Something went wrong.')
                + '</div></div>';
            messageList.appendChild(fallback);
        }
    });
    if (chatColumn) {
        if (appState.restoreScrollTop != null) {
            chatColumn.scrollTop = appState.restoreScrollTop;
            appState.restoreScrollTop = null;
        } else {
            const scrollToBottom = function () {
                chatColumn.scrollTo({ top: chatColumn.scrollHeight, behavior: 'smooth' });
            };
            scrollToBottom();
            requestAnimationFrame(scrollToBottom);
        }
    }
}

/* ── sendMessage ── */

export async function sendMessage() {
    const text = composerInput.value.trim();
    if (!text || appState.isSending) return;
    const conv = getActiveConversation();
    if (!conv) return;
    appState.isSending = true;
    sendBtn.disabled = true;
    composerInput.value = '';
    composerInput.style.height = 'auto';

    function resetSendState() {
        appState.isSending = false;
        if (sendBtn) sendBtn.disabled = false;
        if (composerInput) composerInput.focus();
    }
    try {
        appendMessage('user', text);
        if (_showRetrieving) _showRetrieving();
        const result = await sendQuery(text, appState.useRealAgent);
        const responseText = (result && (result.response || result.answer))
            ? String(result.response || result.answer)
            : 'No response.';
        if (_hideRetrieving) _hideRetrieving();
        appendMessage('assistant', responseText, result);
        if (modeBadge && result && result.agent_mode) {
            if (result.modeFallback) {
                modeBadge.textContent = 'Mode: Playground (fallback)';
                modeBadge.setAttribute('title', result.fallback_reason || 'Real agent failed; switched to Playground.');
                if (result.fallback_reason && _showFallbackToast) _showFallbackToast(result.fallback_reason);
            } else if (result.modeOverrideReason) {
                modeBadge.textContent = 'Mode: Playground';
                modeBadge.setAttribute('title', result.modeOverrideReason);
                if (_showFallbackToast) _showFallbackToast(result.modeOverrideReason);
            } else {
                modeBadge.textContent = result.agent_mode === 'REAL_AGENT' ? 'Mode: Real Agent' : 'Mode: Playground';
                modeBadge.removeAttribute('title');
            }
        }
        if (_updateHeaderRealAgentIndicator) _updateHeaderRealAgentIndicator();
    } catch (err) {
        if (_hideRetrieving) _hideRetrieving();
        const active = getActiveConversation();
        if (active) {
            const msg = err.name === 'AbortError'
                ? 'Request timed out. Please try again.'
                : ('Error: ' + (err.message || String(err)));
            appendMessage('assistant', msg, null);
        }
    } finally {
        try {
            resetSendState();
        } catch (_) { /* ensure we never throw from finally */ }
    }
}
