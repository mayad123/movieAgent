/**
 * CineMind — ES module entry point.
 * Imports all modules and wires them together.
 */

// Foundation
import { appState, migrateConversationsToNested } from './modules/state.js';
import * as dom from './modules/dom.js';

// Features
import { initWhereToWatch, openWhereToWatchDrawer, onWhereToWatch } from './modules/where-to-watch.js';
import { openMovieDetails, initMovieDetails } from './modules/movie-details.js';
import { setPosterCallbacks, renderCollectionPanel, addToCollection, createHeroCard, createCandidateCard, createAttachmentsFromSections, createUnifiedMovieStrip, captureAssetsForProjectScope } from './modules/posters.js';
import { setMessageCallbacks, renderMessages, appendMessage, sendMessage } from './modules/messages.js';
import { setLayoutCallbacks, initLayout, addConversation, updateConversationList, updateHeaderForView, updateRightPanelScope, loadProjects, loadProjectAssets, updateHeaderRealAgentIndicator, showRetrieving, hideRetrieving, openRightPanelToCollection, showSavedToCollectionToast, showSavedToProjectToast, showAlreadyAddedToast, showFallbackToast, addSubConversationFromPoster } from './modules/layout.js';

// Wire callbacks (breaks circular dependencies)
setLayoutCallbacks({
    renderMessages,
    renderCollectionPanel,
    addSubConversationFromPoster: null
});

setPosterCallbacks({
    openWhereToWatch: openWhereToWatchDrawer,
    openMovieDetails: openMovieDetails,
    addSubConversation: addSubConversationFromPoster,
    openRightPanelToCollection,
    showSavedToCollectionToast,
    showSavedToProjectToast,
    showAlreadyAddedToast,
    showFallbackToast,
    loadProjectAssets,
    updateRightPanelScope
});

setMessageCallbacks({
    showRetrieving,
    hideRetrieving,
    captureAssetsForProjectScope,
    createHeroCard,
    createCandidateCard,
    createAttachmentsFromSections,
    createUnifiedMovieStrip,
    updateConversationList,
    updateHeaderForView,
    updateHeaderRealAgentIndicator,
    showFallbackToast
});

// Initialize
initWhereToWatch();
initMovieDetails();
initLayout();

// Boot
migrateConversationsToNested();
loadProjects();
updateHeaderRealAgentIndicator();
if (appState.conversations.length === 0) {
    addConversation();
} else {
    updateConversationList();
    updateHeaderForView();
    updateRightPanelScope();
}

// Wire send button and composer (avoid optional chaining for wider browser support)
if (dom.sendBtn) {
    dom.sendBtn.addEventListener('click', sendMessage);
}
if (dom.composerInput) {
    dom.composerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    dom.composerInput.addEventListener('input', () => {
        dom.composerInput.style.height = 'auto';
        dom.composerInput.style.height = Math.min(dom.composerInput.scrollHeight, 200) + 'px';
    });
    dom.composerInput.focus();
}
