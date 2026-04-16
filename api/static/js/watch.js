(function patchProxyHeadRequests() {
    const PROXY_MARKER = '/proxy/';

    const _fetch = window.fetch.bind(window);
    window.fetch = function (input, init = {}) {
        const url = typeof input === 'string' ? input : input?.url;
        if (
            init.method?.toUpperCase() === 'HEAD' &&
            typeof url === 'string' &&
            url.includes(PROXY_MARKER)
        ) {
            return Promise.resolve(
                new Response(null, {
                    status: 200,
                    headers: {
                        'Content-Type': 'application/x-mpegurl',
                        'Accept-Ranges': 'bytes',
                    },
                })
            );
        }
        return _fetch(input, init);
    };

    const _open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        if (
            method?.toUpperCase() === 'HEAD' &&
            typeof url === 'string' &&
            url.includes(PROXY_MARKER)
        ) {
            method = 'GET';
        }
        return _open.call(this, method, url, ...rest);
    };
})();

// ── Initialize Watch Page with Vidstack Player (Web Component) ──────────
document.addEventListener('DOMContentLoaded', () => {
    const player = document.querySelector('#vidstackPlayer');
    const container = document.getElementById('videoContainer');

    if (!player || !container) {
        console.error('[Player] Vidstack player element or container not found');
        return;
    }

    console.log('[Player] Initializing Vidstack web component, WATCH_CONFIG:', window.WATCH_CONFIG);

    // Store reference globally
    window.player = player;

    // Wait for the custom element to be defined, then set up
    function onPlayerReady() {
        console.log('[Player] Vidstack can-play fired');
        setupSkipButtons();
        setupResumeAndTracking(player);
    }

    player.addEventListener('can-play', onPlayerReady, { once: true });

    // Handle errors
    player.addEventListener('error', (e) => {
        console.error('[Player] Vidstack error:', e.detail);
    });
});

// ── Abort controller to clean up listeners on re-init ──────────
let _playerAbort = null;

function setupSkipButtons() {
    const player = window.player;
    if (!player) return;

    // Cancel all previous time-update/skip listeners
    if (_playerAbort) _playerAbort.abort();
    _playerAbort = new AbortController();
    const signal = _playerAbort.signal;

    const intro = window.WATCH_CONFIG?.intro;
    const outro = window.WATCH_CONFIG?.outro;
    const autoSkip = localStorage.getItem('yume_skip_intro') === 'true';

    console.log('[Skip] Setup, intro:', intro, 'outro:', outro, 'autoSkip:', autoSkip);

    // Remove old skip buttons
    document.getElementById('skipIntroBtn')?.remove();
    document.getElementById('skipOutroBtn')?.remove();

    const wrapper = document.getElementById('video-wrapper') || document.getElementById('videoContainer');

    if (intro && wrapper) {
        const btn = document.createElement('button');
        btn.id = 'skipIntroBtn';
        btn.className = 'skip-btn';
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg> Skip Opening`;
        btn.addEventListener('click', () => {
            if (intro.end != null) {
                player.currentTime = intro.end;
                btn.classList.remove('show');
            }
        });
        wrapper.appendChild(btn);
    }

    if (outro && wrapper) {
        const btn = document.createElement('button');
        btn.id = 'skipOutroBtn';
        btn.className = 'skip-btn';
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg> Skip Ending`;
        btn.addEventListener('click', () => {
            const targetTime = outro.end || (player.duration - 10);
            player.currentTime = targetTime;
            btn.classList.remove('show');
        });
        wrapper.appendChild(btn);
    }

    let introSkipped = false;
    let outroSkipped = false;

    player.addEventListener('time-update', (e) => {
        const cur = e.detail.currentTime;
        const dur = player.duration || 1;

        const introBtn = document.getElementById('skipIntroBtn');
        if (intro && intro.start != null && intro.end != null) {
            introBtn?.classList.toggle('show', cur >= intro.start && cur <= intro.end);
        }

        const outroBtn = document.getElementById('skipOutroBtn');
        if (outro && outro.start != null) {
            const outroEnd = outro.end || dur - 5;
            outroBtn?.classList.toggle('show', cur >= outro.start && cur <= outroEnd);
        }

        if (autoSkip) {
            if (!introSkipped && intro?.start != null && intro?.end != null && cur >= intro.start && cur <= intro.end) {
                introSkipped = true;
                player.currentTime = intro.end;
            }
            if (!outroSkipped && outro?.start != null && cur >= outro.start && cur <= (outro.end || dur - 5)) {
                outroSkipped = true;
                player.currentTime = outro.end || (dur - 1);
            }
        }
    }, { signal });
}

// ── Build chapter markers on the timeline for intro/outro ──────────
function rebuildChaptersTrack() {
    const player = window.player;
    if (!player) return;

    const cfg = window.WATCH_CONFIG;
    if (!cfg) return;

    const intro = cfg.intro;
    const outro = cfg.outro;
    if (!intro && !outro) return;

    const duration = player.duration;
    if (!duration || duration <= 0) {
        // Wait for duration, then retry
        player.addEventListener('duration-change', () => rebuildChaptersTrack(), { once: true });
        return;
    }

    // Remove existing chapter tracks
    try {
        const tracks = player.textTracks.toArray();
        tracks.filter(t => t.kind === 'chapters' && t.label === 'Sections')
              .forEach(t => player.textTracks.remove(t));
    } catch(e) {}

    // VTT timestamp formatter
    function fmtVTT(sec) {
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = Math.floor(sec % 60);
        const ms = Math.floor((sec % 1) * 1000);
        return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(3,'0')}`;
    }

    // Build chapter segments spanning the full duration
    const segments = [];
    let cursor = 0;

    if (intro && intro.start != null && intro.end != null) {
        if (intro.start > cursor) {
            segments.push({ start: cursor, end: intro.start, text: 'Episode' });
        }
        segments.push({ start: intro.start, end: intro.end, text: '\ud83c\udfb5 Opening' });
        cursor = intro.end;
    }

    if (outro && outro.start != null) {
        const outroEnd = outro.end || duration;
        if (outro.start > cursor) {
            segments.push({ start: cursor, end: outro.start, text: 'Episode' });
        }
        segments.push({ start: outro.start, end: outroEnd, text: '\ud83c\udfb5 Ending' });
        cursor = outroEnd;
    }

    if (cursor < duration) {
        segments.push({ start: cursor, end: duration, text: 'Episode' });
    }

    if (segments.length === 0) return;

    // Generate VTT content
    let vtt = 'WEBVTT\n\n';
    segments.forEach((seg, i) => {
        vtt += `${i + 1}\n${fmtVTT(seg.start)} --> ${fmtVTT(seg.end)}\n${seg.text}\n\n`;
    });

    const blob = new Blob([vtt], { type: 'text/vtt' });
    const url = URL.createObjectURL(blob);

    player.textTracks.add({
        src: url,
        kind: 'chapters',
        label: 'Sections',
        language: 'en',
        default: true,
        type: 'vtt'
    });

    console.log('[Chapters] Rebuilt chapter markers — segments:', segments.length);
}
window.rebuildChaptersTrack = rebuildChaptersTrack;

// ── Resume & watched tracking — runs ONCE, never re-registered ──
let _trackingSetup = false;

function setupResumeAndTracking(player) {
    if (_trackingSetup) return;   // ← prevents duplicate listeners
    _trackingSetup = true;

    let resumeApplied = false;

    player.addEventListener('play', () => {
        if (resumeApplied) return;
        resumeApplied = true;

        const pathMatch = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
        if (!pathMatch) return;

        const key = `yumeResume_${pathMatch[1]}_ep${pathMatch[2]}`;
        let savedTime = 0;
        try { savedTime = parseFloat(localStorage.getItem(key)) || 0; } catch(e) {}

        if (savedTime > 10 && player.currentTime < 5) {
            console.log('[AutoResume] Resuming from:', savedTime);
            player.currentTime = savedTime;
        }
    });

    player.addEventListener('time-update', (e) => {
        const cur = e.detail.currentTime;
        if (cur > 10) {
            const pathMatch = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
            if (!pathMatch) return;
            const key = `yumeResume_${pathMatch[1]}_ep${pathMatch[2]}`;
            try { localStorage.setItem(key, String(cur)); } catch(e) {}
        }
    });

    player.addEventListener('time-update', (e) => {
        const dur = player.duration;
        if (dur > 0 && (e.detail.currentTime / dur) >= 0.8) {
            markEpisodeWatched();
        }
    });
}

let watchedMarked = false;
function markEpisodeWatched() {
    if (watchedMarked || !window.WATCH_CONFIG?.isLoggedIn) return;
    watchedMarked = true;

    const animeId = window.WATCH_CONFIG?.animeId;
    const epNum = window.WATCH_CONFIG?.episodeNumber;
    if (!animeId || !epNum) return;

    fetch('/api/watchlist/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            anime_id: animeId,
            action: 'episodes',
            watched_episodes: epNum
        })
    }).then(() => console.log('[Watchlist] Marked watched')).catch(() => {});
}

// ── URL Episode Number Fix ──────────────────────────────────────
(function fixEpisodeFromURL() {
    const match = window.location.pathname.match(/\/ep-(\d+(?:\.\d+)?)/i);
    window._urlEpNum = match ? parseFloat(match[1]) : null;
})();

// ── Watch State for AJAX ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    window._watchState = {
        animeId: window.WATCH_CONFIG?.animeId,
        episodeNumber: window._urlEpNum || window.WATCH_CONFIG?.episodeNumber,
        language: window.WATCH_CONFIG?.language,
        provider: window.WATCH_CONFIG?.provider,
        providers: window.WATCH_CONFIG?.providers
    };
});

// ── Server Switching ────────────────────────────────────────────
function switchProvider(provider) {
    window._watchState.provider = provider;
    fetchAndLoadSources();
}
window.switchProvider = switchProvider;

function switchLanguage(lang) {
    window._watchState.language = lang;
    fetchAndLoadSources();
}

function fetchAndLoadSources() {
    const state = window._watchState;
    console.log('[AJAX] Fetching sources:', state);

    const serverSections = document.getElementById('serverSections');
    if (serverSections) serverSections.classList.add('loading');

    fetch('/api/watch/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            anime_id: state.animeId,
            episode_number: state.episodeNumber,
            language: state.language,
            provider: state.provider
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.error) {
            console.error('[AJAX] Error:', data.error);
            return;
        }

        console.log('[AJAX] Got sources:', data);

        // Update intro/outro
        if (data.intro) window.WATCH_CONFIG.intro = data.intro;
        if (data.outro) window.WATCH_CONFIG.outro = data.outro;

        // Re-create skip buttons with new data
        const oldIntro = document.getElementById('skipIntroBtn');
        const oldOutro = document.getElementById('skipOutroBtn');
        if (oldIntro) oldIntro.remove();
        if (oldOutro) oldOutro.remove();

        if (window.player) {
            setupSkipButtons();
            // Rebuild chapters track with new intro/outro data
            rebuildChaptersTrack();
        }

        // Update video source
        const hlsSources = data.hls_sources || [];
        const embedSources = data.embed_sources || [];
        const videoContainer = document.getElementById('videoContainer');

        if (hlsSources.length > 0) {
            const videoUrl = hlsSources[0].file || hlsSources[0].url;
            const player = window.player;

            if (player && videoUrl) {
                // Vidstack web component: set src with type for HLS
                player.src = {
                    src: videoUrl,
                    type: 'application/x-mpegurl'
                };
            }

            if (videoContainer) videoContainer.style.display = '';

            // Hide embed
            const embedFrame = document.getElementById('embedPlayer');
            if (embedFrame) {
                embedFrame.removeAttribute('src');
                embedFrame.style.display = 'none';
            }
        } else if (embedSources.length > 0) {
            if (videoContainer) videoContainer.style.display = 'none';

            let frame = document.getElementById('embedPlayer');
            if (!frame) {
                frame = document.createElement('iframe');
                frame.id = 'embedPlayer';
                frame.className = 'embed-player-frame';
                frame.allowFullscreen = true;
                frame.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
                frame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-presentation');
                document.getElementById('video-wrapper').insertBefore(frame, document.getElementById('videoContainer'));
            }
            frame.style.cssText = 'width:100%; height:100%; border:none; display:block; position:absolute; top:0; left:0;';
            frame.src = embedSources[0].url;
        }

        if (serverSections) serverSections.classList.remove('loading');

        // Update provider capabilities
        if (data.provider_capabilities) {
            updateProviderPills(data.provider_capabilities);
        }
    });
}

function updateProviderPills(caps) {
    ['hlsServerPills', 'embedServerPills'].forEach(id => {
        const section = document.getElementById(id);
        if (!section) return;

        section.querySelectorAll('.server-pill').forEach(pill => {
            const pName = pill.dataset.provider;
            const hasCaps = id === 'hlsServerPills'
                ? caps[pName]?.hls
                : caps[pName]?.embed;

            if (!hasCaps) {
                pill.classList.add('unavailable');
                pill.style.display = 'none';
            } else {
                pill.classList.remove('unavailable');
                pill.style.display = '';
            }
        });
    });
}

// ── Episode Sidebar ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const viewList = document.getElementById('view-list-btn');
    const viewGrid = document.getElementById('view-grid-btn');
    const list = document.getElementById('episodeList');

    function setView(view) {
        if (list) list.setAttribute('data-view', view);
        localStorage.setItem('episodeView', view);
        viewList?.classList.toggle('active', view === 'list');
        viewGrid?.classList.toggle('active', view === 'grid');
    }

    try {
        setView(localStorage.getItem('episodeView') || 'grid');
    } catch(e) {}

    viewList?.addEventListener('click', () => setView('list'));
    viewGrid?.addEventListener('click', () => setView('grid'));

    // Search
    const search = document.getElementById('episodeSearch');
    if (search && list) {
        search.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            list.querySelectorAll('.episode-sidebar-item').forEach(item => {
                const match = item.dataset.number.includes(term) ||
                             item.textContent.toLowerCase().includes(term);
                item.style.display = match ? '' : 'none';
            });
        });
    }
});

// ── Server Pill Clicks ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const sections = document.getElementById('serverSections');
    if (!sections) return;

    sections.addEventListener('click', (e) => {
        const pill = e.target.closest('.server-pill');
        if (!pill || pill.disabled || pill.classList.contains('unavailable')) return;

        const streamType = pill.dataset.streamType;
        const provider = pill.dataset.provider;
        if (!streamType || !provider) return;

        window._watchState._desiredStreamType = streamType;
        window._watchState.provider = provider;

        try {
            localStorage.setItem('yumePreferredServer', provider);
            document.cookie = `preferred_server=${provider}; path=/; max-age=31536000`;
        } catch(e) {}

        // Update active states
        sections.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');

        fetchAndLoadSources();
    });
});
