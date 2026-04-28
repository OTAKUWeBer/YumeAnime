/**
 * Music (OP/ED Themes) – Anime Info Page
 * Fetches opening/ending theme data from AnimeThemes API via backend proxy
 * and renders playable theme cards with video support.
 */
(() => {
    let loaded = false;
    let currentlyPlaying = null;

    // ── Fetch themes when Music tab becomes active ─────────────────────────
    function initMusicTab() {
        const musicTab = document.getElementById('tab-music');
        if (!musicTab) return;

        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.attributeName === 'class' && musicTab.classList.contains('active') && !loaded) {
                    loaded = true;
                    fetchThemes();
                }
            }
        });
        observer.observe(musicTab, { attributes: true });

        if (musicTab.classList.contains('active') && !loaded) {
            loaded = true;
            fetchThemes();
        }
    }

    async function fetchThemes() {
        const musicTab = document.getElementById('tab-music');
        const title = musicTab?.dataset.animeTitle;
        if (!title) { showEmpty(); return; }

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

        if (loading) loading.style.display = 'none';

        const openings = data.openings || [];
        const endings = data.endings || [];

        if (openings.length === 0 && endings.length === 0) {
            showEmpty();
            return;
        }

        if (themes) themes.style.display = 'block';

        // Get cover image: prefer AnimeThemes image, fallback to page poster
        let coverImage = data.cover_image || '';
        if (!coverImage) {
            const posterEl = document.querySelector('.anime-poster img');
            if (posterEl) coverImage = posterEl.src || '';
        }

        // Add cover banner at top of themes section
        if (coverImage) {
            const themesEl = document.getElementById('music-themes');
            const existingBanner = themesEl?.querySelector('.music-cover-banner');
            if (!existingBanner && themesEl) {
                const banner = document.createElement('div');
                banner.className = 'music-cover-banner';
                banner.innerHTML = `
                    <img src="${coverImage}" alt="" class="music-cover-banner-img">
                    <div class="music-cover-banner-overlay"></div>
                    <div class="music-cover-banner-info">
                        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9 18V5l12-2v13" />
                            <circle cx="6" cy="18" r="3" />
                            <circle cx="18" cy="16" r="3" />
                        </svg>
                        <div>
                            <div class="music-cover-banner-title">Theme Songs</div>
                            <div class="music-cover-banner-count">${openings.length} Opening${openings.length !== 1 ? 's' : ''} · ${endings.length} Ending${endings.length !== 1 ? 's' : ''}</div>
                        </div>
                    </div>
                `;
                themesEl.prepend(banner);
            }
        }

        // Render openings
        if (openings.length > 0) {
            const opGroup = document.getElementById('music-openings');
            const opList = document.getElementById('music-openings-list');
            if (opGroup) opGroup.style.display = 'block';
            if (opList) opList.innerHTML = openings.map((t, i) => buildThemeCard(t, 'op', i, coverImage)).join('');
        }

        // Render endings
        if (endings.length > 0) {
            const edGroup = document.getElementById('music-endings');
            const edList = document.getElementById('music-endings-list');
            if (edGroup) edGroup.style.display = 'block';
            if (edList) edList.innerHTML = endings.map((t, i) => buildThemeCard(t, 'ed', i, coverImage)).join('');
        }

        // Attach event listeners for play buttons
        attachVideoListeners();
    }

    function buildThemeCard(theme, type, index, coverImage) {
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

        const sequenceNum = theme.sequence || (index + 1);
        const episodesStr = theme.episodes ? `<span class="music-episodes">Eps: ${theme.episodes}</span>` : '';

        // Badge with cover image + corner number
        let badgeInner;
        if (coverImage) {
            badgeInner = `
                <img src="${coverImage}" alt="" class="music-badge-img" loading="lazy">
                <span class="music-badge-num ${type}">${sequenceNum}</span>`;
        } else {
            badgeInner = `<span class="music-badge-num no-img ${type}">${sequenceNum}</span>`;
        }

        return `
        <div class="music-card" data-video-url="${videoUrl}">
            <div class="music-card-left">
                <div class="music-sequence-badge ${coverImage ? 'has-image' : ''} ${type}">
                    ${badgeInner}
                </div>
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
                    video.pause();
                    videoContainer.style.display = 'none';
                    card.classList.remove('playing');
                    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3" /></svg>`;
                    currentlyPlaying = null;
                } else {
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

                    videoContainer.style.display = 'block';
                    card.classList.add('playing');
                    btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>`;
                    video.play().catch(() => {});
                    currentlyPlaying = video;
                    videoContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        });

        document.querySelectorAll('.music-card').forEach(card => {
            card.addEventListener('click', (e) => {
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

    document.addEventListener('DOMContentLoaded', initMusicTab);
})();
