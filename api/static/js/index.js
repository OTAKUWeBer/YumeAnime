// Spotlight Carousel — Fade Transition
    const carousel = document.getElementById('spotlight-carousel');
    if (carousel) {
        const slides = carousel.querySelectorAll('.spotlight-slide');
        const prevBtn = document.getElementById('spotlight-prev');
        const nextBtn = document.getElementById('spotlight-next');
        const fractionEl = document.getElementById('spotlight-fraction');
        let currentIndex = 0;
        let autoplayInterval;

        function showSlide(index) {
            if (index < 0) index = slides.length - 1;
            if (index >= slides.length) index = 0;
            
            slides.forEach(slide => slide.classList.remove('active'));
            slides[index].classList.add('active');
            currentIndex = index;

            // Update fraction counter
            if (fractionEl) {
                const currentSpan = fractionEl.querySelector('.spotlight-current');
                if (currentSpan) currentSpan.textContent = currentIndex + 1;
            }
        }

        function nextSlide() { showSlide(currentIndex + 1); }
        function prevSlide() { showSlide(currentIndex - 1); }

        function startAutoplay() {
            stopAutoplay();
            autoplayInterval = setInterval(nextSlide, 6000);
        }

        function stopAutoplay() {
            clearInterval(autoplayInterval);
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', (e) => {
                e.preventDefault();
                nextSlide();
                startAutoplay();
            });
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', (e) => {
                e.preventDefault();
                prevSlide();
                startAutoplay();
            });
        }

        // Touch swipe support
        let touchStartX = 0;
        let touchEndX = 0;

        carousel.addEventListener('touchstart', (e) => {
            touchStartX = e.changedTouches[0].screenX;
            stopAutoplay();
        }, { passive: true });

        carousel.addEventListener('touchend', (e) => {
            touchEndX = e.changedTouches[0].screenX;
            const diff = touchStartX - touchEndX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) nextSlide();
                else prevSlide();
            }
            startAutoplay();
        }, { passive: true });

        // Mouse drag support
        let mouseDown = false;
        let mouseStartX = 0;

        carousel.addEventListener('mousedown', (e) => {
            mouseDown = true;
            mouseStartX = e.screenX;
            stopAutoplay();
        });

        window.addEventListener('mouseup', (e) => {
            if (!mouseDown) return;
            mouseDown = false;
            const diff = mouseStartX - e.screenX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) nextSlide();
                else prevSlide();
            }
            startAutoplay();
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight') { nextSlide(); startAutoplay(); }
            if (e.key === 'ArrowLeft') { prevSlide(); startAutoplay(); }
        });

        // Initialize first slide
        showSlide(0);
        startAutoplay();
    }

// ── Continue Watching & Watch History ────────────────────────────────────
(function initContinueWatching() {
    'use strict';

    // Helper: format seconds to mm:ss or hh:mm:ss
    function formatTime(seconds) {
        if (!seconds || isNaN(seconds) || seconds <= 0) return '00:00';
        seconds = Math.floor(seconds);
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) {
            return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }
        return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }

    // Helper: relative time (e.g., "2 hours ago")
    function timeAgo(timestamp) {
        if (!timestamp) return '';
        const diff = Date.now() - timestamp;
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'Just now';
        if (mins < 60) return mins + 'm ago';
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return hrs + 'h ago';
        const days = Math.floor(hrs / 24);
        if (days < 7) return days + 'd ago';
        return Math.floor(days / 7) + 'w ago';
    }

    // Collect all history entries from localStorage
    function getHistoryEntries() {
        const entries = [];
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith('yumeHistory_')) {
                    try {
                        const data = JSON.parse(localStorage.getItem(key));
                        if (data && data.animeId) {
                            data._key = key;
                            entries.push(data);
                        }
                    } catch (e) { }
                }
            }
        } catch (e) { }
        // Sort by watchedAt (most recent first)
        entries.sort((a, b) => (b.watchedAt || 0) - (a.watchedAt || 0));
        return entries;
    }

    // Deduplicate: keep only the latest entry per anime (latest episode)
    function dedupeByAnime(entries) {
        const seen = new Map();
        const result = [];
        for (const entry of entries) {
            if (!seen.has(entry.animeId)) {
                seen.set(entry.animeId, true);
                result.push(entry);
            }
        }
        return result;
    }

    // Separate into Continue Watching vs Watch History
    function categorize(entries) {
        const continueWatching = [];
        const watchHistory = [];

        for (const entry of entries) {
            const progress = (entry.duration > 0) ? (entry.timestamp / entry.duration) : 0;
            // Continue Watching: has resume timestamp > 10s AND not completed AND < 90% done
            const resumeKey = `yumeResume_${entry.animeId}_ep${entry.epNum}`;
            let hasResume = false;
            try {
                const val = localStorage.getItem(resumeKey);
                hasResume = val && parseFloat(val) > 10;
            } catch (e) { }

            if (!entry.completed && hasResume && progress < 0.9) {
                continueWatching.push(entry);
            } else {
                watchHistory.push(entry);
            }
        }

        return { continueWatching, watchHistory };
    }

    // Create a single card element
    function createCard(entry, showProgress) {
        // The outer shell holds the anchor (image) and the title below it
        const shell = document.createElement('div');
        shell.className = 'cw-card-shell';

        const card = document.createElement('a');
        card.className = 'cw-card-wrapper animPopIn';
        card.href = `/watch/${entry.animeId}/ep-${entry.epNum}`;
        card.title = entry.animeName || entry.animeId;

        const progress = (entry.duration > 0) ? Math.min((entry.timestamp / entry.duration) * 100, 100) : 0;
        const posterSrc = entry.poster || `https://via.placeholder.com/320x180/111/333?text=${encodeURIComponent(entry.animeName || 'Anime')}`;

        // Top info: remove button (and completed badge if any)
        let completedBadgeHTML = '';
        if (entry.completed) {
            completedBadgeHTML = `<span class="cw-card-completed-badge" style="background: rgba(var(--success-rgb, 34, 197, 94), 0.2); color: var(--success); padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; margin-right: auto; display: inline-flex; align-items: center; gap: 4px;">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"></polyline></svg>
                Done
            </span>`;
        }

        // Bottom info: EP badge and duration/progress text
        let durationTextHTML = '';
        if (showProgress && entry.duration > 0) {
            durationTextHTML = `<span class="cw-card-label">${formatTime(entry.timestamp)}<span class="cw-card-duration-total">/${formatTime(entry.duration)}</span></span>`;
        }

        let progressBarHTML = '';
        if (showProgress && entry.duration > 0) {
            progressBarHTML = `
            <div class="cw-card-progress-container">
                <div class="cw-card-progress-track"></div>
                <div class="cw-card-progress-fill" style="width: max(${progress}%, 2%);"></div>
            </div>`;
        }

        card.innerHTML = `
            <img src="${posterSrc}" alt="${entry.animeName || ''}" loading="lazy" class="cw-card-image" onerror="this.src='https://via.placeholder.com/320x180/111/333?text=No+Image'">
            <div class="cw-play-button" aria-label="Play Episode">
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 512 512" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg"><path d="M0 256a256 256 0 1 1 512 0A256 256 0 1 1 0 256zM188.3 147.1c-7.6 4.2-12.3 12.3-12.3 20.9l0 176c0 8.7 4.7 16.7 12.3 20.9s16.8 4.1 24.3-.5l144-88c7.1-4.4 11.5-12.1 11.5-20.5s-4.4-16.1-11.5-20.5l-144-88c-7.4-4.5-16.7-4.7-24.3-.5z"></path></svg>
            </div>
            ${progressBarHTML}
            <div class="cw-card-info-top">
                ${completedBadgeHTML}
                <button type="button" class="cw-card-remove" data-key="${entry._key}" title="Remove from history">
                    <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 352 512" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg"><path d="M242.72 256l100.07-100.07c12.28-12.28 12.28-32.19 0-44.48l-22.24-22.24c-12.28-12.28-32.19-12.28-44.48 0L176 189.28 75.93 89.21c-12.28-12.28-32.19-12.28-44.48 0L9.21 111.45c-12.28 12.28-12.28 32.19 0 44.48L109.28 256 9.21 356.07c-12.28 12.28-12.28 32.19 0 44.48l22.24 22.24c12.28 12.28 32.2 12.28 44.48 0L176 322.72l100.07 100.07c12.28 12.28 32.2 12.28 44.48 0l22.24-22.24c12.28-12.28 12.28-32.19 0-44.48L242.72 256z"></path></svg>
                </button>
            </div>
            <div class="cw-card-info-bottom">
                <span class="cw-card-label">EP ${entry.epNum}</span>
                ${durationTextHTML}
            </div>
        `;

        const titleText = entry.episodeTitle ? `${entry.epNum}. ${entry.episodeTitle}` : (entry.animeName || entry.animeId.replace(/-/g, ' '));
        const subtitleText = entry.episodeTitle ? entry.animeName : `Episode ${entry.epNum}`;

        shell.appendChild(card);
        shell.insertAdjacentHTML('beforeend', `
            <div class="cw-card-title-below">
                <p class="cw-card-title-text">${titleText}</p>
                <p class="cw-card-subtitle-text">${subtitleText}</p>
            </div>
        `);

        // Remove button handler
        const removeBtn = card.querySelector('.cw-card-remove');
        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const key = removeBtn.dataset.key;
                if (key) {
                    try { localStorage.removeItem(key); } catch (err) { }
                    // Also remove the resume key
                    const resumeKey = key.replace('yumeHistory_', 'yumeResume_');
                    try { localStorage.removeItem(resumeKey); } catch (err) { }
                }
                shell.style.transition = 'opacity 0.3s, transform 0.3s';
                shell.style.opacity = '0';
                shell.style.transform = 'scale(0.9)';
                setTimeout(() => {
                    shell.remove();
                    // Re-check if section should hide
                    checkSectionVisibility();
                }, 300);
            });
        }

        return shell;
    }

    function checkSectionVisibility() {
        const cwContainer = document.getElementById('cw-scroll-container');
        const whContainer = document.getElementById('wh-scroll-container');
        const cwSection = document.getElementById('continue-watching-section');
        const whSection = document.getElementById('watch-history-section');

        if (cwSection && cwContainer) {
            cwSection.style.display = cwContainer.children.length > 0 ? '' : 'none';
        }
        if (whSection && whContainer) {
            whSection.style.display = whContainer.children.length > 0 ? '' : 'none';
        }
    }

    // Render everything
    function render() {
        const cwContainer = document.getElementById('cw-scroll-container');
        const whContainer = document.getElementById('wh-scroll-container');
        const cwSection = document.getElementById('continue-watching-section');
        const whSection = document.getElementById('watch-history-section');

        if (!cwContainer || !whContainer) return;

        const allEntries = getHistoryEntries();
        const deduped = dedupeByAnime(allEntries);
        const { continueWatching, watchHistory } = categorize(deduped);

        // Render Continue Watching
        cwContainer.innerHTML = '';
        if (continueWatching.length > 0) {
            for (const entry of continueWatching.slice(0, 20)) {
                cwContainer.appendChild(createCard(entry, true));
            }
            cwSection.style.display = '';
        } else {
            cwSection.style.display = 'none';
        }

        // Render Watch History
        whContainer.innerHTML = '';
        if (watchHistory.length > 0) {
            for (const entry of watchHistory.slice(0, 20)) {
                whContainer.appendChild(createCard(entry, false));
            }
            whSection.style.display = '';
        } else {
            whSection.style.display = 'none';
        }
    }

    // Clear all buttons
    const cwClearBtn = document.getElementById('cw-clear-btn');
    if (cwClearBtn) {
        cwClearBtn.addEventListener('click', () => {
            // Remove all yumeHistory_ and yumeResume_ keys for items in Continue Watching
            const entries = getHistoryEntries();
            const deduped = dedupeByAnime(entries);
            const { continueWatching } = categorize(deduped);
            for (const entry of continueWatching) {
                try {
                    localStorage.removeItem(entry._key);
                    localStorage.removeItem(`yumeResume_${entry.animeId}_ep${entry.epNum}`);
                } catch (e) { }
            }
            render();
        });
    }

    const whClearBtn = document.getElementById('wh-clear-btn');
    if (whClearBtn) {
        whClearBtn.addEventListener('click', () => {
            const entries = getHistoryEntries();
            const deduped = dedupeByAnime(entries);
            const { watchHistory } = categorize(deduped);
            for (const entry of watchHistory) {
                try {
                    localStorage.removeItem(entry._key);
                } catch (e) { }
            }
            render();
        });
    }

    // Initial render
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', render);
    } else {
        render();
    }
})();
