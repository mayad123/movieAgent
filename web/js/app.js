/**
 * CineMind — production app (from playground UI).
 * Depends on: js/config.js (window.CINEMIND_CONFIG.apiBase).
 * Data contracts: see web/DATA_CONTRACTS.md (Message, Media Strip, Conversation, backward compatibility).
 */
(function () {
    'use strict';

    var API_BASE = window.CINEMIND_CONFIG && window.CINEMIND_CONFIG.apiBase ? window.CINEMIND_CONFIG.apiBase : 'http://localhost:8000';

    var sidebar = document.getElementById('sidebar');
    var sidebarToggle = document.getElementById('sidebarToggle');
    var conversationList = document.getElementById('conversationList');
    var conversationTitle = document.getElementById('conversationTitle');
    var chatColumn = document.getElementById('chatColumn');
    var messageList = document.getElementById('messageList');
    var retrievingRow = document.getElementById('retrievingRow');
    var composerInput = document.getElementById('composerInput');
    var sendBtn = document.getElementById('sendBtn');
    var newChatBtn = document.getElementById('newChatBtn');
    var headerNewChat = document.getElementById('headerNewChat');

    var messages = [];
    var isSending = false;
    var app = document.getElementById('app');

    function toggleSidebar() {
        sidebar.classList.toggle('collapsed');
        app.classList.toggle('sidebar-collapsed', sidebar.classList.contains('collapsed'));
    }
    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);

    function startNewChat() {
        messages = [];
        renderMessages();
        updateConversationList();
        conversationTitle.textContent = 'New conversation';
        composerInput.value = '';
        if (composerInput) composerInput.focus();
    }
    if (newChatBtn) newChatBtn.addEventListener('click', startNewChat);
    if (headerNewChat) headerNewChat.addEventListener('click', startNewChat);

    function updateConversationList() {
        if (!conversationList) return;
        conversationList.innerHTML = '';
        var userMessages = messages.filter(function (m) { return m.role === 'user'; });
        userMessages.forEach(function (m, i) {
            var el = document.createElement('div');
            el.className = 'conversation-item';
            el.textContent = m.content.length > 36 ? m.content.slice(0, 36) + '\u2026' : m.content;
            var msgIndex = messages.indexOf(m);
            el.addEventListener('click', function () {
                var msgEl = messageList.querySelector('[data-msg-index="' + msgIndex + '"]');
                if (msgEl) msgEl.scrollIntoView({ behavior: 'smooth' });
            });
            conversationList.appendChild(el);
        });
    }

    function showRetrieving() {
        if (retrievingRow) retrievingRow.classList.remove('hidden');
        if (chatColumn) chatColumn.scrollTop = chatColumn.scrollHeight;
    }
    function hideRetrieving() {
        if (retrievingRow) retrievingRow.classList.add('hidden');
    }

    function appendMessage(role, content, meta) {
        messages.push({ role: role, content: content, meta: meta || null });
        renderMessages();
        updateConversationList();
        if (messages.length === 1 && role === 'user') {
            conversationTitle.textContent = content.length > 40 ? content.slice(0, 40) + '\u2026' : content;
        }
    }

    function escapeHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    /* Media Strip: contract in DATA_CONTRACTS.md. Require movie_title; primary_image_url, thumbnail_urls optional. */
    function createMediaStrip(mediaStrip) {
        if (!mediaStrip || !mediaStrip.movie_title) return null;
        var title = String(mediaStrip.movie_title).trim();
        if (!title) return null;
        var primaryUrl = mediaStrip.primary_image_url && mediaStrip.primary_image_url.trim();
        var thumbUrls = Array.isArray(mediaStrip.thumbnail_urls)
            ? mediaStrip.thumbnail_urls.slice(0, 3).filter(Boolean)
            : [];

        var wrap = document.createElement('div');
        wrap.className = 'media-strip';

        if (!primaryUrl && thumbUrls.length === 0) {
            var placeholder = document.createElement('div');
            placeholder.className = 'media-strip-placeholder';
            placeholder.innerHTML = '<span class="media-strip-placeholder-title">' + escapeHtml(title) + '</span><span class="media-strip-placeholder-caption">No image available yet.</span>';
            wrap.appendChild(placeholder);
            return wrap;
        }

        var layout = document.createElement('div');
        layout.className = 'media-strip-layout';
        if (primaryUrl && thumbUrls.length === 0) wrap.classList.add('has-primary-only');

        var primarySlot = document.createElement('div');
        primarySlot.className = 'media-strip-primary';
        if (primaryUrl) {
            primarySlot.classList.add('media-strip-skeleton');
            var img = document.createElement('img');
            img.src = primaryUrl;
            img.alt = title;
            img.loading = 'lazy';
            img.onload = function () { primarySlot.classList.remove('media-strip-skeleton'); };
            img.onerror = function () {
                primarySlot.classList.remove('media-strip-skeleton');
                primarySlot.innerHTML = '';
                var ph = document.createElement('div');
                ph.className = 'media-strip-placeholder';
                ph.style.minHeight = '140px';
                ph.innerHTML = '<span class="media-strip-placeholder-title">' + escapeHtml(title) + '</span><span class="media-strip-placeholder-caption">No image available yet.</span>';
                primarySlot.appendChild(ph);
            };
            primarySlot.appendChild(img);
        } else {
            var ph0 = document.createElement('div');
            ph0.className = 'media-strip-placeholder';
            ph0.style.minHeight = '100%';
            ph0.innerHTML = '<span class="media-strip-placeholder-title">' + escapeHtml(title) + '</span><span class="media-strip-placeholder-caption">No image available yet.</span>';
            primarySlot.appendChild(ph0);
        }
        layout.appendChild(primarySlot);

        var thumbContainer = document.createElement('div');
        thumbContainer.className = 'media-strip-thumbnails';
        thumbUrls.forEach(function (url) {
            var thumb = document.createElement('div');
            thumb.className = 'media-strip-thumb media-strip-skeleton';
            var timg = document.createElement('img');
            timg.src = url;
            timg.alt = '';
            timg.loading = 'lazy';
            timg.onload = function () { thumb.classList.remove('media-strip-skeleton'); };
            timg.onerror = function () { thumb.classList.remove('media-strip-skeleton'); };
            thumb.appendChild(timg);
            thumbContainer.appendChild(thumb);
        });
        layout.appendChild(thumbContainer);
        wrap.appendChild(layout);
        return wrap;
    }

    function renderMessages() {
        if (!messageList) return;
        messageList.innerHTML = '';
        chatColumn.classList.toggle('empty', messages.length === 0);
        messages.forEach(function (msg, i) {
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
            var mediaStrip = msg.role === 'assistant' && msg.meta && msg.meta.media_strip ? createMediaStrip(msg.meta.media_strip) : null;
            if (mediaStrip) bubble.appendChild(mediaStrip);
            bubble.appendChild(document.createTextNode(msg.content));
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
        });
        if (chatColumn) chatColumn.scrollTop = chatColumn.scrollHeight;
    }

    async function sendMessage() {
        var text = composerInput.value.trim();
        if (!text || isSending) return;
        isSending = true;
        sendBtn.disabled = true;
        composerInput.value = '';
        composerInput.style.height = 'auto';

        appendMessage('user', text);
        showRetrieving();

        try {
            var response = await fetch(API_BASE + '/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_query: text })
            });
            if (!response.ok) {
                var err = await response.json();
                throw new Error(err.detail && err.detail.error ? err.detail.error : 'HTTP ' + response.status);
            }
            var result = await response.json();
            var responseText = result.response || result.answer || 'No response.';
            hideRetrieving();
            appendMessage('assistant', responseText, result);
        } catch (err) {
            hideRetrieving();
            appendMessage('assistant', 'Error: ' + err.message, null);
        } finally {
            isSending = false;
            sendBtn.disabled = false;
            if (composerInput) composerInput.focus();
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
})();
