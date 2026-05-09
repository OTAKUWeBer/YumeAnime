(function patchProxyHeadRequests() {
    const _fetch = window.fetch.bind(window);
    window.fetch = function (input, init = {}) {
        const url = typeof input === 'string' ? input : input?.url;
        if (
            init.method?.toUpperCase() === 'HEAD' &&
            typeof url === 'string' &&
            (url.includes('/proxy/') || url.includes('/p/'))
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
            (url.includes('/proxy/') || url.includes('/p/'))
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
        return;
    }

    // Store reference globally
    window.player = player;

    // Immediately set up listeners, no need to wait for can-play
    // because time-update handles duration dynamically
    setupSkipButtons();
    setupResumeAndTracking(player);

    function onPlayerReady() {
        console.log('[Player] Vidstack can-play fired');
    }

    player.addEventListener('can-play', onPlayerReady, { once: true });

    // Handle errors
    player.addEventListener('error', (e) => {
        console.error('Player error:', e.detail);
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

    // Remove old skip buttons
    document.getElementById('skipIntroBtn')?.remove();
    document.getElementById('skipOutroBtn')?.remove();

    const wrapper = document.getElementById('video-wrapper') || document.getElementById('videoContainer');

    if (intro && wrapper) {
        const btn = document.createElement('button');
        btn.id = 'skipIntroBtn';
        btn.className = 'skip-btn';
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg> Skip Intro`;
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
        btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg> Skip Outro`;
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
    } catch (e) { }

    // VTT timestamp formatter
    function fmtVTT(sec) {
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = Math.floor(sec % 60);
        const ms = Math.floor((sec % 1) * 1000);
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
    }

    // Build chapter segments spanning the full duration
    const segments = [];
    let cursor = 0;

    if (intro && intro.start != null && intro.end != null) {
        if (intro.start > cursor) {
            segments.push({ start: cursor, end: intro.start, text: 'Episode' });
        }
        segments.push({ start: intro.start, end: intro.end, text: '\ud83c\udfb5 Intro' });
        cursor = intro.end;
    }

    if (outro && outro.start != null) {
        const outroEnd = outro.end || duration;
        if (outro.start > cursor) {
            segments.push({ start: cursor, end: outro.start, text: 'Episode' });
        }
        segments.push({ start: outro.start, end: outroEnd, text: '\ud83c\udfb5 Outro' });
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
}
window.rebuildChaptersTrack = rebuildChaptersTrack;

// ── Resume & watched tracking — runs ONCE, never re-registered ──
let _trackingSetup = false;

function setupResumeAndTracking(player) {
    if (_trackingSetup) return;   // ← prevents duplicate listeners
    _trackingSetup = true;

    let resumeApplied = false;
    let lastHistorySave = 0; // throttle history saves

    // ── Save watch history entry to localStorage ──
    function saveWatchHistory(currentTime, duration) {
        const cfg = window.WATCH_CONFIG;
        if (!cfg || !cfg.animeId) return;

        const epNum = cfg.episodeNumber;
        const key = `yumeHistory_${cfg.animeId}_ep${epNum}`;
        const progress = duration > 0 ? currentTime / duration : 0;

        const entry = {
            animeId: cfg.animeId,
            epNum: epNum,
            animeName: cfg.animeName || '',
            poster: cfg.poster || '',
            episodeTitle: cfg.episodeTitle || '',
            timestamp: currentTime,
            duration: duration,
            completed: progress >= 0.9,
            watchedAt: Date.now()
        };

        try {
            localStorage.setItem(key, JSON.stringify(entry));
        } catch (e) { }
    }

    player.addEventListener('play', () => {
        if (resumeApplied) return;
        resumeApplied = true;

        const pathMatch = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
        if (!pathMatch) return;

        const key = `yumeResume_${pathMatch[1]}_ep${pathMatch[2]}`;
        let savedTime = 0;
        try { savedTime = parseFloat(localStorage.getItem(key)) || 0; } catch (e) { }

        if (savedTime > 10 && player.currentTime < 5) {
            player.currentTime = savedTime;
        }

        // Save initial history entry on first play
        saveWatchHistory(player.currentTime, player.duration || 0);
    });

    player.addEventListener('time-update', (e) => {
        const cur = e.detail.currentTime;
        if (cur > 10) {
            const pathMatch = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
            if (!pathMatch) return;
            const key = `yumeResume_${pathMatch[1]}_ep${pathMatch[2]}`;
            try { localStorage.setItem(key, String(cur)); } catch (e) { }
        }

        // Save watch history every 15 seconds to avoid excessive writes
        const now = Date.now();
        if (cur > 5 && now - lastHistorySave > 15000) {
            lastHistorySave = now;
            saveWatchHistory(cur, player.duration || 0);
        }
    });

    player.addEventListener('time-update', (e) => {
        const dur = player.duration;
        if (dur > 0 && (e.detail.currentTime / dur) >= 0.8) {
            markEpisodeWatched();
        }
    });

    // Save history when user leaves the page
    window.addEventListener('beforeunload', () => {
        if (player && player.currentTime > 5) {
            saveWatchHistory(player.currentTime, player.duration || 0);
        }
    });
}

let watchedMarked = false;
function markEpisodeWatched() {
    if (watchedMarked || !window.WATCH_CONFIG?.isLoggedIn) return;

    // Use anilistId (numeric) for the AniList API, fall back to animeId
    const anilistId = window.WATCH_CONFIG?.anilistId;
    const animeId = anilistId || window.WATCH_CONFIG?.animeId;
    const epNum = window.WATCH_CONFIG?.episodeNumber;
    const malId = window.WATCH_CONFIG?.malId;
    if (!animeId || !epNum) return;

    watchedMarked = true;

    const payload = {
        anime_id: animeId,
        action: 'episodes',
        watched_episodes: epNum
    };
    // Include malId for direct MAL sync if available
    if (malId) {
        payload.mal_id = malId;
        payload.sync_mal = true;
    }

    function doUpdate(attempt) {
        fetch('/api/watchlist/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            // Keep the request alive even if the page is being closed (mobile)
            keepalive: true
        })
            .then(r => {
                if (!r.ok) {
                    throw new Error(`HTTP ${r.status}`);
                }
                return r.json();
            })
            .then(data => {
                if (data.success) {
                } else {
                    // Retry once on server-side failure
                    if (attempt < 2) {
                        setTimeout(() => doUpdate(attempt + 1), 2000);
                    }
                }
            })
            .catch(err => {
                // Retry on network error (common on mobile)
                if (attempt < 2) {
                    setTimeout(() => doUpdate(attempt + 1), 3000);
                } else {
                    // Last resort: reset flag so it can try again on next time-update
                    watchedMarked = false;
                }
            });
    }

    doUpdate(1);
}

// Reset watchedMarked when episode changes (AJAX navigation)
function resetWatchedFlag() {
    watchedMarked = false;
}

// ── URL Episode Number Fix ──────────────────────────────────────
(function fixEpisodeFromURL() {
    const match = window.location.pathname.match(/\/ep-(\d+(?:\.\d+)?)/i);
    window._urlEpNum = match ? parseFloat(match[1]) : null;
})();

// ── Provider Fallback System ───────────────────────────────────
const _PROVIDER_PRIORITY = ['arc', 'jet', 'kiwi', 'zoro', 'bee', 'wco'];
let _failedProviders = new Set(); // stores "provider" (fully failed) or "provider::hls" / "provider::embed"
let _isFallbackInProgress = false;

function resetFailedProviders() {
    _failedProviders.clear();
    _isFallbackInProgress = false;
}

// Check if a provider is fully failed (no sources at all from API)
function isProviderFullyFailed(provider) {
    return _failedProviders.has(provider) ||
        (_failedProviders.has(`${provider}::hls`) && _failedProviders.has(`${provider}::embed`));
}

// Check if a provider is failed for a specific stream type
function isProviderFailedForType(provider, streamType) {
    if (_failedProviders.has(provider)) return true; // fully failed
    if (streamType && _failedProviders.has(`${provider}::${streamType}`)) return true;
    return false;
}

function getNextAvailableProvider(currentProvider) {
    const providers = window._watchState?.providers || _PROVIDER_PRIORITY;
    const desiredType = window._watchState?._desiredStreamType;
    const currentIdx = providers.indexOf(currentProvider);
    for (let i = 1; i < providers.length; i++) {
        const idx = (currentIdx + i) % providers.length;
        const candidate = providers[idx];
        if (isProviderFullyFailed(candidate)) continue;
        // If user wants a specific type, skip providers failed for that type
        if (desiredType && isProviderFailedForType(candidate, desiredType)) continue;
        return candidate;
    }
    return null;
}

function markProviderFailed(provider, streamType) {
    if (streamType) {
        _failedProviders.add(`${provider}::${streamType}`);
    } else {
        // No stream type = API returned nothing at all — fully failed
        _failedProviders.add(provider);
    }
    updateServerPillAvailability();
}

function updateServerPillAvailability() {
    document.querySelectorAll('.server-pill').forEach(pill => {
        const provider = pill.dataset.provider;
        const streamType = pill.dataset.streamType;
        // Only mark a pill unavailable if that specific type failed, or provider fully failed
        if (isProviderFullyFailed(provider) || isProviderFailedForType(provider, streamType)) {
            pill.classList.add('unavailable');
            pill.title = 'Source unavailable for this episode';
        } else {
            pill.classList.remove('unavailable');
            pill.title = '';
        }
    });
}

function showFallbackToast(fromProvider, toProvider) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.style.cssText = 'pointer-events:auto;display:flex;align-items:center;gap:10px;padding:12px 18px;background:rgba(30,30,40,0.95);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);border-radius:12px;color:#fff;font-size:0.85rem;font-weight:500;box-shadow:0 8px 32px rgba(0,0,0,0.4);transform:translateX(120%);transition:transform 0.35s cubic-bezier(0.2,0.8,0.2,1),opacity 0.3s ease;opacity:0;max-width:360px;';
    toast.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" style="flex-shrink:0"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg><span><strong>${fromProvider}</strong> unavailable — switching to <strong>${toProvider}</strong></span>`;
    container.appendChild(toast);
    requestAnimationFrame(() => { toast.style.transform = 'translateX(0)'; toast.style.opacity = '1'; });
    setTimeout(() => {
        toast.style.transform = 'translateX(120%)'; toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400);
    }, 3500);
}

function showNoSourcesMessage() {
    const videoContainer = document.getElementById('videoContainer');
    const embedFrame = document.getElementById('embedPlayer');
    const errorContainer = document.getElementById('errorFallbackContainer');
    if (videoContainer) videoContainer.style.display = 'none';
    if (embedFrame) { embedFrame.removeAttribute('src'); embedFrame.style.display = 'none'; }
    if (errorContainer) {
        errorContainer.style.display = 'flex';
        errorContainer.innerHTML = `<div class="text-center"><div class="no-results-icon">🔌</div><p class="text-muted" style="max-width:300px;margin:8px auto 0">All servers tried — no working sources found for this episode. Try switching language or check back later.</p></div>`;
    }
    const fsBtn = document.getElementById('embedFullscreenBtn');
    if (fsBtn) fsBtn.style.display = 'none';
}

// ── Watch State for AJAX ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    window._watchState = {
        animeId: window.WATCH_CONFIG?.animeId,
        episodeNumber: window._urlEpNum || window.WATCH_CONFIG?.episodeNumber,
        language: window.WATCH_CONFIG?.language,
        provider: window.WATCH_CONFIG?.provider,
        providers: window.WATCH_CONFIG?.providers
    };

    // ── HLS Player Error Handler — auto-fallback on playback failure ──
    const player = document.querySelector('#vidstackPlayer');
    if (player) {
        player.addEventListener('error', (e) => {
            console.error('[Player] Playback error:', e.detail);
            const currentProvider = window._watchState?.provider;
            if (!currentProvider || _isFallbackInProgress) return;
            markProviderFailed(currentProvider, 'hls');

            // Set desired type BEFORE lookup so getNextAvailableProvider
            // knows to skip providers whose HLS already failed
            window._watchState._desiredStreamType = 'hls';
            const next = getNextAvailableProvider(currentProvider);
            if (next) {
                // Try next provider's HLS
                showFallbackToast(currentProvider, next);
                window._watchState.provider = next;
                _isFallbackInProgress = true;
                fetchAndLoadSources(true);
            } else {
                // All HLS exhausted — try embed on the first available provider
                const providers = window._watchState?.providers || _PROVIDER_PRIORITY;
                const embedProvider = providers.find(p => !isProviderFailedForType(p, 'embed'));
                if (embedProvider) {
                    showFallbackToast('All HLS servers', embedProvider + ' (embed)');
                    window._watchState.provider = embedProvider;
                    window._watchState._desiredStreamType = 'embed';
                    _isFallbackInProgress = true;
                    fetchAndLoadSources(true);
                } else {
                    showNoSourcesMessage();
                }
            }
        });
    }
});

// ── Server Switching ────────────────────────────────────────────
function switchProvider(provider) {
    window._watchState.provider = provider;
    // User explicit switch — clear failed tracking for a fresh attempt
    _failedProviders.delete(provider);
    _isFallbackInProgress = false;
    fetchAndLoadSources();
}
window.switchProvider = switchProvider;

function switchLanguage(lang) {
    window._watchState.language = lang;
    // Language switch resets provider availability
    resetFailedProviders();

    document.querySelectorAll('.lang-btn, .language-btn, [data-lang]').forEach(btn => {
        const btnLang = btn.dataset.lang || btn.textContent.trim().toLowerCase();
        btn.classList.toggle('active', btnLang === lang.toLowerCase());
    });

    // Reset unavailable pill states
    document.querySelectorAll('.server-pill.unavailable').forEach(p => p.classList.remove('unavailable'));

    fetchAndLoadSources();
}

// ── Apply video sources to the player ──────────────────────────
function applyVideoSources(data) {
    const hlsSources = data.hls_sources || [];
    const embedSources = data.embed_sources || [];
    const videoContainer = document.getElementById('videoContainer');
    const desired = window._watchState._desiredStreamType;

    // Decide which source type to use
    let useEmbed = false;
    if (desired === 'hls') {
        useEmbed = false;
    } else if (desired === 'embed' && embedSources.length > 0) {
        useEmbed = true;
    } else if (hlsSources.length > 0) {
        useEmbed = false;
    } else if (embedSources.length > 0) {
        useEmbed = true;
    }

    const errorContainer = document.getElementById('errorFallbackContainer');

    if (!useEmbed && hlsSources.length > 0) {
        // ── HLS playback ──
        const videoUrl = hlsSources[0].file || hlsSources[0].url;
        const player = window.player;

        if (player && videoUrl) {
            player.src = { src: videoUrl, type: 'application/x-mpegurl' };
        }

        if (videoContainer) videoContainer.style.display = '';
        if (errorContainer) errorContainer.style.display = 'none';

        const embedFrame = document.getElementById('embedPlayer');
        if (embedFrame) { embedFrame.removeAttribute('src'); embedFrame.style.display = 'none'; }

        const fsBtn = document.getElementById('embedFullscreenBtn');
        if (fsBtn) fsBtn.style.display = 'none';

    } else if (useEmbed && embedSources.length > 0) {
        // ── Embed playback ──
        if (videoContainer) videoContainer.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'none';

        // Stop HLS player if running
        const player = window.player;
        if (player) { try { player.src = ''; } catch (_) { } }

        let frame = document.getElementById('embedPlayer');
        if (!frame) {
            frame = document.createElement('iframe');
            frame.id = 'embedPlayer';
            frame.className = 'embed-player-frame';
            frame.allowFullscreen = true;
            frame.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
            frame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-presentation');
            const wrapper = document.getElementById('video-wrapper');
            if (wrapper) wrapper.insertBefore(frame, videoContainer);
        }
        frame.style.cssText = 'width:100%;height:100%;border:none;display:block;position:absolute;top:0;left:0;';
        frame.src = embedSources[0].url;

        ensureEmbedFullscreenBtn();
        const fsBtn = document.getElementById('embedFullscreenBtn');
        if (fsBtn) fsBtn.style.display = '';

    } else {
        // ── No sources at all for this path ──
        // This shouldn't normally be reached (fallback handles it), but just in case
        if (videoContainer) videoContainer.style.display = 'none';
        const embedFrame = document.getElementById('embedPlayer');
        if (embedFrame) { embedFrame.removeAttribute('src'); embedFrame.style.display = 'none'; }
        const fsBtn = document.getElementById('embedFullscreenBtn');
        if (fsBtn) fsBtn.style.display = 'none';
        if (errorContainer) errorContainer.style.display = 'flex';
    }
}

// ── Core: Fetch and load sources with auto-fallback ────────────
function fetchAndLoadSources(isAutoFallback) {
    const state = window._watchState;
    const currentProvider = state.provider;

    const serverSections = document.getElementById('serverSections');
    if (serverSections) serverSections.classList.add('loading');

    fetch('/api/watch/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            anime_id: state.animeId,
            episode_number: state.episodeNumber,
            language: state.language,
            provider: currentProvider
        })
    })
        .then(res => res.json())
        .then(data => {
            const hlsSources = data.hls_sources || [];
            const embedSources = data.embed_sources || [];
            const hasSources = hlsSources.length > 0 || embedSources.length > 0;

            if (data.error || !hasSources) {
                markProviderFailed(currentProvider);

                const next = getNextAvailableProvider(currentProvider);
                if (next) {
                    showFallbackToast(currentProvider, next);
                    state.provider = next;
                    _isFallbackInProgress = true;
                    fetchAndLoadSources(true);
                    return;
                }

                // All providers exhausted
                _isFallbackInProgress = false;
                showNoSourcesMessage();
                if (serverSections) serverSections.classList.remove('loading');
                return;
            }

            // ── Success — apply sources ──
            _isFallbackInProgress = false;

            // Update intro/outro
            if (data.intro !== undefined) window.WATCH_CONFIG.intro = data.intro;
            if (data.outro !== undefined) window.WATCH_CONFIG.outro = data.outro;

            resetWatchedFlag();

            // Re-create skip buttons
            document.getElementById('skipIntroBtn')?.remove();
            document.getElementById('skipOutroBtn')?.remove();
            if (window.player) {
                setupSkipButtons();
                rebuildChaptersTrack();
            }

            applyVideoSources(data);

            // Update active pill to reflect what actually loaded
            if (serverSections) {
                serverSections.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));
                const desired = state._desiredStreamType;
                const streamType = desired || data.source_type || (hlsSources.length > 0 ? 'hls' : 'embed');
                const activePill = serverSections.querySelector(
                    `.server-pill[data-provider="${currentProvider}"][data-stream-type="${streamType}"]`
                );
                if (activePill) activePill.classList.add('active');
            }

            delete state._desiredStreamType;
            if (serverSections) serverSections.classList.remove('loading');
        })
        .catch(err => {
            markProviderFailed(currentProvider);

            const next = getNextAvailableProvider(currentProvider);
            if (next) {
                showFallbackToast(currentProvider, next);
                state.provider = next;
                _isFallbackInProgress = true;
                fetchAndLoadSources(true);
                return;
            }

            _isFallbackInProgress = false;
            showNoSourcesMessage();
            if (serverSections) serverSections.classList.remove('loading');
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
    } catch (e) { }

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
        if (!pill || pill.disabled) return;
        if (pill.classList.contains('unavailable')) return;

        const streamType = pill.dataset.streamType;
        const provider = pill.dataset.provider;
        if (!streamType || !provider) return;

        window._watchState._desiredStreamType = streamType;
        window._watchState.provider = provider;
        _isFallbackInProgress = false;

        // User explicit click — clear stream-specific failure so this attempt is fresh
        _failedProviders.delete(`${provider}::${streamType}`);
        _failedProviders.delete(provider);

        try {
            localStorage.setItem('yumePreferredServer', provider);
            document.cookie = `preferred_server=${provider}; path=/; max-age=31536000`;
        } catch (e) { }

        sections.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');

        fetchAndLoadSources();
    });
});

// ── Embed Fullscreen (wrapper-based, bypasses iframe sandbox) ──
function ensureEmbedFullscreenBtn() {
    const wrapper = document.getElementById('video-wrapper');
    if (!wrapper || document.getElementById('embedFullscreenBtn')) return;

    const btn = document.createElement('button');
    btn.id = 'embedFullscreenBtn';
    btn.className = 'embed-fullscreen-btn';
    btn.title = 'Toggle Fullscreen (F)';
    btn.innerHTML = `
        <svg class="embed-fs-enter" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 3 21 3 21 9"></polyline>
            <polyline points="9 21 3 21 3 15"></polyline>
            <line x1="21" y1="3" x2="14" y2="10"></line>
            <line x1="3" y1="21" x2="10" y2="14"></line>
        </svg>
        <svg class="embed-fs-exit" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;">
            <polyline points="4 14 10 14 10 20"></polyline>
            <polyline points="20 10 14 10 14 4"></polyline>
            <line x1="14" y1="10" x2="21" y2="3"></line>
            <line x1="3" y1="21" x2="10" y2="14"></line>
        </svg>`;
    btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleEmbedFullscreen();
    });
    wrapper.appendChild(btn);
}
window.ensureEmbedFullscreenBtn = ensureEmbedFullscreenBtn;

function isEmbedVisible() {
    const frame = document.getElementById('embedPlayer');
    return frame && frame.style.display !== 'none' && frame.offsetParent !== null;
}

function toggleEmbedFullscreen() {
    const wrapper = document.getElementById('video-wrapper');
    if (!wrapper) return;

    const fsEl = document.fullscreenElement || document.webkitFullscreenElement || null;

    if (fsEl) {
        // Currently in fullscreen — exit
        if (document.exitFullscreen) {
            document.exitFullscreen().catch(() => { });
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        }
    } else {
        // Not in fullscreen — enter
        if (wrapper.requestFullscreen) {
            wrapper.requestFullscreen().catch(() => { });
        } else if (wrapper.webkitRequestFullscreen) {
            wrapper.webkitRequestFullscreen();
        }
    }
}

// Swap fullscreen icons on state change
document.addEventListener('fullscreenchange', updateEmbedFsIcons);
document.addEventListener('webkitfullscreenchange', updateEmbedFsIcons);

function updateEmbedFsIcons() {
    const fsEl = document.fullscreenElement || document.webkitFullscreenElement || null;
    const isFs = !!fsEl;
    // Use class-based selectors (works for both template and JS-created buttons)
    document.querySelectorAll('.embed-fs-enter').forEach(el => el.style.display = isFs ? 'none' : '');
    document.querySelectorAll('.embed-fs-exit').forEach(el => el.style.display = isFs ? '' : 'none');
}

// "F" key shortcut + double-click for embed fullscreen
document.addEventListener('DOMContentLoaded', () => {
    const wrapper = document.getElementById('video-wrapper');
    if (!wrapper) return;

    // Double-click on wrapper to toggle fullscreen
    wrapper.addEventListener('dblclick', (e) => {
        if (e.target === wrapper || e.target.closest('.embed-fullscreen-btn')) {
            toggleEmbedFullscreen();
        }
    });

    // "F" key to toggle fullscreen when embed is visible
    document.addEventListener('keydown', (e) => {
        // Don't trigger if typing in an input
        const tag = document.activeElement?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        if (document.activeElement?.isContentEditable) return;

        if (e.key === 'f' || e.key === 'F') {
            if (isEmbedVisible()) {
                e.preventDefault();
                toggleEmbedFullscreen();
            }
        }
    });
});

// ── Next Episode Countdown ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Legacy small countdown
    const countdownEl = document.getElementById('countdown-text');
    const container = document.getElementById('watch-countdown');
    let legacyTimestamp = null;
    if (container) {
        legacyTimestamp = parseInt(container.getAttribute('data-timestamp'), 10);
    }

    // New large countdown (Episodes Unavailable UI)
    const euContainer = document.getElementById('eu-countdown-wrapper');
    const euDays = document.getElementById('eu-days');
    const euHours = document.getElementById('eu-hours');
    const euMins = document.getElementById('eu-mins');
    const euSecs = document.getElementById('eu-secs');
    let euTimestamp = null;
    if (euContainer) {
        euTimestamp = parseInt(euContainer.getAttribute('data-timestamp'), 10);
    }

    if (!legacyTimestamp && !euTimestamp) return;

    function pad(n) {
        return n < 10 ? '0' + n : n;
    }

    function updateTimer() {
        const now = Date.now();

        // Update legacy countdown
        if (countdownEl && legacyTimestamp) {
            const jsTimestamp = legacyTimestamp > 9999999999 ? legacyTimestamp : legacyTimestamp * 1000;
            const diff = jsTimestamp - now;

            if (diff <= 0) {
                countdownEl.textContent = "Aired";
            } else {
                const d = Math.floor(diff / (1000 * 60 * 60 * 24));
                const h = Math.floor((diff / (1000 * 60 * 60)) % 24);
                const m = Math.floor((diff / 1000 / 60) % 60);
                const s = Math.floor((diff / 1000) % 60);

                let timeStr = '';
                if (d > 0) timeStr += `${d}d `;
                if (h > 0 || d > 0) timeStr += `${h}h `;
                timeStr += `${m}m ${s}s`;
                countdownEl.textContent = timeStr;
            }
        }

        // Update new large countdown
        if (euTimestamp && euDays && euHours && euMins && euSecs) {
            const jsTimestamp = euTimestamp > 9999999999 ? euTimestamp : euTimestamp * 1000;
            const diff = jsTimestamp - now;

            if (diff <= 0) {
                euDays.textContent = "00";
                euHours.textContent = "00";
                euMins.textContent = "00";
                euSecs.textContent = "00";
            } else {
                const d = Math.floor(diff / (1000 * 60 * 60 * 24));
                const h = Math.floor((diff / (1000 * 60 * 60)) % 24);
                const m = Math.floor((diff / 1000 / 60) % 60);
                const s = Math.floor((diff / 1000) % 60);

                euDays.textContent = pad(d);
                euHours.textContent = pad(h);
                euMins.textContent = pad(m);
                euSecs.textContent = pad(s);
            }
        }
    }

    updateTimer();
    setInterval(updateTimer, 1000);
});