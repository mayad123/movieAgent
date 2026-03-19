import {
    chatColumn,
    composerInput,
    movieDetailsView,
    movieDetailsCloseBtn,
    movieDetailsTitle,
    movieDetailsYear,
    movieDetailsTagline,
    movieDetailsPosterWrap,
    movieDetailsHeroMeta,
    movieDetailsStorySection,
    movieDetailsStory,
    movieDetailsCreditsSection,
    movieDetailsDirectorsGroup,
    movieDetailsCastGroup,
    movieDetailsDirectorsList,
    movieDetailsCastList,
    movieDetailsMetaSection,
    movieDetailsMetaList,
    movieDetailsRelatedSection,
    movieDetailsRelatedList,
    movieDetailsWhereToWatchSection,
    movieDetailsWhereToWatchLoading,
    movieDetailsWhereToWatchResults,
    movieDetailsWhereToWatchEmpty,
    movieDetailsWhereToWatchError,
    movieDetailsWhereToWatchErrorText
} from './dom.js';
import { createCandidateCard } from './posters.js';
import { fetchWhereToWatch } from './api.js';
import { API_BASE, SEND_TIMEOUT_MS } from './state.js';

let currentMovie = null;
let previousScrollTop = null;
let tmdbDetailsAbortController = null;

function safeTrim(value) {
    return value == null ? '' : String(value).trim();
}

function clearElement(el) {
    if (!el) return;
    el.innerHTML = '';
}

function setHidden(el, hidden) {
    if (!el) return;
    el.classList.toggle('hidden', hidden);
}

function renderHeader(movie) {
    if (!movieDetailsTitle) return;
    const title = safeTrim(movie.movie_title || movie.title);
    movieDetailsTitle.textContent = title || '';

    if (movieDetailsYear) {
        const year = movie.year != null ? String(movie.year) : '';
        movieDetailsYear.textContent = year ? '(' + year + ')' : '';
    }

    if (movieDetailsTagline) {
        const tagline = safeTrim(movie.tagline || movie.shortDescription || movie.tag_line);
        movieDetailsTagline.textContent = tagline;
        movieDetailsTagline.classList.toggle('hidden', !tagline);
    }
}

function renderHero(movie) {
    clearElement(movieDetailsPosterWrap);
    clearElement(movieDetailsHeroMeta);
    if (!movieDetailsPosterWrap || !movieDetailsHeroMeta) return;

    const backdropUrl = safeTrim(movie.backdrop_url || movie.backdropUrl);
    const hasBackdrop = !!backdropUrl;
    if (hasBackdrop) {
        movieDetailsPosterWrap.classList.add('has-backdrop');
        movieDetailsPosterWrap.style.setProperty('--hero-backdrop-url', 'url("' + backdropUrl + '")');
    } else {
        movieDetailsPosterWrap.classList.remove('has-backdrop');
        movieDetailsPosterWrap.style.removeProperty('--hero-backdrop-url');
    }

    const title = safeTrim(movie.movie_title || movie.title);
    const imgUrl = safeTrim(
        movie.primary_image_url
        || movie.posterUrl
        || movie.poster_url
        || movie.imageUrl
    );

    if (imgUrl) {
        const img = document.createElement('img');
        img.src = imgUrl;
        img.alt = title || 'Poster';
        img.loading = 'lazy';
        movieDetailsPosterWrap.appendChild(img);
    } else {
        const ph = document.createElement('div');
        ph.className = 'movie-details-hero-placeholder';
        const phTitle = document.createElement('div');
        phTitle.className = 'movie-details-hero-placeholder-title';
        phTitle.textContent = title || 'Movie';
        const phCaption = document.createElement('div');
        phCaption.textContent = 'No image available';
        ph.appendChild(phTitle);
        ph.appendChild(phCaption);
        movieDetailsPosterWrap.appendChild(ph);
    }

    const metaPrimary = document.createElement('div');
    metaPrimary.className = 'movie-details-hero-meta-primary';
    const pieces = [];
    if (movie.year != null) {
        pieces.push(String(movie.year));
    }
    const genres = Array.isArray(movie.genres)
        ? movie.genres
        : Array.isArray(movie.genre_names) ? movie.genre_names : [];
    if (genres.length) {
        pieces.push(genres.slice(0, 3).join(', '));
    }
    const runtimeMinutes = movie.runtime_minutes || movie.runtimeMinutes || movie.runtime;
    if (runtimeMinutes) {
        const mins = Number(runtimeMinutes);
        if (!isNaN(mins) && mins > 0) {
            const hours = Math.floor(mins / 60);
            const minsR = mins % 60;
            const text = (hours ? hours + 'h ' : '') + (minsR ? minsR + 'm' : '');
            if (text) pieces.push(text);
        }
    }
    metaPrimary.textContent = pieces.join(' \u2022 ');
    movieDetailsHeroMeta.appendChild(metaPrimary);

    const chipsWrap = document.createElement('div');
    chipsWrap.className = 'movie-details-hero-meta-chips';
    const rating = movie.rating || movie.vote_average || movie.voteAverage;
    const voteCount = movie.vote_count || movie.voteCount;
    if (rating != null) {
        const chip = document.createElement('span');
        chip.className = 'movie-details-chip';
        const ratingText = Number(rating).toFixed(1);
        chip.textContent = voteCount ? (ratingText + ' / 10 • ' + voteCount + ' votes') : (ratingText + ' / 10');
        chipsWrap.appendChild(chip);
    }
    const language = safeTrim(movie.language || movie.original_language);
    if (language) {
        const chip = document.createElement('span');
        chip.className = 'movie-details-chip';
        chip.textContent = language.toUpperCase();
        chipsWrap.appendChild(chip);
    }
    const country = safeTrim(movie.country || movie.production_country);
    if (country) {
        const chip = document.createElement('span');
        chip.className = 'movie-details-chip';
        chip.textContent = country;
        chipsWrap.appendChild(chip);
    }
    if (chipsWrap.children.length > 0) {
        movieDetailsHeroMeta.appendChild(chipsWrap);
    }
}

function renderStory(movie) {
    if (!movieDetailsStorySection || !movieDetailsStory) return;
    const story = safeTrim(
        movie.overview
        || movie.summary
        || movie.plot
        || movie.description
    );
    movieDetailsStory.textContent = story;
    setHidden(movieDetailsStorySection, !story);
}

function normalizeNames(list) {
    if (!list) return [];
    if (Array.isArray(list)) {
        return list.map(function (it) {
            if (typeof it === 'string') return safeTrim(it);
            if (it && typeof it === 'object' && it.name) return safeTrim(it.name);
            return '';
        }).filter(function (s) { return !!s; });
    }
    if (typeof list === 'string') return [safeTrim(list)];
    return [];
}

function renderCredits(movie) {
    if (!movieDetailsCreditsSection) return;
    const directors = normalizeNames(
        movie.directors
        || (movie.credits && movie.credits.directors)
        || (movie.credits && movie.credits.director)
    );
    const cast = normalizeNames(
        movie.cast
        || (movie.credits && movie.credits.cast)
    );

    clearElement(movieDetailsDirectorsList);
    clearElement(movieDetailsCastList);

    if (movieDetailsDirectorsGroup) {
        setHidden(movieDetailsDirectorsGroup, directors.length === 0);
    }
    if (movieDetailsCastGroup) {
        setHidden(movieDetailsCastGroup, cast.length === 0);
    }

    directors.forEach(function (name) {
        const li = document.createElement('li');
        li.textContent = name;
        movieDetailsDirectorsList.appendChild(li);
    });
    const maxCast = 12;
    cast.slice(0, maxCast).forEach(function (name) {
        const li = document.createElement('li');
        li.textContent = name;
        movieDetailsCastList.appendChild(li);
    });

    const hasAny = directors.length > 0 || cast.length > 0;
    setHidden(movieDetailsCreditsSection, !hasAny);
}

function addMetaRow(label, value) {
    if (!movieDetailsMetaList || !value) return;
    const trimmed = safeTrim(value);
    if (!trimmed) return;
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = trimmed;
    movieDetailsMetaList.appendChild(dt);
    movieDetailsMetaList.appendChild(dd);
}

function renderMeta(movie) {
    if (!movieDetailsMetaSection || !movieDetailsMetaList) return;
    clearElement(movieDetailsMetaList);

    const runtimeMinutes = movie.runtime_minutes || movie.runtimeMinutes || movie.runtime;
    if (runtimeMinutes) {
        const mins = Number(runtimeMinutes);
        if (!isNaN(mins) && mins > 0) {
            const hours = Math.floor(mins / 60);
            const minsR = mins % 60;
            const text = (hours ? hours + 'h ' : '') + (minsR ? minsR + 'm' : '');
            addMetaRow('Runtime', text);
        }
    }
    const genres = Array.isArray(movie.genres)
        ? movie.genres
        : Array.isArray(movie.genre_names) ? movie.genre_names : [];
    if (genres.length) addMetaRow('Genres', genres.join(', '));

    const releaseDate = safeTrim(movie.release_date || movie.releaseDate);
    if (releaseDate) addMetaRow('Release date', releaseDate);

    const language = safeTrim(movie.language || movie.original_language);
    if (language) addMetaRow('Language', language.toUpperCase());

    const country = safeTrim(movie.country || movie.production_country);
    if (country) addMetaRow('Country', country);

    const certification = safeTrim(
        movie.content_rating
        || movie.certification
        || movie.rated
    );
    if (certification) addMetaRow('Rating', certification);

    const hasRows = movieDetailsMetaList.children.length > 0;
    setHidden(movieDetailsMetaSection, !hasRows);
}

function getRelatedMoviesFromMovie(movie) {
    if (!movie) return [];
    if (Array.isArray(movie.relatedMovies)) return movie.relatedMovies;
    if (Array.isArray(movie.similar)) return movie.similar;
    return [];
}

function renderRelatedMovies(movie) {
    if (!movieDetailsRelatedSection || !movieDetailsRelatedList) return;
    clearElement(movieDetailsRelatedList);
    const related = getRelatedMoviesFromMovie(movie);
    if (!related.length) {
        setHidden(movieDetailsRelatedSection, true);
        return;
    }
    related.forEach(function (item) {
        const li = document.createElement('li');
        li.className = 'movie-details-related-item';

        if (item && typeof item === 'object') {
            const title = safeTrim(item.movie_title || item.title);
            const year = item.year != null ? Number(item.year) : undefined;

            const card = createCandidateCard({
                movie_title: title,
                title: item.title || item.movie_title || title,
                year: Number.isFinite(year) ? year : undefined,
                primary_image_url: item.primary_image_url || item.imageUrl || item.primaryImageUrl,
                page_url: item.page_url || item.pageUrl || '',
                tmdbId: item.tmdbId || item.tmdb_id,
                mediaType: item.mediaType || item.media_type
            }, { link: false });

            if (card) li.appendChild(card);
            else li.textContent = title || '';

            if (title) {
                li.classList.add('movie-details-related-item--interactive');
                li.tabIndex = 0;
                li.addEventListener('click', function () {
                    openMovieDetails(item);
                });
                li.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        openMovieDetails(item);
                    }
                });
            }
        } else {
            li.textContent = safeTrim(String(item));
        }
        movieDetailsRelatedList.appendChild(li);
    });
    setHidden(movieDetailsRelatedSection, false);
}

function clearWhereToWatch() {
    if (!movieDetailsWhereToWatchSection) return;
    setHidden(movieDetailsWhereToWatchLoading, true);
    setHidden(movieDetailsWhereToWatchResults, true);
    setHidden(movieDetailsWhereToWatchEmpty, true);
    setHidden(movieDetailsWhereToWatchError, true);
    clearElement(movieDetailsWhereToWatchResults);
    if (movieDetailsWhereToWatchErrorText) movieDetailsWhereToWatchErrorText.textContent = '';
}

function renderWhereToWatchLoading() {
    if (!movieDetailsWhereToWatchSection) return;
    clearWhereToWatch();
    setHidden(movieDetailsWhereToWatchLoading, false);
}

function renderWhereToWatchError(message) {
    if (!movieDetailsWhereToWatchSection) return;
    clearWhereToWatch();
    if (movieDetailsWhereToWatchErrorText) {
        movieDetailsWhereToWatchErrorText.textContent = message || 'Unable to load streaming information.';
    }
    setHidden(movieDetailsWhereToWatchError, false);
}

function renderWhereToWatchResults(data) {
    if (!movieDetailsWhereToWatchSection) return;
    clearWhereToWatch();
    const hasOffers = data && Array.isArray(data.offers) && data.offers.length > 0;
    const hasGroups = data && Array.isArray(data.groups) && data.groups.length > 0;
    if (!hasOffers && !hasGroups) {
        setHidden(movieDetailsWhereToWatchEmpty, false);
        return;
    }
    if (!movieDetailsWhereToWatchResults) return;

    const root = movieDetailsWhereToWatchResults;
    if (hasOffers) {
        const accessOrder = ['subscription', 'free', 'rent', 'buy', 'tve', 'other', 'unknown'];
        const byType = {};
        data.offers.forEach(function (offer) {
            let at = (offer.accessType || 'unknown').toLowerCase();
            if (at === 'rental') at = 'rent';
            if (at === 'purchase') at = 'buy';
            if (!byType[at]) byType[at] = [];
            byType[at].push(offer);
        });
        const region = data.region && String(data.region).trim();
        if (region) {
            const regionLine = document.createElement('p');
            regionLine.className = 'movie-details-where-region';
            regionLine.textContent = 'Results for ' + region;
            root.appendChild(regionLine);
        }
        accessOrder.forEach(function (at) {
            const list = byType[at];
            if (!list || list.length === 0) return;
            const title = document.createElement('div');
            title.className = 'movie-details-where-group-title';
            title.textContent = at.charAt(0).toUpperCase() + at.slice(1);
            root.appendChild(title);
            const ul = document.createElement('ul');
            ul.className = 'movie-details-where-offer-list';
            list.forEach(function (offer) {
                const li = document.createElement('li');
                li.className = 'movie-details-where-offer';
                const url = (offer.webUrl && offer.webUrl.trim()) || (offer.iosUrl && offer.iosUrl.trim()) || (offer.androidUrl && offer.androidUrl.trim());
                const link = document.createElement(url ? 'a' : 'div');
                if (url) {
                    link.href = url;
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.className = 'movie-details-where-offer-link';
                } else {
                    link.className = 'movie-details-where-offer-link';
                }
                const providerName = (offer.provider && offer.provider.name) || 'Provider';
                const providerEl = document.createElement('div');
                providerEl.className = 'movie-details-where-offer-provider';
                providerEl.textContent = providerName;
                link.appendChild(providerEl);
                if (offer.price && typeof offer.price.amount === 'number') {
                    const priceEl = document.createElement('div');
                    priceEl.className = 'movie-details-where-offer-price';
                    priceEl.textContent = (offer.price.currency || 'USD') + ' ' + Number(offer.price.amount);
                    link.appendChild(priceEl);
                }
                li.appendChild(link);
                ul.appendChild(li);
            });
            root.appendChild(ul);
        });
    } else if (hasGroups) {
        const region = data.region && String(data.region).trim();
        if (region) {
            const regionLine = document.createElement('p');
            regionLine.className = 'movie-details-where-region';
            regionLine.textContent = 'Results for ' + region;
            root.appendChild(regionLine);
        }
        data.groups.forEach(function (group) {
            const title = document.createElement('div');
            title.className = 'movie-details-where-group-title';
            title.textContent = group.label || group.accessType || 'Watch';
            root.appendChild(title);
            const ul = document.createElement('ul');
            ul.className = 'movie-details-where-offer-list';
            (group.offers || []).forEach(function (offer) {
                const li = document.createElement('li');
                li.className = 'movie-details-where-offer';
                const url = offer.webUrl || offer.deeplink;
                const link = document.createElement(url ? 'a' : 'div');
                if (url) {
                    link.href = url;
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.className = 'movie-details-where-offer-link';
                } else {
                    link.className = 'movie-details-where-offer-link';
                }
                const providerName = offer.providerName || (offer.provider && offer.provider.name) || 'Provider';
                const providerEl = document.createElement('div');
                providerEl.className = 'movie-details-where-offer-provider';
                providerEl.textContent = providerName;
                link.appendChild(providerEl);
                if (offer.price && typeof offer.price.amount === 'number') {
                    const priceEl = document.createElement('div');
                    priceEl.className = 'movie-details-where-offer-price';
                    priceEl.textContent = (offer.price.currency || 'USD') + ' ' + Number(offer.price.amount);
                    link.appendChild(priceEl);
                }
                li.appendChild(link);
                ul.appendChild(li);
            });
            root.appendChild(ul);
        });
    }
    setHidden(movieDetailsWhereToWatchResults, false);
}

async function fetchMovieDetails(tmdbId, controller, timeoutMs) {
    const tmdbIdStr = safeTrim(tmdbId);
    if (!tmdbIdStr) throw new Error('tmdbId is required');
    const url = API_BASE + '/api/movies/' + encodeURIComponent(tmdbIdStr) + '/details';
    let timeoutId = null;
    try {
        timeoutId = setTimeout(function () {
            try { controller.abort(); } catch (_) { /* ignore */ }
        }, timeoutMs);
        const res = await fetch(url, { method: 'GET', signal: controller.signal });
        if (!res.ok) {
            let msg = res.statusText || 'Request failed';
            try {
                const body = await res.json();
                msg = (body && (body.detail || body.message)) ? (body.detail || body.message) : msg;
            } catch (_) { /* ignore */ }
            throw new Error(msg);
        }
        const data = await res.json();
        return data;
    } finally {
        if (timeoutId) clearTimeout(timeoutId);
    }
}

function setStoryLoading() {
    if (!movieDetailsStorySection || !movieDetailsStory) return;
    if (!movieDetailsStorySection.classList.contains('hidden')) {
        // leave existing visible state alone
    }
    movieDetailsStory.textContent = 'Loading details...';
    setHidden(movieDetailsStorySection, false);
}

async function maybeLoadTmdbDetails(movie) {
    if (!movie) return;
    const tmdbId = movie.tmdbId || movie.tmdb_id;
    const tmdbIdStr = safeTrim(tmdbId);
    if (!tmdbIdStr) return;
    if (!movieDetailsView || movieDetailsView.classList.contains('hidden')) return;

    // Abort any previous in-flight fetch for the modal.
    if (tmdbDetailsAbortController) {
        try { tmdbDetailsAbortController.abort(); } catch (_) { /* ignore */ }
    }
    tmdbDetailsAbortController = new AbortController();

    const requestTmdbId = tmdbIdStr;
    const timeoutMs = Math.min(SEND_TIMEOUT_MS, 12000);

    // If we don't have an overview yet, show a small non-stuck loading state.
    if (!safeTrim(movie.overview) && !safeTrim(movie.summary) && !safeTrim(movie.plot)) {
        setStoryLoading();
    }

    try {
        const details = await fetchMovieDetails(requestTmdbId, tmdbDetailsAbortController, timeoutMs);
        if (!details || typeof details !== 'object') return;

        const activeTmdbId = safeTrim((currentMovie && (currentMovie.tmdbId || currentMovie.tmdb_id)) || '');
        if (activeTmdbId !== requestTmdbId) return; // modal switched movies

        const hasExistingRelated = Array.isArray(currentMovie && currentMovie.relatedMovies) && currentMovie.relatedMovies.length > 0;
        const merged = Object.assign({}, currentMovie, details, { tmdbId: requestTmdbId });
        // Prefer poster-derived related movies when present; only use backend enrichment as fallback.
        if (hasExistingRelated) {
            merged.relatedMovies = currentMovie.relatedMovies;
        }
        currentMovie = merged;

        renderHeader(currentMovie);
        renderHero(currentMovie);
        renderStory(currentMovie);
        renderCredits(currentMovie);
        renderMeta(currentMovie);
        renderRelatedMovies(currentMovie);
    } catch (err) {
        // Ignore aborts (e.g., modal closed or another movie opened).
        if (err && err.name === 'AbortError') return;
        // Re-render with the optimistic payload so we don't leave loading text.
        renderStory(currentMovie);
    }
}

function loadWhereToWatch(movie) {
    if (!movieDetailsWhereToWatchSection) return;
    const title = safeTrim(movie.movie_title || movie.title);
    if (!title) {
        setHidden(movieDetailsWhereToWatchSection, true);
        return;
    }
    setHidden(movieDetailsWhereToWatchSection, false);
    renderWhereToWatchLoading();
    const payload = {
        title: title,
        year: movie.year != null ? movie.year : undefined,
        pageUrl: safeTrim(movie.page_url || movie.pageUrl),
        pageId: movie.pageId != null ? String(movie.pageId).trim() : undefined,
        tmdbId: movie.tmdbId || movie.tmdb_id,
        mediaType: movie.mediaType || movie.media_type,
        country: movie.country || movie.production_country
    };
    fetchWhereToWatch(payload, function (err, data) {
        if (err) {
            renderWhereToWatchError(err && err.message ? String(err.message) : 'Unable to load streaming information.');
            return;
        }
        if (!data) {
            clearWhereToWatch();
            setHidden(movieDetailsWhereToWatchEmpty, false);
            return;
        }
        renderWhereToWatchResults(data);
    });
}

export function openMovieDetails(movie) {
    if (!movieDetailsView || !movie) return;
    if (tmdbDetailsAbortController) {
        try { tmdbDetailsAbortController.abort(); } catch (_) { /* ignore */ }
    }
    tmdbDetailsAbortController = null;

    currentMovie = movie;
    previousScrollTop = chatColumn ? chatColumn.scrollTop : null;

    renderHeader(movie);
    renderHero(movie);
    renderStory(movie);
    renderCredits(movie);
    renderMeta(movie);
    renderRelatedMovies(movie);
    loadWhereToWatch(movie);

    movieDetailsView.classList.remove('hidden');
    movieDetailsView.setAttribute('aria-hidden', 'false');

    // Enrich with TMDB details when available (no blocking UI).
    maybeLoadTmdbDetails(movie).catch(function () { /* ignore; optimistic UI remains */ });
}

export function closeMovieDetails() {
    if (!movieDetailsView) return;
    if (tmdbDetailsAbortController) {
        try { tmdbDetailsAbortController.abort(); } catch (_) { /* ignore */ }
    }
    tmdbDetailsAbortController = null;
    movieDetailsView.classList.add('hidden');
    movieDetailsView.setAttribute('aria-hidden', 'true');
    currentMovie = null;
    clearWhereToWatch();
    if (chatColumn != null && previousScrollTop != null) {
        chatColumn.scrollTop = previousScrollTop;
    }
    previousScrollTop = null;
}

export function initMovieDetails() {
    if (movieDetailsCloseBtn) {
        movieDetailsCloseBtn.addEventListener('click', function () {
            closeMovieDetails();
        });
    }
    const askBtn = document.getElementById('movieDetailsAskBtn');
    if (askBtn && composerInput) {
        askBtn.addEventListener('click', function () {
            if (!currentMovie) return;
            const title = safeTrim(currentMovie.movie_title || currentMovie.title);
            const year = currentMovie.year != null ? String(currentMovie.year) : '';
            const label = year ? (title + ' (' + year + ')') : title;
            const prompt = label ? ('Tell me more about ' + label) : 'Tell me more about this movie';
            composerInput.value = prompt;
            composerInput.focus();
        });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && movieDetailsView && !movieDetailsView.classList.contains('hidden')) {
            closeMovieDetails();
        }
    });
}

