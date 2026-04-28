/**
 * Music (OP/ED Themes) – Anime Info Page
 * Fetches opening/ending theme data from AnimeThemes API via backend proxy
 * and renders playable theme cards with video support.
 */
(() => {
    let loaded = false;
    let currentlyPlaying = null; // track the currently playing video element

    // ── Fetch themes when Music tab becomes active ─────────────────────────
    function initMusicTab() {
        const musicTab = document.getElementById('tab-music');
        if (!musicTab) return;

        // Observe tab activation
        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.attributeName === 'class' && musicTab.classList.contains('active') && !loaded) {
                    loaded = true;
                    fetchThemes();
                }
            }
        });
        observer.observe(musicTab, { attributes: true });

        // Also check if it's already active (e.g. deep-linked)
        if (musicTab.classList.contains('active') && !loaded) {
            loaded = true;
            fetchThemes();
        }
    }

    async function fetchThemes() {
        const musicTab = document.getElementById('tab-music');
        const title = musicTab?.dataset.animeTitle;
        if (!title) {
            showEmpty();
            return;
        }

        try {
            const resp = await fetch(`/api/anime-themes?title=${encodeURIComponent(title)}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            renderThemes(data);
        } catch (e) {
            console.error('Failed to fetch anime themes:', e);
            showEmpty();
        }
    }

    function showEmpty() {
        const loading = document.getElementById('music-loading');
        const empty = document.getElementById('music-empty');
        if (loading) loading.style.display = 'none';
        if (empty) empty.style.display = 'flex';
    }

    function renderThemes(data) {
        const loading = document.getElementById('music-loading');
        const themes = document.getElementById('music-themes');
        const empty = document.getElementById('music-empty');

        if (loading) loading.style.display = 'none';

        const openings = data.openings || [];
        const endings = data.endings || [];

        if (openings.length === 0 && endings.length === 0) {
            showEmpty();
            return;
        }

        if (themes) themes.style.display = 'block';

        // Render openings
        if (openings.length > 0) {
            const opGroup = document.getElementById('music-openings');
            const opList = document.getElementById('music-openings-list');
            if (opGroup) opGroup.style.display = 'block';
            if (opList) opList.innerHTML = openings.map((t, i) => buildThemeCard(t, 'op', i)).join('');
        }

        // Render endings
        if (endings.length > 0) {
            const edGroup = document.getElementById('music-endings');
            const edList = document.getElementById('music-endings-list');
            if (edGroup) edGroup.style.display = 'block';
            if (edList) edList.innerHTML = endings.map((t, i) => buildThemeCard(t, 'ed', i)).join('');
        }

        // Attach event listeners for play buttons
        attachVideoListeners();
    }

    function buildThemeCard(theme, type, index) {
        const artists = (theme.artists || [])
            .map(a => {
                let display = a.name || '';
                if (a.as) display += ` <span class="music-artist-as">(as ${a.as})</span>`;
                return display;
            })
            .join(', ');

        const hasVideo = theme.videos && theme.videos.length > 0;
        const video = hasVideo ? theme.videos[0] : null;
        const videoUrl = video ? video.url : '';
        const videoTags = video ? (video.tags || '') : '';

        const sequenceLabel = `${type.toUpperCase()}${theme.sequence || (index + 1)}`;
        const episodesStr = theme.episodes ? `<span class="music-episodes">Eps: ${theme.episodes}</span>` : '';

        return `
        <div class="music-card" data-video-url="${videoUrl}">
            <div class="music-card-left">
                <div class="music-sequence-badge ${type}">${sequenceLabel}</div>
                <div class="music-card-info">
                    <div class="music-song-title">${escapeHtml(theme.title || 'Unknown')}</div>
                    <div class="music-artist">${artists || 'Unknown Artist'}</div>
                    ${episodesStr}
                </div>
            </div>
            <div class="music-card-right">
                ${videoTags ? `<span class="music-video-tag">${escapeHtml(videoTags)}</span>` : ''}
                ${hasVideo ? `
                <button class="music-play-btn" data-video-url="${videoUrl}" title="Play theme video">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                        <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                </button>` : ''}
            </div>
        </div>
        ${hasVideo ? `
        <div class="music-video-container" id="video-${type}-${index}" style="display: none;">
            <video class="music-video-player" preload="none" controls>
                <source src="${videoUrl}" type="video/webm">
                Your browser does not support WebM video.
            </video>
        </div>` : ''}`;
    }

    function attachVideoListeners() {
        document.querySelectorAll('.music-play-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const card = btn.closest('.music-card');
                const videoContainer = card?.nextElementSibling;

                if (!videoContainer || !videoContainer.classList.contains('music-video-container')) return;

                const video = videoContainer.querySelector('video');
                const isVisible = videoContainer.style.display !== 'none';

                if (isVisible) {
                    // Close this video
                    video.pause();
                    videoContainer.style.display = 'none';
                    card.classList.remove('playing');
                    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>`;
                    currentlyPlaying = null;
                } else {
                    // Stop any currently playing video
                    if (currentlyPlaying && currentlyPlaying !== video) {
                        currentlyPlaying.pause();
                        const prevContainer = currentlyPlaying.closest('.music-video-container');
                        if (prevContainer) {
                            prevContainer.style.display = 'none';
                            const prevCard = prevContainer.previousElementSibling;
                            if (prevCard) {
                                prevCard.classList.remove('playing');
                                const prevBtn = prevCard.querySelector('.music-play-btn');
                                if (prevBtn) {
                                    prevBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>`;
                                }
                            }
                        }
                    }

                    // Open and play this video
                    videoContainer.style.display = 'block';
                    card.classList.add('playing');
                    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
                    video.play().catch(() => { /* autoplay may be blocked */ });
                    currentlyPlaying = video;

                    // Smooth scroll to video
                    videoContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        });

        // Also allow clicking the entire card to toggle video
        document.querySelectorAll('.music-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't trigger if the play button was clicked (it handles itself)
                if (e.target.closest('.music-play-btn')) return;
                const btn = card.querySelector('.music-play-btn');
                if (btn) btn.click();
            });
        });
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Init ───────────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', initMusicTab);
})();
