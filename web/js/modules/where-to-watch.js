import {
    whereToWatchDrawerEl,
    whereToWatchDrawerTitle,
    whereToWatchDrawerClose,
    whereToWatchDrawerContent,
    whereToWatchDrawerLoading,
    whereToWatchDrawerResults,
    whereToWatchDrawerEmpty,
    whereToWatchDrawerError,
    whereToWatchDrawerErrorText,
} from './dom.js';
import { fetchWhereToWatch } from './api.js';
import { normalizeWhereToWatchErrorMessage } from './normalize.js';

let whereToWatchDrawerState = {
    open: false,
    movie: null,
    status: 'idle',
    results: null,
    error: null,
};

export function closeWhereToWatchDrawer() {
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
    const s = whereToWatchDrawerState;
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
    const hasOffers = s.results && Array.isArray(s.results.offers) && s.results.offers.length > 0;
    const hasGroups = s.results && Array.isArray(s.results.groups) && s.results.groups.length > 0;
    if (s.status === 'empty' || (s.status === 'success' && !hasOffers && !hasGroups)) {
        whereToWatchDrawerEmpty.classList.remove('hidden');
        return;
    }
    if (s.status === 'success' && s.results && (hasOffers || hasGroups)) {
        whereToWatchDrawerResults.classList.remove('hidden');
        whereToWatchDrawerResults.innerHTML = '';
        if (hasOffers) {
            const accessOrder = ['subscription', 'free', 'rent', 'buy', 'tve', 'other', 'unknown'];
            const byType = {};
            s.results.offers.forEach(function (offer) {
                let at = (offer.accessType || 'unknown').toLowerCase();
                if (at === 'rental') at = 'rent';
                if (at === 'purchase') at = 'buy';
                if (!byType[at]) byType[at] = [];
                byType[at].push(offer);
            });
            const region = (s.results.region && String(s.results.region).trim()) || '';
            if (region) {
                const regionLine = document.createElement('p');
                regionLine.className = 'where-to-watch-drawer-region';
                regionLine.textContent = 'Results for ' + region;
                whereToWatchDrawerResults.appendChild(regionLine);
            }
            accessOrder.forEach(function (at) {
                if (!byType[at] || byType[at].length === 0) return;
                const groupTitle = document.createElement('div');
                groupTitle.className = 'where-to-watch-group-title';
                groupTitle.textContent = at.charAt(0).toUpperCase() + at.slice(1);
                whereToWatchDrawerResults.appendChild(groupTitle);
                const list = document.createElement('ul');
                list.className = 'where-to-watch-offer-list';
                byType[at].forEach(function (offer) {
                    const li = document.createElement('li');
                    li.className = 'where-to-watch-offer';
                    const info = document.createElement('div');
                    info.className = 'where-to-watch-offer-info';
                    const provider = document.createElement('div');
                    provider.className = 'where-to-watch-offer-provider';
                    provider.textContent = (offer.provider && offer.provider.name) || 'Provider';
                    info.appendChild(provider);
                    if (offer.quality && String(offer.quality).trim()) {
                        const quality = document.createElement('span');
                        quality.className = 'where-to-watch-offer-quality';
                        quality.textContent = String(offer.quality).trim();
                        info.appendChild(quality);
                    }
                    if (offer.price && typeof offer.price.amount === 'number') {
                        const price = document.createElement('div');
                        price.className = 'where-to-watch-offer-price';
                        price.textContent = (offer.price.currency || 'USD') + ' ' + Number(offer.price.amount);
                        info.appendChild(price);
                    }
                    const url = (offer.webUrl && offer.webUrl.trim()) || (offer.iosUrl && offer.iosUrl.trim()) || (offer.androidUrl && offer.androidUrl.trim());
                    if (url) {
                        const rowLink = document.createElement('a');
                        rowLink.className = 'where-to-watch-offer-link';
                        rowLink.href = url;
                        rowLink.target = '_blank';
                        rowLink.rel = 'noopener';
                        rowLink.setAttribute('aria-label', 'Open ' + ((offer.provider && offer.provider.name) || 'provider'));
                        rowLink.appendChild(info);
                        li.appendChild(rowLink);
                    } else {
                        li.appendChild(info);
                    }
                    list.appendChild(li);
                });
                whereToWatchDrawerResults.appendChild(list);
            });
        } else if (hasGroups) {
            const region = (s.results.region && String(s.results.region).trim()) || '';
            if (region) {
                const regionLine = document.createElement('p');
                regionLine.className = 'where-to-watch-drawer-region';
                regionLine.textContent = 'Results for ' + region;
                whereToWatchDrawerResults.appendChild(regionLine);
            }
            s.results.groups.forEach(function (group) {
                const groupTitle = document.createElement('div');
                groupTitle.className = 'where-to-watch-group-title';
                groupTitle.textContent = group.label || group.accessType || 'Watch';
                whereToWatchDrawerResults.appendChild(groupTitle);
                const list = document.createElement('ul');
                list.className = 'where-to-watch-offer-list';
                (group.offers || []).forEach(function (offer) {
                    const li = document.createElement('li');
                    li.className = 'where-to-watch-offer';
                    const info = document.createElement('div');
                    info.className = 'where-to-watch-offer-info';
                    const provider = document.createElement('div');
                    provider.className = 'where-to-watch-offer-provider';
                    provider.textContent = offer.providerName || (offer.provider && offer.provider.name) || 'Provider';
                    info.appendChild(provider);
                    if (offer.price && typeof offer.price.amount === 'number') {
                        const price = document.createElement('div');
                        price.className = 'where-to-watch-offer-price';
                        price.textContent = (offer.price.currency || 'USD') + ' ' + Number(offer.price.amount);
                        info.appendChild(price);
                    }
                    const url = offer.webUrl || offer.deeplink;
                    if (url) {
                        const rowLink = document.createElement('a');
                        rowLink.className = 'where-to-watch-offer-link';
                        rowLink.href = url;
                        rowLink.target = '_blank';
                        rowLink.rel = 'noopener';
                        rowLink.setAttribute('aria-label', 'Open ' + (offer.providerName || (offer.provider && offer.provider.name) || 'provider'));
                        rowLink.appendChild(info);
                        li.appendChild(rowLink);
                    } else {
                        li.appendChild(info);
                    }
                    list.appendChild(li);
                });
                whereToWatchDrawerResults.appendChild(list);
            });
        }
    }
}

export function openWhereToWatchDrawer(movie) {
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
    fetchWhereToWatch(movie, function (err, data) {
        if (err) {
            whereToWatchDrawerState.status = 'error';
            whereToWatchDrawerState.error = normalizeWhereToWatchErrorMessage(err.message || String(err));
        } else if (!data) {
            whereToWatchDrawerState.status = 'empty';
            whereToWatchDrawerState.results = null;
        } else {
            const hasOffers = Array.isArray(data.offers) && data.offers.length > 0;
            const hasGroups = Array.isArray(data.groups) && data.groups.length > 0;
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
}

export function onWhereToWatch(movie) {
    openWhereToWatchDrawer(movie);
}

export function initWhereToWatch() {
    if (whereToWatchDrawerClose) {
        whereToWatchDrawerClose.addEventListener('click', function () { closeWhereToWatchDrawer(); });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && whereToWatchDrawerState.open) {
            closeWhereToWatchDrawer();
        }
    });
}
