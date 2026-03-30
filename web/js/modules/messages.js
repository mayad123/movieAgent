/** @module messages — Message rendering, appending, and sending. */

import {
    chatColumn, messageList, composerInput, sendBtn, modeBadge,
    movieHubFilterHistoryWrap, movieHubFilterHistory
} from './dom.js';
import { appState, getActiveConversation, getActiveThread, nextId } from './state.js';
import { normalizeMeta, escapeHtml } from './normalize.js';
import { sendQuery, prefixMovieHubContextQuery } from './api.js';
import { buildHubConversationHistory, cloneMovieHubClusters } from './hub-history.js';
import { applyMovieHubClusters, recomputeHubFromMessages } from './layout.js';

/* ── Callback registry (breaks circular deps with layout/poster modules) ── */

let _showRetrieving = null;
let _hideRetrieving = null;
let _createHeroCard = null;
let _createCandidateCard = null;
let _createAttachmentsFromSections = null;
let _createUnifiedMovieStrip = null;
let _updateConversationList = null;
let _updateHeaderForView = null;
let _updateHeaderRealAgentIndicator = null;
let _showFallbackToast = null;
let _applyMovieHubClusters = null;

export function setMessageCallbacks({
    showRetrieving, hideRetrieving,
    createHeroCard, createCandidateCard,
    createAttachmentsFromSections, createUnifiedMovieStrip,
    updateConversationList, updateHeaderForView,
    updateHeaderRealAgentIndicator, showFallbackToast,
    applyMovieHubClusters
}) {
    _showRetrieving = showRetrieving;
    _hideRetrieving = hideRetrieving;
    _createHeroCard = createHeroCard;
    _createCandidateCard = createCandidateCard;
    _createAttachmentsFromSections = createAttachmentsFromSections;
    _createUnifiedMovieStrip = createUnifiedMovieStrip;
    _updateConversationList = updateConversationList;
    _updateHeaderForView = updateHeaderForView;
    _updateHeaderRealAgentIndicator = updateHeaderRealAgentIndicator;
    _showFallbackToast = showFallbackToast;
    _applyMovieHubClusters = applyMovieHubClusters;
}

/* ── appendMessage ── */

/**
 * Strip markdown the assistant sometimes echoes (***, **, HR lines) so lists render as plain text.
 * Aligned with output_validator._normalize_markdown_artifacts and SYSTEM prompt plain-text rule.
 */
function stripMarkdownNoiseForDisplay(text) {
    let s = text != null ? String(text) : '';
    if (!s) return s;
    s = s.replace(/^\s*\*{3,}\s*$/gm, '');
    s = s.replace(/^\s*-{3,}\s*$/gm, '');
    s = s.replace(/\*\*\*([^*]+?)\*\*\*/g, '$1');
    s = s.replace(/\*\*([^*]+?)\*\*/g, '$1');
    s = s.replace(/^(\s*\d+\.\s*)\*{2,}\s*/gm, '$1');
    s = s.replace(/^(\s*-\s*)\*{2,}\s*/gm, '$1');
    s = s.replace(/\n{3,}/g, '\n\n');
    return s;
}

function renderAssistantContent(text, bubbleEl) {
    const value = stripMarkdownNoiseForDisplay(text != null ? String(text) : '');
    if (!value) {
        return;
    }
    const blocks = value.split(/\n{2,}/);
    const appendParagraph = (block) => {
        const trimmed = block.trim();
        if (!trimmed) return;
        const p = document.createElement('p');
        p.appendChild(document.createTextNode(trimmed));
        bubbleEl.appendChild(p);
    };
    const appendList = (lines, ordered) => {
        const listEl = document.createElement(ordered ? 'ol' : 'ul');
        lines.forEach((line) => {
            const raw = line.trim();
            if (!raw) return;
            const li = document.createElement('li');
            let textContent = raw;
            if (!ordered && raw.startsWith('- ')) {
                textContent = raw.slice(2);
            } else if (ordered) {
                const stripped = raw.replace(/^\d+\.\s+/, '');
                textContent = stripped || raw;
            }
            li.appendChild(document.createTextNode(textContent));
            listEl.appendChild(li);
        });
        bubbleEl.appendChild(listEl);
    };
    blocks.forEach((block) => {
        const lines = block.split('\n');
        const contentLines = lines.filter((line) => line.trim().length > 0);
        if (!contentLines.length) {
            return;
        }
        const allBulleted = contentLines.every((line) => line.trim().startsWith('- '));
        const allNumbered = contentLines.every((line) => /^\d+\.\s+/.test(line.trim()));
        if (allBulleted) {
            appendList(contentLines, false);
        } else if (allNumbered) {
            appendList(contentLines, true);
        } else {
            appendParagraph(block);
        }
    });
}

export function appendMessage(role, content, meta) {
    const thread = getActiveThread();
    if (!thread.messages) return;
    thread.messages.push({ id: nextId(), role: role, content: content, meta: meta || null });
    if (thread.messages.length === 1 && role === 'user') {
        const title = content.length > 40 ? content.slice(0, 40) + '\u2026' : content;
        if (thread.sub) thread.sub.title = title;
        else if (thread.main) thread.main.title = title;
        if (_updateHeaderForView) _updateHeaderForView();
        if (_updateConversationList) _updateConversationList();
    }
    renderMessages();
}

/**
 * Restore hub UI from a stored assistant-turn snapshot (does not change chat history).
 * @param {object} meta — message.meta
 */
export function restoreSubHubSnapshotFromMessageMeta(meta) {
    if (!meta || typeof meta !== 'object') return;
    const raw = meta.hubSnapshot || meta.movieHubClusters;
    const snap = cloneMovieHubClusters(raw);
    if (!snap) return;
    applyMovieHubClusters(snap);
}

/**
 * Remove one message, then replay remaining hub-filter turns from hubOriginalClusters.
 * @param {string} messageId
 */
export async function deleteMessageByIdAndRecomputeHub(messageId) {
    if (!messageId || appState.isSending) return;
    const thread = getActiveThread();
    if (!thread.sub || !Array.isArray(thread.messages)) return;
    let idx = -1;
    let j;
    for (j = 0; j < thread.messages.length; j++) {
        if (thread.messages[j].id === messageId) {
            idx = j;
            break;
        }
    }
    if (idx < 0) return;
    thread.messages.splice(idx, 1);
    appState.isSending = true;
    if (sendBtn) sendBtn.disabled = true;
    if (_showRetrieving) _showRetrieving();
    try {
        if (thread.sub.hubOriginalClusters) {
            await recomputeHubFromMessages(thread.sub, appState.useRealAgent);
        }
    } finally {
        appState.isSending = false;
        if (sendBtn) sendBtn.disabled = false;
        if (_hideRetrieving) _hideRetrieving();
        renderMessages();
    }
}

/**
 * Compact hub filter history inside #movieHubView (sub-context only). Chat rows stay in state/API but are not shown as a thread.
 */
function renderSubHubFilterHistory(thread) {
    const wrap = movieHubFilterHistoryWrap;
    const list = movieHubFilterHistory;
    if (!wrap || !list || !thread || !thread.sub) return;
    const messages = thread.messages || [];
    list.innerHTML = '';
    if (messages.length === 0) {
        wrap.classList.add('hidden');
        return;
    }
    wrap.classList.remove('hidden');
    messages.forEach(function (msg, i) {
        if (!msg.id) msg.id = nextId();
        const row = document.createElement('div');
        row.className = 'movie-hub-history-item movie-hub-history-item--' + msg.role;
        row.setAttribute('role', 'listitem');

        const mainBlock = document.createElement('div');
        mainBlock.className = 'movie-hub-history-item-main';

        const roleLabel = document.createElement('span');
        roleLabel.className = 'movie-hub-history-role';
        roleLabel.textContent = msg.role === 'user' ? 'Your question' : 'Assistant';

        const textEl = document.createElement('span');
        textEl.className = 'movie-hub-history-text';
        let displayContent = msg.content != null ? String(msg.content) : '';
        if (msg.role === 'assistant') {
            const norm = normalizeMeta(msg.meta);
            if (norm) displayContent = norm.content;
            displayContent = stripMarkdownNoiseForDisplay(displayContent);
            if (displayContent.length > 140) displayContent = displayContent.slice(0, 137) + '\u2026';
        }
        textEl.textContent = displayContent;
        if (msg.content != null && String(msg.content).length > 140) {
            textEl.setAttribute('title', String(msg.content));
        }

        mainBlock.appendChild(roleLabel);
        mainBlock.appendChild(textEl);
        row.appendChild(mainBlock);

        const actions = document.createElement('div');
        actions.className = 'movie-hub-history-actions';

        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.className = 'message-hub-action-btn';
        delBtn.textContent = 'Remove';
        delBtn.setAttribute('aria-label', 'Remove this turn from history and recompute the hub');
        delBtn.addEventListener('click', function () {
            void deleteMessageByIdAndRecomputeHub(msg.id);
        });
        actions.appendChild(delBtn);

        if (msg.role === 'assistant' && msg.meta && (msg.meta.hubSnapshot || msg.meta.movieHubClusters)) {
            const restBtn = document.createElement('button');
            restBtn.type = 'button';
            restBtn.className = 'message-hub-action-btn';
            restBtn.textContent = 'Show this hub';
            restBtn.setAttribute('aria-label', 'Restore the poster row to this response’s hub');
            restBtn.addEventListener('click', function () {
                restoreSubHubSnapshotFromMessageMeta(msg.meta);
            });
            actions.appendChild(restBtn);
        }

        if (msg.role === 'assistant' && msg.meta && (msg.meta.actualAgentMode || msg.meta.agent_mode)) {
            const modeBadge = document.createElement('span');
            modeBadge.className = 'movie-hub-history-mode';
            modeBadge.textContent = msg.meta.modeFallback
                ? 'Playground (fallback)'
                : (msg.meta.actualAgentMode || msg.meta.agent_mode) === 'REAL_AGENT' ? 'Real Agent' : 'Playground';
            actions.appendChild(modeBadge);
        }

        row.appendChild(actions);
        list.appendChild(row);

    });
}

/* ── renderMessages ── */

export function renderMessages() {
    const thread = getActiveThread();
    if (!thread || !thread.messages) return;
    const messages = thread.messages || [];

    if (appState.conversationView === 'sub' && thread.sub) {
        if (messageList) {
            messageList.innerHTML = '';
            messageList.classList.add('hidden');
        }
        if (chatColumn) chatColumn.classList.remove('empty');
        renderSubHubFilterHistory(thread);
        if (chatColumn) {
            if (appState.restoreScrollTop != null) {
                chatColumn.scrollTop = appState.restoreScrollTop;
                appState.restoreScrollTop = null;
            } else {
                chatColumn.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }
        return;
    }

    if (messageList) messageList.classList.remove('hidden');
    if (!messageList) return;
    messageList.innerHTML = '';
    if (movieHubFilterHistoryWrap) movieHubFilterHistoryWrap.classList.add('hidden');
    if (chatColumn) chatColumn.classList.toggle('empty', messages.length === 0);
    messages.forEach(function (msg, i) {
        try {
            if (!msg.id) msg.id = nextId();
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
                }
            }
            if (movieStrip) {
                content.appendChild(movieStrip);
            }
            if (msg.role === 'assistant') {
                renderAssistantContent(displayContent, bubble);
            } else {
                bubble.appendChild(document.createTextNode(displayContent));
            }

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
        const threadBefore = getActiveThread();
        let hubConversationHistory = null;
        if (appState.conversationView === 'sub'
            && threadBefore && threadBefore.sub && threadBefore.sub.contextMovie
            && Array.isArray(threadBefore.messages)) {
            hubConversationHistory = buildHubConversationHistory(threadBefore.messages, threadBefore.messages.length);
        }

        appendMessage('user', text);
        if (_showRetrieving) _showRetrieving();
        const thread = getActiveThread();
        let candidateTitles = [];
        if (appState.conversationView === 'sub'
            && thread && thread.sub && thread.sub.contextMovie) {
            const sub = thread.sub;
            const movies = [];

            if (Array.isArray(sub.similarClusters)) {
                sub.similarClusters.forEach(function (cl) {
                    const ms = (cl && Array.isArray(cl.movies)) ? cl.movies : [];
                    ms.forEach(function (m) { movies.push(m); });
                });
            }

            if (!movies.length
                && sub.contextMovie
                && Array.isArray(sub.contextMovie.relatedMovies)) {
                sub.contextMovie.relatedMovies.forEach(function (m) { movies.push(m); });
            }

            // Keep candidate titles aligned with what's currently shown and unique.
            candidateTitles = movies.map(function (m) {
                if (!m || typeof m !== 'object') return null;
                const title = (m.movie_title != null ? m.movie_title : m.title != null ? m.title : '').toString().trim();
                if (!title) return null;

                let year = m.year;
                if (year == null && m.release_date) {
                    // Best-effort year extraction for models that only carry release_date.
                    const mYear = /^(\d{4})/.exec(String(m.release_date));
                    year = mYear && mYear[1] ? mYear[1] : null;
                }
                const yearNum = year != null ? parseInt(String(year), 10) : NaN;
                if (!isNaN(yearNum) && yearNum > 0) {
                    return title + ' (' + yearNum + ')';
                }
                return title;
            }).filter(function (s) {
                if (!s) return false;
                return !!s.toString().trim();
            });
            if (candidateTitles.length > 0) {
                const seen = new Set();
                candidateTitles = candidateTitles.filter(function (t) {
                    const key = String(t || '').trim().toLowerCase();
                    if (!key || seen.has(key)) return false;
                    seen.add(key);
                    return true;
                });
            }
        }

        const outgoingText = (appState.conversationView === 'sub'
            && thread && thread.sub && thread.sub.contextMovie)
            ? prefixMovieHubContextQuery(text, thread.sub.contextMovie, candidateTitles)
            : text;
        const queryOpts = (hubConversationHistory && hubConversationHistory.length > 0)
            ? { hubConversationHistory: hubConversationHistory }
            : {};
        const result = await sendQuery(outgoingText, appState.useRealAgent, queryOpts);
        const responseText = (result && (result.response || result.answer))
            ? String(result.response || result.answer)
            : 'No response.';
        appendMessage('assistant', responseText, result);
        if (_applyMovieHubClusters && result && Array.isArray(result.movieHubClusters)) {
            _applyMovieHubClusters(result.movieHubClusters);
            const tAfter = getActiveThread();
            const msgsAfter = tAfter && tAfter.messages ? tAfter.messages : [];
            const lastMsg = msgsAfter.length > 0 ? msgsAfter[msgsAfter.length - 1] : null;
            if (lastMsg && lastMsg.role === 'assistant' && lastMsg.meta && typeof lastMsg.meta === 'object') {
                const snap = cloneMovieHubClusters(result.movieHubClusters);
                lastMsg.meta.hubSnapshot = snap;
                lastMsg.meta.movieHubClusters = snap;
            }
        }
        if (_hideRetrieving) _hideRetrieving();
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
