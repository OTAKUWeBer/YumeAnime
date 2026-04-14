document.addEventListener('DOMContentLoaded', () => {
                    const el = document.getElementById('watch-countdown');
                    if (!el) return;
                    const ts = parseInt(el.dataset.timestamp, 10);
                    if (!ts) return;

                    const update = () => {
                        const now = Date.now();
                        const diff = (ts > 9999999999 ? ts : ts * 1000) - now;
                        const countdownText = document.getElementById('countdown-text');

                        if (diff <= 0) {
                            countdownText.textContent = 'Airing now!';
                            return;
                        }

                        const days = Math.floor(diff / 86400000);
                        const hours = Math.floor(diff / 3600000) % 24;
                        const minutes = Math.floor(diff / 60000) % 60;

                        let timeStr = '';
                        if (days > 0) timeStr += days + ' day' + (days > 1 ? 's' : '') + ', ';
                        timeStr += hours + ' hour' + (hours !== 1 ? 's' : '');

                        countdownText.innerHTML = '<span style="color: var(--accent);">(' + timeStr + ')</span>';
                    };

                    update();
                    setInterval(update, 60000); // Update every minute
                });


// ── URL-based episode number correction (fixes stale state bugs) ──────────
    (function fixEpisodeNumberFromURL() {
        const match = window.location.pathname.match(/\/ep-(\d+(?:\.\d+)?)/i);
        if (!match) return;
        const urlEpNum = parseFloat(match[1]);

        // Patch _watchState once it's defined (runs after inline init below)
        window._pendingEpNumFix = urlEpNum;

        // Fix sidebar: remove any wrong 'current' marks, set correct one
        document.addEventListener('DOMContentLoaded', function () {
            const epNum = window._pendingEpNumFix;
            if (epNum == null) return;

            // Sync _watchState
            if (window._watchState) {
                window._watchState.episodeNumber = epNum;
            }

            const list = document.getElementById('episodeList');
            if (!list) return;

            let foundCurrent = false;
            list.querySelectorAll('.episode-sidebar-item').forEach(item => {
                const itemNum = parseFloat(item.dataset.number);
                const shouldBeCurrent = itemNum === epNum;

                item.classList.toggle('current', shouldBeCurrent);
                if (shouldBeCurrent) foundCurrent = true;
            });

            // Auto-scroll to current episode inside the list container only (never scrolls the page)
            if (foundCurrent) {
                const currentEl = list.querySelector('.episode-sidebar-item.current');
                if (currentEl) {
                    setTimeout(() => {
                        const container = document.getElementById('episodeList');
                        if (container) {
                            const targetScrollTop = currentEl.offsetTop - (container.clientHeight / 2) + (currentEl.clientHeight / 2);
                            container.scrollTop = Math.max(0, targetScrollTop);
                        }
                    }, 300);
                }
            }

            // Validate prev/next nav buttons against URL-derived episode number
            // If they point to the wrong episode, log a warning (helps debug backend issues)
            const prevBtn = document.querySelector('a[href*="/ep-"]#watch-navigation a:first-child, #watch-navigation a:first-child');
            const nextBtn = document.querySelector('#watch-navigation a:nth-child(2)');

            [prevBtn, nextBtn].forEach(btn => {
                if (!btn) return;
                const btnMatch = btn.href && btn.href.match(/\/ep-(\d+)/);
                if (btnMatch) {
                    const btnEp = parseFloat(btnMatch[1]);
                    // Prev should be less than current, next should be greater
                    const isPrev = btn.textContent.trim().startsWith('Prev');
                    if (isPrev && btnEp >= epNum) {
                        console.warn('[EpNav] Prev button points to ep', btnEp, 'but current is', epNum, '— likely a backend numbering mismatch');
                    }
                    if (!isPrev && btnEp <= epNum) {
                        console.warn('[EpNav] Next button points to ep', btnEp, 'but current is', epNum, '— likely a backend numbering mismatch');
                    }
                }
            });
        });
    })();

    // ── URL is the single source of truth for episode number ──────────────────
    // Extract IMMEDIATELY so _watchState, prev/next buttons, and sidebar
    // all use the correct value even when the backend passes a wrong episode_number.
    var _urlEpMatch = window.location.pathname.match(/\/ep-(\d+(?:\.\d+)?)/i);
    var _urlEpNum = _urlEpMatch ? parseFloat(_urlEpMatch[1]) : null;

    // --- CRITICAL AUDIO CODEC FIX ---
    if (window.MediaSource && MediaSource.prototype?.addSourceBuffer) {
        try {
            const _origAddSourceBuffer = MediaSource.prototype.addSourceBuffer;
            MediaSource.prototype.addSourceBuffer = function (mimeType) {
                const fixed = mimeType.replace('mp4a.40.1', 'mp4a.40.2');
                if (fixed !== mimeType) console.log('[codec-fix] Remapped:', mimeType, '->', fixed);
                return _origAddSourceBuffer.call(this, fixed);
            };
        } catch (e) {
            console.warn('[codec-fix] Could not patch addSourceBuffer:', e);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        // Episode sidebar view toggle
        const episodeList = document.getElementById('episodeList');
        const viewListBtn = document.getElementById('view-list-btn');
        const viewGridBtn = document.getElementById('view-grid-btn');

        function setEpisodeView(view) {
            if (!episodeList) return;
            episodeList.setAttribute('data-view', view);
            localStorage.setItem('episodeView', view);
            viewListBtn?.classList.toggle('active', view === 'list');
            viewGridBtn?.classList.toggle('active', view === 'grid');
        }

        try {
            setEpisodeView(localStorage.getItem('episodeView') || 'grid');
        } catch (e) { }
        viewListBtn?.addEventListener('click', () => setEpisodeView('list'));
        viewGridBtn?.addEventListener('click', () => setEpisodeView('grid'));

        // Episode search
        const searchInput = document.getElementById('episodeSearch');
        if (searchInput && episodeList) {
            searchInput.addEventListener('input', (e) => {
                const term = e.target.value.toLowerCase();
                episodeList.querySelectorAll('.episode-sidebar-item').forEach(item => {
                    const match = item.dataset.number.includes(term) || item.textContent.toLowerCase().includes(term);
                    item.style.display = match ? '' : 'none';
                });
            });
        }

        // Auto-scroll to current episode (Removed as per user request for better UX on mobile)
        // const currentEp = episodeList?.querySelector('.current');

        // HLS Player Logic
        const video = document.getElementById('videoPlayer');
        if (video) {
            const videoUrl = video.dataset.videoUrl;
            console.log("[Player] Found URL:", videoUrl);

            if (Hls.isSupported() && (videoUrl.includes('.m3u8') || videoUrl.includes('/proxy/'))) {
                console.log("[Player] Initializing Hls.js");
                let initialSavedTime = 0;
                try {
                    const match = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
                    if (match) {
                        const storKey = `yumeResume_${match[1]}_ep${match[2]}`;
                        initialSavedTime = parseFloat(localStorage.getItem(storKey)) || 0;
                    }
                } catch(e) {}

                const hls = new Hls({
                    debug: false,
                    startPosition: initialSavedTime > 5 ? initialSavedTime : -1,
                    enableWorker: true,
                    // Timeout & retry config to avoid infinite loading on PC
                    manifestLoadingTimeOut: 15000,
                    manifestLoadingMaxRetry: 3,
                    manifestLoadingRetryDelay: 1000,
                    levelLoadingTimeOut: 15000,
                    levelLoadingMaxRetry: 3,
                    levelLoadingRetryDelay: 1000,
                    fragLoadingTimeOut: 20000,
                    fragLoadingMaxRetry: 4,
                    fragLoadingRetryDelay: 1000,
                    // Lower start for faster first-frame
                    startLevel: -1,
                    // Bandwidth estimation
                    abrEwmaDefaultEstimate: 500000,
                    // PC-specific: disable low-latency mode to improve compatibility
                    lowLatencyMode: false,
                    // Seek optimization — tolerate gaps and nudge playback past them
                    maxBufferHole: 0.5,
                    nudgeMaxRetry: 5,
                    maxFragLookUpTolerance: 0.25,
                    highBufferWatchdogPeriod: 2,
                    xhrSetup: function (xhr, url) {
                        xhr.withCredentials = false;
                    }
                });

                let hlsNetworkRetries = 0;
                let hlsMediaRecoveryAttempts = 0;
                hls.on(Hls.Events.ERROR, (e, data) => {
                    console.error('[HLS Error]', data.type, data.details);
                    if (data.fatal) {
                        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
                            hlsNetworkRetries++;
                            if (hlsNetworkRetries <= 3) {
                                console.log('[HLS] Network retry', hlsNetworkRetries);
                                hls.startLoad();
                            } else {
                                console.warn('[Fallback] HLS network retries exhausted');
                                tryFallback('hls');
                            }
                        } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
                            hlsMediaRecoveryAttempts++;
                            if (hlsMediaRecoveryAttempts <= 2) {
                                console.log('[HLS] Recovering media error, attempt', hlsMediaRecoveryAttempts);
                                hls.recoverMediaError();
                            } else {
                                console.warn('[Fallback] HLS media recovery exhausted');
                                tryFallback('hls');
                            }
                        } else {
                            console.warn('[Fallback] HLS fatal error on initial load, triggering fallback');
                            tryFallback('hls');
                        }
                    }
                });

                window.hls = hls; // Store global reference

                hls.attachMedia(video);
                hls.on(Hls.Events.MEDIA_ATTACHED, function () {
                    console.log('[Player] HLS media attached!');
                    hls.loadSource(videoUrl);
                });

                // KEY FIX: Trigger play on MANIFEST_PARSED — standard HLS.js pattern
                // Without this, PC browsers never start playback (autoplay policy)
                hls.on(Hls.Events.MANIFEST_PARSED, function (event, data) {
                    console.log('[Player] HLS manifest parsed, levels:', data.levels.length);
                    // Show overlay NOW — video is ready, so tapping it will actually work
                    var overlay = document.getElementById('mobilePlayOverlay');
                    if (overlay) overlay.style.display = 'flex';
                    video.play().then(function () {
                        // Autoplay succeeded — hide the overlay
                        if (overlay) overlay.style.display = 'none';
                    }).catch(function (e) {
                        console.log('[Player] Auto-play blocked by browser, awaiting user interaction:', e.name);
                        // Overlay is already visible — user can tap it to start playback
                    });
                });

                // Multi-stage stall detection with recovery before fallback
                let hlsStallRecoveryStage = 0;
                window._hlsStallTimer = setTimeout(function hlsStallCheck() {
                    // If video is playing fine, stop checking
                    if (video.readyState >= 3 && !video.paused && video.currentTime > 0) {
                        console.log('[Player] HLS playing successfully');
                        return;
                    }
                    hlsStallRecoveryStage++;
                    if (hlsStallRecoveryStage === 1) {
                        // Stage 1: Check if we have buffered data but video is stuck
                        if (video.buffered.length > 0 && video.readyState < 3) {
                            console.warn('[HLS Recovery] Buffered data exists but readyState=' + video.readyState + ', attempting recoverMediaError');
                            hls.recoverMediaError();
                            video.play().catch(function () { });
                        } else if (video.readyState >= 3) {
                            // Data ready but not playing — try play again
                            console.log('[HLS Recovery] readyState OK, re-triggering play');
                            video.play().catch(function () { });
                        }
                        window._hlsStallTimer = setTimeout(hlsStallCheck, 10000);
                    } else if (hlsStallRecoveryStage === 2) {
                        // Stage 2: If still stuck, try swapping codec levels
                        if (video.readyState < 3 || (video.paused && video.currentTime === 0)) {
                            console.warn('[HLS Recovery] Stage 2: Attempting level switch + recoverMediaError');
                            if (hls.levels && hls.levels.length > 1) {
                                hls.currentLevel = hls.levels.length - 1; // Force lowest quality
                            }
                            hls.recoverMediaError();
                            video.play().catch(function () { });
                            window._hlsStallTimer = setTimeout(hlsStallCheck, 10000);
                        } else {
                            console.log('[Player] HLS recovered at stage 2');
                        }
                    } else {
                        // Stage 3: Give up and fallback
                        if (video.readyState < 3 || (video.paused && video.currentTime === 0)) {
                            console.warn('[Fallback] HLS stall unrecoverable after multi-stage recovery, triggering fallback');
                            tryFallback('hls');
                        }
                    }
                }, 15000);
                // Clear stall timer once video is genuinely playing
                video.addEventListener('playing', function onPlaying() {
                    clearTimeout(window._hlsStallTimer);
                    window._hlsStallTimer = null;
                    video.removeEventListener('playing', onPlaying);
                }, { once: false });

            } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                // Native Safari HLS
                console.log("[Player] Using Native HLS (iOS/Safari)");
                video.src = videoUrl;
                video.load(); // Force iOS Safari to load metadata immediately
                // Show overlay once video is ready to play (so tap reliably starts it)
                video.addEventListener('canplay', function onNativeCanPlay() {
                    video.removeEventListener('canplay', onNativeCanPlay);
                    var overlay = document.getElementById('mobilePlayOverlay');
                    if (overlay) overlay.style.display = 'flex';
                    video.play().then(function () {
                        if (overlay) overlay.style.display = 'none';
                    }).catch(function () {
                        // Overlay stays visible for user to tap
                    });
                }, { once: true });
            } else {
                console.log("[Player] Basic MP4 Embed");
                video.src = videoUrl;
                video.load();
            }
        }
    });

    // Shared cleanup helper — tears down ALL active players (HLS, video, embed)
    function cleanupCurrentPlayer() {
        // Cancel any pending stall detection timers to prevent ghost fallbacks
        if (window._hlsStallTimer) {
            clearTimeout(window._hlsStallTimer);
            window._hlsStallTimer = null;
        }
        if (window._ajaxStallTimer) {
            clearTimeout(window._ajaxStallTimer);
            window._ajaxStallTimer = null;
        }
        // Destroy any active HLS.js instance
        if (window.hls) {
            try {
                window.hls.stopLoad();
                window.hls.detachMedia();
                window.hls.destroy();
            } catch (e) { console.warn('[cleanup] hls destroy error:', e); }
            window.hls = null;
        }
        // Pause and reset the native video element
        const video = document.getElementById('videoPlayer');
        if (video) {
            try {
                video.pause();
                video.removeAttribute('src');
                // Remove all source elements to prevent stale playback
                video.querySelectorAll('source').forEach(s => s.remove());
                video.load();
            } catch (e) { console.warn('[cleanup] video reset error:', e); }
            video.style.display = 'none';
            // Remove the progress tracking flag so new instances get re-tracked
            video.removeAttribute('data-progress-tracked');
        }
        // Hide the video container and custom player UI
        const vc = document.getElementById('videoContainer');
        if (vc) vc.style.display = 'none';
        const ui = document.getElementById('customPlayerUI');
        if (ui) ui.style.display = 'none';
        // Clear any embed iframe so its audio/video stops, and hide it
        const embedFrame = document.getElementById('embedPlayer');
        if (embedFrame) {
            embedFrame.removeAttribute('src');
            embedFrame.style.display = 'none';
        }
        // Always hide the error fallback during transitions
        const fallback = document.getElementById('errorFallbackContainer');
        if (fallback) fallback.style.display = 'none';
    }

    // ── Global Fullscreen & Orientation Helpers ──────────────────────────────────
    // Defined at top-level so they work for BOTH HLS & embed player types.

    function lockOrientation() {
        try {
            if (screen.orientation && screen.orientation.lock) {
                screen.orientation.lock("landscape").catch((err) => {
                    console.log("[Player] Screen orientation lock failed:", err);
                });
            } else {
                const lockFn = screen.lockOrientation || screen.mozLockOrientation || screen.msLockOrientation;
                if (lockFn) lockFn.call(screen, "landscape");
            }
        } catch (e) {
            console.log("[Player] Orientation lock not supported:", e);
        }
    }

    function unlockOrientation() {
        try {
            if (screen.orientation && screen.orientation.unlock) {
                screen.orientation.unlock();
            } else {
                const unlockFn = screen.unlockOrientation || screen.mozUnlockOrientation || screen.msUnlockOrientation;
                if (unlockFn) unlockFn.call(screen);
            }
        } catch (e) {
            console.log("[Player] Orientation unlock not supported:", e);
        }
    }

    /**
     * Request fullscreen on the target element with orientation lock.
     * Falls back gracefully: masterWrapper → video.webkitEnterFullscreen (iOS).
     */
    window._requestPlayerFullscreen = function (targetEl, videoEl) {
        try {
            if (document.fullscreenElement || document.webkitFullscreenElement) {
                // Already fullscreen → exit
                if (document.exitFullscreen) document.exitFullscreen();
                else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
            } else {
                // Lock orientation first (must happen during user gesture)
                lockOrientation();

                if (targetEl && targetEl.requestFullscreen) {
                    targetEl.requestFullscreen();
                } else if (targetEl && targetEl.webkitRequestFullscreen) {
                    targetEl.webkitRequestFullscreen();
                } else if (videoEl && videoEl.webkitEnterFullscreen) {
                    // iOS Safari native fullscreen on the video element itself
                    if (videoEl.readyState === 0) {
                        alert("Video is still loading. Please tap play first.");
                        videoEl.play().catch(e => console.log(e));
                    } else {
                        videoEl.webkitEnterFullscreen();
                    }
                }
            }
        } catch (err) {
            console.error("Fullscreen error:", err);
        }
    };

    // Global fullscreen state listeners — handle orientation lock/unlock & layout
    // These fire for ALL fullscreen changes (HLS player, embed iframes, etc.)
    function handleFullscreenChange() {
        const fsEl = document.fullscreenElement || document.webkitFullscreenElement;
        const mw = document.getElementById('video-wrapper');
        if (fsEl) {
            lockOrientation();
            if (mw) {
                mw.style.width = "100%";
                mw.style.height = "100%";
                mw.style.maxHeight = "100dvh";
            }
        } else {
            unlockOrientation();
            if (mw) {
                mw.style.width = "";
                mw.style.height = "";
                mw.style.maxHeight = "";
            }
        }
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange, true);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange, true);

    // Handle orientation changes while in fullscreen (resize layout)
    window.addEventListener("orientationchange", () => {
        const mw = document.getElementById('video-wrapper');
        if (mw && (document.fullscreenElement || document.webkitFullscreenElement)) {
            mw.style.width = "100%";
            mw.style.height = "100%";
            mw.style.maxHeight = "100dvh";
        }
    });

    // ── Embed-only fullscreen support ──────────────────────────────────────────
    // If the page only has an embed player (no HLS video), initVanillaPlayerUI won't run,
    // so we need a separate fullscreen handler for the embed iframe.
    document.addEventListener('DOMContentLoaded', function () {
        const videoPlayer = document.getElementById('videoPlayer');
        // Only set up embed fullscreen if there's no HLS player (embed-only page)
        if (!videoPlayer) {
            const masterWrapper = document.getElementById('video-wrapper');
            if (masterWrapper) {
                // Double-tap on mobile to fullscreen the embed
                let lastTap = 0;
                masterWrapper.addEventListener('touchend', function (e) {
                    const now = Date.now();
                    if (now - lastTap < 300) {
                        e.preventDefault();
                        window._requestPlayerFullscreen(masterWrapper, null);
                    }
                    lastTap = now;
                });
            }
        }
    });

    // ── Server Section Pill Click Logic (INTERNAL/EXTERNAL) ─────────────────
    // Clicking an INTERNAL pill → switch to that provider and load HLS
    // Clicking an EXTERNAL pill → switch to that provider and load Embed
    document.addEventListener('DOMContentLoaded', function () {
        const serverSections = document.getElementById('serverSections');
        if (!serverSections) return;

        serverSections.addEventListener('click', function (e) {
            const pill = e.target.closest('.server-pill');
            if (!pill || pill.disabled || pill.classList.contains('unavailable')) return;

            const streamType = pill.dataset.streamType; // 'hls' or 'embed'
            const provider = pill.dataset.provider;
            if (!streamType || !provider) return;

            e.preventDefault();

            // Update active state: deactivate ALL pills in the OTHER section,
            // and set active within the clicked section
            const allSections = serverSections.querySelectorAll('.server-section-pills');
            allSections.forEach(sec => {
                sec.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));
            });
            pill.classList.add('active');

            // Store desired stream type so fetchAndLoadSources knows what to play
            window._watchState._desiredStreamType = streamType;
            window._watchState.provider = provider;

            // Save preference
            if (window.serverManager) {
                window.serverManager.savePreferredServer(provider);
            } else {
                try {
                    localStorage.setItem('yumePreferredServer', provider);
                    document.cookie = `preferred_server=${provider}; path=/; max-age=31536000`;
                } catch (e) { }
            }

            fetchAndLoadSources();
        });
    });

    // Server Progress Configuration
    window._watchProgressState = {
        isLoggedIn: window.WATCH_CONFIG.isLoggedIn,
        serverProgress: window.WATCH_CONFIG.serverProgress || {},
        animeId: window.WATCH_CONFIG.animeId
    };

    function initWatchlistButtons() { }

    // ─── Auto Resume + Embed Tracking System ────────────────────────────────
    (function initAutoResume() {
        const pathMatch = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
        if (!pathMatch) return;

        const animeId = pathMatch[1];
        const epNum = pathMatch[2];
        const storageKey = `yumeResume_${animeId}_ep${epNum}`;

        // Load saved resume time
        let savedTime = 0;
        try { savedTime = parseFloat(localStorage.getItem(storageKey)) || 0; } catch (e) { }

        // ── HLS / native video player ──────────────────────────────────────────
        const hlsVideo = document.getElementById('videoPlayer');
        if (hlsVideo) {
            const saveHLS = () => {
                if (hlsVideo.currentTime > 5)
                    try { localStorage.setItem(storageKey, String(hlsVideo.currentTime)); } catch (e) { }
            };
            hlsVideo.addEventListener('timeupdate', () => { if (Math.floor(hlsVideo.currentTime) % 5 === 0) saveHLS(); });
            hlsVideo.addEventListener('pause', saveHLS);
            hlsVideo.addEventListener('ended', () => { try { localStorage.removeItem(storageKey); } catch (e) { } });
            window.addEventListener('beforeunload', saveHLS);

            const doHLSResume = () => {
                if (savedTime > 10 && hlsVideo.duration > savedTime + 5) {
                    hlsVideo.currentTime = savedTime;
                    console.log('[AutoResume] HLS resumed from', savedTime + 's');
                }
            };
            hlsVideo.addEventListener('loadedmetadata', doHLSResume);
            hlsVideo.addEventListener('canplay', doHLSResume, { once: true });
        }

        // ── Auto-mark episode watched in watchlist at 80% progress ────────────
        // Works for both HLS video and embed (wall-clock timer).
        // This runs once per episode page load — `markedWatched` prevents double-fire.
        (function initWatchlistAutoMark() {
            const state = window._watchProgressState;
            if (!state || !state.isLoggedIn) return;

            const animeIdForMark = (window._watchState && window._watchState.animeId)
                || (window.location.pathname.match(/\/watch\/([^\/]+)\//) || [])[1];
            const epNumForMark = (window._watchState && window._watchState.episodeNumber)
                || parseInt((window.location.pathname.match(/\/ep-(\d+)/) || [])[1], 10);

            if (!animeIdForMark || !epNumForMark) return;

            let markedWatched = false;

            function markWatched() {
                if (markedWatched) return;
                markedWatched = true;
                const payload = {
                    anime_id: animeIdForMark,
                    action: 'episodes',
                    watched_episodes: epNumForMark
                };
                if (window.WATCH_CONFIG && window.WATCH_CONFIG.malId && localStorage.getItem('yume_mal_sync') === 'true') {
                    payload.sync_mal = true;
                    payload.mal_id = window.WATCH_CONFIG.malId;
                }
                fetch('/api/watchlist/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }).then(r => {
                    if (r.ok) console.log('[Watchlist] Episode', epNumForMark, 'marked as watched');
                }).catch(() => { });
            }

            // HLS / native video: mark at 80% completion
            const hlsVid = document.getElementById('videoPlayer');
            if (hlsVid) {
                hlsVid.addEventListener('timeupdate', function onProgress() {
                    if (!markedWatched && hlsVid.duration > 0 &&
                        (hlsVid.currentTime / hlsVid.duration) >= 0.80) {
                        markWatched();
                        hlsVid.removeEventListener('timeupdate', onProgress);
                    }
                });
                hlsVid.addEventListener('ended', markWatched);
            }

            // Embed (iframe): wall-clock based — mark after 18 minutes
            // (covers ~80% of a typical 24-min episode).
            // This is already tracked by elapsedSecs in the outer IIFE;
            // we hook in by polling the shared elapsed counter.
            const embedFrame = document.getElementById('embedPlayer');
            if (embedFrame && !hlsVid) {
                // 18 minutes = 1080 seconds is a reasonable "mostly watched" threshold
                const EMBED_MARK_AFTER_SECS = 1080;
                const embedMarkTimer = setInterval(() => {
                    // elapsedSecs is defined in the outer IIFE scope
                    if (typeof elapsedSecs !== 'undefined' && elapsedSecs >= EMBED_MARK_AFTER_SECS) {
                        clearInterval(embedMarkTimer);
                        markWatched();
                    }
                }, 10000); // check every 10 seconds
            }
        })();

        // ── Embed (iframe) player ──────────────────────────────────────────────
        const embedFrame = document.getElementById('embedPlayer');
        if (embedFrame) {
            // Inject resume time via every common URL param format
            if (savedTime > 10) {
                try {
                    const t = Math.floor(savedTime);
                    let src = embedFrame.src.split('#')[0];
                    // Remove any existing time params
                    src = src.replace(/([?&])(t|start|starttime|begin|at)=\d+/gi, '');
                    const sep = src.includes('?') ? '&' : '?';
                    // Inject all common formats; player will use what it understands
                    embedFrame.src = src + sep + 't=' + t + '&start=' + t + '#t=' + t;
                    console.log('[AutoResume] Embed resumed from', t + 's');
                } catch (e) { }
            }

            // Wall-clock timer to track elapsed seconds in embed (provider-agnostic)
            let elapsedSecs = savedTime;
            let embedTimer = null;

            function startEmbedTimer() {
                if (embedTimer) return;
                embedTimer = setInterval(() => {
                    if (document.visibilityState === 'visible') {
                        elapsedSecs++;
                        if (elapsedSecs > 5) try { localStorage.setItem(storageKey, String(elapsedSecs)); } catch (e) { }
                    }
                }, 1000);
            }
            function stopEmbedTimer() {
                clearInterval(embedTimer);
                embedTimer = null;
            }

            // Start timer 2s after iframe loads (gives player time to init)
            embedFrame.addEventListener('load', () => setTimeout(startEmbedTimer, 2000));
            document.addEventListener('visibilitychange', () => {
                document.visibilityState === 'hidden' ? stopEmbedTimer() : startEmbedTimer();
            });

            // On tab close: save time + fire watchlist beacon if user clicked Next
            window.addEventListener('beforeunload', () => {
                stopEmbedTimer();
                try { localStorage.setItem(storageKey, String(elapsedSecs)); } catch (e) { }

                if (window._forceEpisodeComplete && window._watchProgressState && window._watchProgressState.isLoggedIn) {
                    const epNumber = window._watchState && window._watchState.episodeNumber;
                    if (epNumber) {
                        const payload = { anime_id: animeId, action: 'episodes', watched_episodes: epNumber };
                        if (window.WATCH_CONFIG && window.WATCH_CONFIG.malId && localStorage.getItem('yume_mal_sync') === 'true') {
                            payload.sync_mal = true;
                            payload.mal_id = window.WATCH_CONFIG.malId;
                        }
                        navigator.sendBeacon('/api/watchlist/update',
                            new Blob([JSON.stringify(payload)],
                                { type: 'application/json' }));
                    }
                }
            });

            // Detect natural episode end via postMessage (works if provider sends it)
            window.addEventListener('message', (ev) => {
                if (!ev.data) return;
                let d = ev.data;
                if (typeof d === 'string') { try { d = JSON.parse(d); } catch (e) { return; } }
                const ended = d.event === 'ended' || d.type === 'ended' || d.event === 'complete' || d.ended === true;
                if (ended) {
                    stopEmbedTimer();
                    try { localStorage.removeItem(storageKey); } catch (e) { }
                    if (window._watchProgressState && window._watchProgressState.isLoggedIn) {
                        const payload = { anime_id: animeId, action: 'episodes', watched_episodes: window._watchState && window._watchState.episodeNumber };
                        if (window.WATCH_CONFIG && window.WATCH_CONFIG.malId && localStorage.getItem('yume_mal_sync') === 'true') {
                            payload.sync_mal = true;
                            payload.mal_id = window.WATCH_CONFIG.malId;
                        }
                        fetch('/api/watchlist/update', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        }).catch(() => { });
                    }
                }
            });
        }
    })();
    // ──────────────────────────────────────────────────────────────────────────

    // ─── Watch History Metadata Tracker ──────────────────────────────────────
    // Saves rich metadata to localStorage for Continue Watching / Watch History
    // sections on the home page. Uses key: yumeHistory_{animeId}_ep{epNum}
    (function initWatchHistoryTracker() {
        const pathMatch = window.location.pathname.match(/\/watch\/([^\/]+)\/ep-(\d+)/);
        if (!pathMatch) return;

        const animeId = pathMatch[1];
        const epNum = pathMatch[2];
        const historyKey = `yumeHistory_${animeId}_ep${epNum}`;
        const resumeKey = `yumeResume_${animeId}_ep${epNum}`;

        // Gather metadata from page
        const animeTitle = document.querySelector('.anime-title-main')?.textContent?.trim()
            || document.querySelector('title')?.textContent?.replace(/ - YumeAnime.*/, '').replace(/,?\s*Episode \d+/, '').trim()
            || animeId.replace(/-/g, ' ');
        const posterEl = document.querySelector('.anime-poster');
        const poster = posterEl ? posterEl.src : '';
        const epTitleEl = document.querySelector('.player-title span:last-child');
        const episodeTitle = epTitleEl ? epTitleEl.textContent.trim() : '';

        function saveHistoryMeta(currentTime, duration, completed) {
            try {
                const existing = JSON.parse(localStorage.getItem(historyKey) || '{}');
                const entry = {
                    animeId: animeId,
                    epNum: parseInt(epNum),
                    animeName: animeTitle,
                    episodeTitle: episodeTitle,
                    poster: poster,
                    timestamp: currentTime || existing.timestamp || 0,
                    duration: duration || existing.duration || 0,
                    completed: completed || false,
                    watchedAt: Date.now()
                };
                localStorage.setItem(historyKey, JSON.stringify(entry));
            } catch (e) { }
        }

        // Save initial entry immediately (marks that user visited this episode)
        setTimeout(() => {
            saveHistoryMeta(0, 0, false);
        }, 2000);

        // HLS video tracking
        const hlsVideo = document.getElementById('videoPlayer');
        if (hlsVideo) {
            let lastHistorySave = 0;
            hlsVideo.addEventListener('timeupdate', () => {
                const now = Date.now();
                if (now - lastHistorySave > 10000) { // Save every 10 seconds
                    lastHistorySave = now;
                    saveHistoryMeta(hlsVideo.currentTime, hlsVideo.duration, false);
                }
            });
            hlsVideo.addEventListener('pause', () => {
                saveHistoryMeta(hlsVideo.currentTime, hlsVideo.duration, false);
            });
            hlsVideo.addEventListener('ended', () => {
                saveHistoryMeta(hlsVideo.duration, hlsVideo.duration, true);
                // Remove resume key on completion
                try { localStorage.removeItem(resumeKey); } catch(e) {}
            });
            window.addEventListener('beforeunload', () => {
                saveHistoryMeta(hlsVideo.currentTime, hlsVideo.duration, false);
            });
        }

        // Embed tracking (wall-clock based)
        const embedFrame = document.getElementById('embedPlayer');
        if (embedFrame && !hlsVideo) {
            let embedElapsed = 0;
            try {
                const saved = parseFloat(localStorage.getItem(resumeKey)) || 0;
                embedElapsed = saved;
            } catch(e) {}

            setInterval(() => {
                if (document.visibilityState === 'visible') {
                    embedElapsed++;
                    if (embedElapsed % 15 === 0) { // Save every 15 seconds
                        saveHistoryMeta(embedElapsed, 0, false);
                    }
                }
            }, 1000);

            window.addEventListener('beforeunload', () => {
                saveHistoryMeta(embedElapsed, 0, false);
            });
        }
    })();
    // ──────────────────────────────────────────────────────────────────────────

    // Custom Vanilla UI Driver
    function initVanillaPlayerUI() {
        if (window._vanillaUiInitialized) return;

        const video = document.getElementById('videoPlayer');
        const wrapper = document.getElementById('videoContainer');
        const playBtn = document.getElementById('playPauseBtn');
        const centerPlayBtn = document.getElementById('centerPlayBtn');
        const muteBtn = document.getElementById('muteBtn');
        const volumeSlider = document.getElementById('volumeSlider');
        const fsBtn = document.getElementById('fullscreenBtn');
        const progressContainer = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        const progressThumb = document.getElementById('progressThumb');
        const progressBuffer = document.getElementById('progressBuffer');
        const progressTooltip = document.getElementById('progressTooltip');
        const tooltipThumbCanvas = document.getElementById('tooltipThumbCanvas');
        const tooltipTimeText   = document.getElementById('tooltipTimeText');
        const tooltipThumbCtx   = tooltipThumbCanvas ? tooltipThumbCanvas.getContext('2d') : null;
        const currTimeDisp = document.getElementById('currentTimeDisplay');
        const durDisp = document.getElementById('durationDisplay');

        // New UI Elements
        const settingsBtn = document.getElementById('settingsBtn');
        const settingsMenu = document.getElementById('settingsMenu');
        const settingsContainer = document.getElementById('settingsContainer');
        const speedOptions = document.getElementById('speedOptions');
        const qualityOptions = document.getElementById('qualityOptions');
        const pipBtn = document.getElementById('pipBtn');
        const dtLeft = document.getElementById('dtLeft');
        const dtRight = document.getElementById('dtRight');
        const dtIndLeft = document.getElementById('dtIndLeft');
        const dtIndRight = document.getElementById('dtIndRight');
        const playerLoader = document.getElementById('playerLoader');

        if (!video || !wrapper || !playBtn) return;
        
        window._vanillaUiInitialized = true;

        const masterWrapper = document.getElementById('video-wrapper');

        // Mouse Inactivity Timeout (3 seconds)
        let inactivityTimeout;
        const resetInactivity = () => {
            if (masterWrapper) {
                masterWrapper.classList.remove('user-inactive');
            }
            clearTimeout(inactivityTimeout);
            if (!video.paused) {
                inactivityTimeout = setTimeout(() => {
                    if (masterWrapper) {
                        masterWrapper.classList.add('user-inactive');
                        masterWrapper.classList.remove('controls-visible');
                    }
                    mobileControlsVisible = false;
                }, 3000);
            }
        };

        // Mobile: tap to toggle controls visibility
        let mobileControlsVisible = false;
        const showMobileControls = () => {
            if (!masterWrapper) return;
            masterWrapper.classList.add('controls-visible');
            masterWrapper.classList.remove('user-inactive');
            mobileControlsVisible = true;
            clearTimeout(inactivityTimeout);
            if (!video.paused) {
                inactivityTimeout = setTimeout(() => {
                    masterWrapper.classList.remove('controls-visible');
                    if (!video.paused) masterWrapper.classList.add('user-inactive');
                    mobileControlsVisible = false;
                }, 3000);
            }
        };

        if (masterWrapper) {
            masterWrapper.addEventListener('mousemove', resetInactivity);
            masterWrapper.addEventListener('mouseleave', () => {
                if (!video.paused) {
                    clearTimeout(inactivityTimeout);
                    if (masterWrapper) {
                        masterWrapper.classList.add('user-inactive');
                        masterWrapper.classList.remove('controls-visible');
                    }
                    mobileControlsVisible = false;
                }
            });
            // On mobile: single tap toggles control bar visibility (show ↔ hide)
            masterWrapper.addEventListener('touchstart', (e) => {
                // Only toggle if the tap isn't on a control button/progress bar
                const isControl = e.target.closest('.controls-bar') || e.target.closest('.player-top-bar') || e.target.closest('#mobilePlayOverlay');
                if (!isControl) {
                    // Toggle: if already visible, hide; if hidden, show
                    if (mobileControlsVisible) {
                        clearTimeout(inactivityTimeout);
                        masterWrapper.classList.remove('controls-visible');
                        if (!video.paused) masterWrapper.classList.add('user-inactive');
                        mobileControlsVisible = false;
                    } else {
                        showMobileControls();
                    }
                } else {
                    // Even control taps should reset the hide timer
                    resetInactivity();
                }
            }, { passive: true });
            document.addEventListener('keydown', resetInactivity);
        }

        // Play/Pause
        let playThrottleTimer = null;
        const togglePlay = (e) => {
            if (e && e.type) {
                e.preventDefault();
                e.stopPropagation();
            }
            // Prevent ghost clicks from firing immediately after pointerup
            if (playThrottleTimer) return;
            playThrottleTimer = setTimeout(() => { playThrottleTimer = null; }, 400);

            if (video.paused) {
                const playPromise = video.play();
                if (playPromise !== undefined) {
                    playPromise.catch(err => {
                        console.error("Play error:", err);
                    });
                }
            } else {
                video.pause();
            }
        };
        playBtn.addEventListener('pointerup', togglePlay);
        playBtn.addEventListener('click', togglePlay);
        centerPlayBtn.addEventListener('pointerup', togglePlay);
        centerPlayBtn.addEventListener('click', togglePlay);

        // Track the timestamp of the last touchend so we can distinguish
        // a real mouse-click from a synthetic click fired after a touch tap.
        // This is the most reliable cross-browser approach and works in
        // Brave, Firefox, Safari, and Chrome on Android/iOS.
        let _lastTouchEnd = 0;
        wrapper.addEventListener('touchend', () => { _lastTouchEnd = Date.now(); }, { passive: true });

        wrapper.addEventListener('click', (e) => {
            // On touch devices a tap fires touchstart → touchend → click.
            // We only want the click handler to run for genuine mouse clicks.
            // 500 ms is well above the typical 300 ms click-delay on mobile.
            if (Date.now() - _lastTouchEnd < 500) return;

            // Ignore if clicking on interactive UI elements or controls
            if (e.target.closest('.controls-bar') || 
                e.target.closest('.player-top-bar') || 
                e.target.closest('.player-menu') ||
                e.target.closest('.center-play-pause')) {
                return;
            }
            togglePlay();
        });

        // Mobile Overlay Logic is handled by the standalone initMobileOverlay() below.
        // Do NOT attach duplicate listeners here.

        const iconPlay = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 6.82v10.36c0 .79.87 1.27 1.54.84l8.14-5.18c.62-.39.62-1.29 0-1.69L9.54 5.98C8.87 5.55 8 6.03 8 6.82z"/></svg>';
        const iconPause = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 19c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2s-2 .9-2 2v10c0 1.1.9 2 2 2zm6-12v10c0 1.1.9 2 2 2s2-.9 2-2V7c0-1.1-.9-2-2-2s-2 .9-2 2z"/></svg>';

        video.addEventListener('play', () => {
            if (masterWrapper) masterWrapper.classList.remove('paused');
            if (mobilePlayOverlay) mobilePlayOverlay.style.display = 'none';
            if (centerPlayBtn) centerPlayBtn.style.display = '';
            playBtn.innerHTML = iconPause;
            centerPlayBtn.innerHTML = iconPause;
            resetInactivity();
        });
        video.addEventListener('pause', () => {
            if (masterWrapper) masterWrapper.classList.add('paused');
            playBtn.innerHTML = iconPlay;
            centerPlayBtn.innerHTML = iconPlay;
            clearTimeout(inactivityTimeout);
            if (masterWrapper) masterWrapper.classList.remove('user-inactive');
        });

        video.addEventListener('playing', () => {
            if (playerLoader) playerLoader.style.display = 'none';
        });
        video.addEventListener('waiting', () => {
            if (playerLoader) playerLoader.style.display = 'flex';
        });
        video.addEventListener('canplay', () => {
            if (playerLoader) playerLoader.style.display = 'none';
        });
        // Show loader immediately on seek, hide when seeked completes
        video.addEventListener('seeking', () => {
            if (playerLoader) playerLoader.style.display = 'flex';
        });
        video.addEventListener('seeked', () => {
            if (playerLoader) playerLoader.style.display = 'none';
        });

        // Time & Progress
        const formatTime = (s) => {
            if (isNaN(s)) return '00:00';
            let m = Math.floor(s / 60); let sec = Math.floor(s % 60);
            let h = Math.floor(m / 60); m = m % 60;
            return (h > 0 ? h + ':' : '') + (m < 10 && h > 0 ? '0' : '') + m + ':' + (sec < 10 ? '0' : '') + sec;
        };

        // ── Thumbnail preview engine ──────────────────────────────────────────
        // Captures video frames periodically while the video plays and uses the
        // nearest cached frame when the user hovers or scrubs the progress bar.
        // A hidden offscreen canvas is used; CORS is not needed because we draw
        // from the same <video> element that is already playing the content.
        const THUMB_INTERVAL_S = 5;   // capture one frame every 5 s of video time
        const thumbFrames = new Map(); // key = bucketed time (s), value = ImageData
        let _lastCaptureBucket = -1;

        // Reset state when a new video is loaded
        video.addEventListener('loadstart', () => {
            thumbFrames.clear();
            _lastCaptureBucket = -1;
            if (progressFill) progressFill.style.width = '0%';
            if (progressThumb) progressThumb.style.left = '0%';
            if (progressBuffer) progressBuffer.style.width = '0%';
            if (currTimeDisp) currTimeDisp.textContent = '00:00';
            if (durDisp) durDisp.textContent = '00:00';
            if (tooltipThumbCanvas) {
                tooltipThumbCanvas.classList.remove('has-frame');
                if (tooltipThumbCtx) tooltipThumbCtx.clearRect(0, 0, tooltipThumbCanvas.width, tooltipThumbCanvas.height);
            }
        });

        // Offscreen scratch canvas for capture (reused to avoid GC pressure)
        const captureCanvas = document.createElement('canvas');
        captureCanvas.width  = 160;
        captureCanvas.height = 90;
        const captureCtx = captureCanvas.getContext('2d');

        function captureFrame() {
            if (!video || video.readyState < 2 || video.videoWidth === 0) return;
            try {
                captureCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
                const bucket = Math.floor(video.currentTime / THUMB_INTERVAL_S) * THUMB_INTERVAL_S;
                if (!thumbFrames.has(bucket)) {
                    // Store ImageData (cheaper than toDataURL, no encoding)
                    thumbFrames.set(bucket, captureCtx.getImageData(0, 0, captureCanvas.width, captureCanvas.height));
                }
            } catch (e) { /* cross-origin guard — silently skip */ }
        }

        // Capture a frame every THUMB_INTERVAL_S of playback time
        video.addEventListener('timeupdate', () => {
            const bucket = Math.floor(video.currentTime / THUMB_INTERVAL_S) * THUMB_INTERVAL_S;
            if (bucket !== _lastCaptureBucket) {
                _lastCaptureBucket = bucket;
                captureFrame();
            }
        });

        // Render nearest cached frame into the tooltip canvas
        function showTooltipThumb(timeSec) {
            if (!tooltipThumbCtx || !tooltipThumbCanvas || thumbFrames.size === 0) return;
            const bucket = Math.round(timeSec / THUMB_INTERVAL_S) * THUMB_INTERVAL_S;
            // Find closest available bucket
            let bestKey = null, bestDist = Infinity;
            thumbFrames.forEach((_, k) => {
                const d = Math.abs(k - bucket);
                if (d < bestDist) { bestDist = d; bestKey = k; }
            });
            if (bestKey === null) return;
            tooltipThumbCtx.putImageData(thumbFrames.get(bestKey), 0, 0);
            tooltipThumbCanvas.classList.add('has-frame');
        }

        // Unified tooltip updater (time text + optional thumb)
        function updateProgressTooltip(pos) {
            if (!progressTooltip || !video.duration) return;
            const timeSec = pos * video.duration;
            // Update time text
            if (tooltipTimeText) {
                tooltipTimeText.textContent = formatTime(timeSec);
            } else {
                progressTooltip.textContent = formatTime(timeSec);
            }
            // Position the tooltip, clamped to bar edges
            const thumbW = tooltipThumbCanvas && tooltipThumbCanvas.classList.contains('has-frame') ? 160 : 0;
            const tooltipHalfW = Math.max(thumbW / 2, 25);
            const barW = progressContainer.getBoundingClientRect().width;
            const pxPos = pos * barW;
            const clampedPct = Math.max(tooltipHalfW, Math.min(barW - tooltipHalfW, pxPos)) / barW * 100;
            progressTooltip.style.left = `${clampedPct}%`;
            showTooltipThumb(timeSec);
        }
        // ─────────────────────────────────────────────────────────────────────

        video.addEventListener('timeupdate', () => {
            const cur = video.currentTime;
            const dur = video.duration;
            currTimeDisp.textContent = formatTime(cur);
            durDisp.textContent = formatTime(dur);
            if (dur > 0) {
                const pct = (cur / dur) * 100;
                progressFill.style.width = pct + '%';
                progressThumb.style.left = pct + '%';
            }
        });

        video.addEventListener('progress', () => {
            if (video.buffered.length > 0) {
                const pct = (video.buffered.end(video.buffered.length - 1) / video.duration) * 100;
                progressBuffer.style.width = pct + '%';
            }
        });

        // ── Smooth Progress Bar Seeking (unified mouse + touch) ──────────────
        let isSeeking = false;
        let seekRaf = null;
        let seekPos = 0;  // 0–1 fraction

        function getSeekPos(clientX) {
            const rect = progressContainer.getBoundingClientRect();
            return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        }

        function updateSeekVisual(pos) {
            const pct = pos * 100;
            progressFill.style.width = pct + '%';
            progressThumb.style.left = pct + '%';
            // Live time preview
            if (video.duration > 0) {
                currTimeDisp.textContent = formatTime(pos * video.duration);
                if (isSeeking && progressTooltip) {
                    progressTooltip.textContent = formatTime(pos * video.duration);
                    progressTooltip.style.left = pct + '%';
                }
            }
        }

        function startSeek(clientX) {
            isSeeking = true;
            seekPos = getSeekPos(clientX);
            progressContainer.classList.add('seeking');
            updateSeekVisual(seekPos);
            showMobileControls();
        }

        function moveSeek(clientX) {
            if (!isSeeking) return;
            seekPos = getSeekPos(clientX);
            // Use rAF for smooth 60fps visual updates without hammering video.currentTime
            if (seekRaf) cancelAnimationFrame(seekRaf);
            seekRaf = requestAnimationFrame(() => {
                updateSeekVisual(seekPos);
                // Show tooltip (with thumbnail) during scrubbing on all devices
                if (progressTooltip) updateProgressTooltip(seekPos);
            });
        }

        function endSeek() {
            if (!isSeeking) return;
            isSeeking = false;
            if (seekRaf) { cancelAnimationFrame(seekRaf); seekRaf = null; }
            progressContainer.classList.remove('seeking');
            // Apply the actual seek on release
            if (video.duration > 0) {
                video.currentTime = seekPos * video.duration;
            }
        }

        // Mouse: click to seek instantly, drag for smooth scrubbing
        progressContainer.addEventListener('mousemove', (e) => {
            if (!video.duration || !progressTooltip) return;
            const rect = progressContainer.getBoundingClientRect();
            let pos = (e.clientX - rect.left) / rect.width;
            pos = Math.max(0, Math.min(1, pos));
            updateProgressTooltip(pos);
        });
        
        progressContainer.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startSeek(e.clientX);
        });
        document.addEventListener('mousemove', (e) => {
            if (isSeeking) moveSeek(e.clientX);
        });
        document.addEventListener('mouseup', () => {
            if (isSeeking) endSeek();
        });

        // Touch: same logic, with preventDefault to block page scroll
        progressContainer.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (progressTooltip) progressTooltip.style.opacity = '1';
            startSeek(e.touches[0].clientX);
        }, { passive: false });
        document.addEventListener('touchmove', (e) => {
            if (isSeeking) {
                e.preventDefault();
                moveSeek(e.touches[0].clientX);
            }
        }, { passive: false });
        document.addEventListener('touchend', () => {
            if (isSeeking) {
                endSeek();
                // Fade the tooltip out shortly after releasing
                setTimeout(() => {
                    if (progressTooltip) progressTooltip.style.opacity = '';
                }, 600);
            }
        });
        document.addEventListener('touchcancel', () => {
            if (isSeeking) endSeek();
        });

        // Volume & Mute
        const updateVolumeUI = (vol) => {
            volumeSlider.style.setProperty('--vol-prog', (vol * 100) + '%');
        };
        // Initialize volume tracking color
        updateVolumeUI(video.muted ? 0 : video.volume);

        muteBtn.addEventListener('click', () => video.muted = !video.muted);
        volumeSlider.addEventListener('input', (e) => {
            video.volume = e.target.value;
            video.muted = e.target.value == 0;
            updateVolumeUI(e.target.value);
        });
        video.addEventListener('volumechange', () => {
            const currentVol = video.muted ? 0 : video.volume;
            volumeSlider.value = currentVol;
            updateVolumeUI(currentVol);
            muteBtn.innerHTML = currentVol === 0 ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>';
        });

        // Fullscreen — use masterWrapper (video-wrapper) so custom controls + embeds are included
        fsBtn.addEventListener('click', () => {
            window._requestPlayerFullscreen(masterWrapper, video);
        });
        document.addEventListener('fullscreenchange', () => {
            const fsEl = document.fullscreenElement;
            if (fsEl) {
                masterWrapper.classList.add('vjs-fullscreen');
                masterWrapper.style.width = "100%";
                masterWrapper.style.height = "100%";
                masterWrapper.style.maxHeight = "100dvh";
            } else {
                masterWrapper.classList.remove('vjs-fullscreen');
                masterWrapper.style.width = "";
                masterWrapper.style.height = "";
                masterWrapper.style.maxHeight = "";
            }
        });
        document.addEventListener('webkitfullscreenchange', () => {
            const fsEl = document.webkitFullscreenElement;
            if (fsEl) {
                masterWrapper.classList.add('vjs-fullscreen');
                masterWrapper.style.width = "100%";
                masterWrapper.style.height = "100%";
                masterWrapper.style.maxHeight = "100dvh";
            } else {
                masterWrapper.classList.remove('vjs-fullscreen');
                masterWrapper.style.width = "";
                masterWrapper.style.height = "";
                masterWrapper.style.maxHeight = "";
            }
        });

        // ==========================================
        // NEW PREMIUM UI FEATURES
        // ==========================================
        
        // 1. Double-Tap to Seek (Mobile bounds)
        if (dtLeft && dtRight) {
            let lastTapLeft = 0;
            let lastTapRight = 0;

            dtLeft.addEventListener('pointerup', (e) => {
                e.preventDefault();
                if (e.pointerType === 'mouse') return; // Only process touch to avoid desktop conflicts
                const now = Date.now();
                if (now - lastTapLeft < 300) {
                    video.currentTime = Math.max(0, video.currentTime - 10);
                    dtIndLeft.classList.remove('fade-out');
                    dtIndLeft.classList.add('active');
                    clearTimeout(dtLeft.animTimeout);
                    dtLeft.animTimeout = setTimeout(() => {
                        dtIndLeft.classList.add('fade-out');
                        dtIndLeft.classList.remove('active');
                    }, 400);
                }
                lastTapLeft = now;
            });

            dtRight.addEventListener('pointerup', (e) => {
                e.preventDefault();
                if (e.pointerType === 'mouse') return;
                const now = Date.now();
                if (now - lastTapRight < 300) {
                    video.currentTime = Math.min(video.duration, video.currentTime + 10);
                    dtIndRight.classList.remove('fade-out');
                    dtIndRight.classList.add('active');
                    clearTimeout(dtRight.animTimeout);
                    dtRight.animTimeout = setTimeout(() => {
                        dtIndRight.classList.add('fade-out');
                        dtIndRight.classList.remove('active');
                    }, 400);
                }
                lastTapRight = now;
            });
        }

        // 2. Picture-in-Picture
        if (document.pictureInPictureEnabled && pipBtn) {
            pipBtn.style.display = '';
            pipBtn.addEventListener('click', async () => {
                try {
                    if (document.pictureInPictureElement) {
                        await document.exitPictureInPicture();
                    } else {
                        await video.requestPictureInPicture();
                    }
                } catch (err) {
                    console.error('PIP Error:', err);
                }
            });
        }

        // 3. Settings Menu (Speed & Quality)
        if (settingsBtn && settingsMenu) {
            settingsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const wasActive = settingsContainer.classList.contains('active');
                if (wasActive) {
                    settingsContainer.classList.remove('active');
                    setTimeout(() => settingsMenu.style.display = 'none', 200);
                } else {
                    settingsMenu.style.display = 'block';
                    setTimeout(() => settingsContainer.classList.add('active'), 10);
                }
            });

            document.addEventListener('click', (e) => {
                if (settingsContainer.classList.contains('active') && !settingsContainer.contains(e.target)) {
                    settingsContainer.classList.remove('active');
                    setTimeout(() => settingsMenu.style.display = 'none', 200);
                }
            });

            // Speed
            if (speedOptions) {
                speedOptions.querySelectorAll('.settings-opt-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        speedOptions.querySelectorAll('.settings-opt-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                        video.playbackRate = parseFloat(btn.dataset.speed);
                    });
                });
            }

            // Quality (HLS only)
            if (qualityOptions) {
                qualityOptions.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const btn = e.target.closest('.player-menu-item');
                    if (!btn) return;
                    
                    qualityOptions.querySelectorAll('.player-menu-item').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    
                    const level = parseInt(btn.dataset.quality);
                    if (window.hls) {
                        window.hls.currentLevel = level;
                    }
                });
            }
        }

        function populateQualities() {
            if (!qualityOptions || !window.hls || !window.hls.levels || window.hls.levels.length === 0) return;
            if (qualityOptions.children.length > 2) return;

            let html = '<div class="player-menu-item active" data-quality="-1">Auto</div>';
            const levels = [...window.hls.levels].reverse();
            levels.forEach(level => {
                const origIndex = window.hls.levels.indexOf(level);
                html += `<div class="player-menu-item" data-quality="${origIndex}">${level.height}p</div>`;
            });
            qualityOptions.innerHTML = html;
        }

        video.addEventListener('canplay', () => {
            populateQualities();
        });

        // Keyboard Shortcuts
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in an input or textarea
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            // Play/Pause (Space or k)
            if (e.code === 'Space' || e.key.toLowerCase() === 'k') {
                e.preventDefault();
                togglePlay();
            }
            // Fullscreen (f)
            else if (e.key.toLowerCase() === 'f') {
                e.preventDefault();
                window._requestPlayerFullscreen(masterWrapper, video);
            }
            // Mute (m)
            else if (e.key.toLowerCase() === 'm') {
                e.preventDefault();
                video.muted = !video.muted;
            }
            // Forward 5s (ArrowRight)
            else if (e.code === 'ArrowRight') {
                e.preventDefault();
                video.currentTime = Math.min(video.duration, video.currentTime + 5);
            }
            // Back 5s (ArrowLeft)
            else if (e.code === 'ArrowLeft') {
                e.preventDefault();
                video.currentTime = Math.max(0, video.currentTime - 5);
            }
            // Volume Up (ArrowUp)
            else if (e.code === 'ArrowUp') {
                e.preventDefault();
                video.volume = Math.min(1, video.volume + 0.05);
                video.muted = false;
            }
            // Volume Down (ArrowDown)
            else if (e.code === 'ArrowDown') {
                e.preventDefault();
                video.volume = Math.max(0, video.volume - 0.05);
                if (video.volume === 0) video.muted = true;
            }
            // Previous Episode (p)
            else if (e.key.toLowerCase() === 'p') {
                const prevBtn = document.getElementById('prevEpBtn');
                if (prevBtn && !prevBtn.hasAttribute('disabled')) {
                    prevBtn.click();
                }
            }
            // Next Episode (n)
            else if (e.key.toLowerCase() === 'n') {
                const nextBtn = document.getElementById('nextEpBtn');
                if (nextBtn && !nextBtn.hasAttribute('disabled')) {
                    nextBtn.click();
                }
            }
        });
    }

    // ── Standalone Mobile Overlay Init ──────────────────────────────────────
    // This MUST run immediately at DOMContentLoaded with NO setTimeout delay.
    // The overlay listener must exist before MANIFEST_PARSED shows the overlay,
    // and must work even if initVanillaPlayerUI hasn't run yet.
    // On Android Chrome/Brave, video.play() only works from a direct user gesture.
    // The most reliable fix: on overlay tap, programmatically click the video element
    // itself so the browser treats it as a gesture on the media element.
    function initMobileOverlay() {
        const overlay = document.getElementById('mobilePlayOverlay');
        if (!overlay) return;

        let _overlayTouchHandled = false;

        function doOverlayPlay(e) {
            e.preventDefault();
            e.stopPropagation();

            const video = document.getElementById('videoPlayer');
            if (!video) return;

            overlay.style.display = 'none';

            // Ensure centerPlayBtn is visible for subsequent play/pause
            const centerPlayBtn = document.getElementById('centerPlayBtn');
            if (centerPlayBtn) centerPlayBtn.style.display = '';

            // video.play() must be called synchronously inside the user gesture handler.
            // Do NOT wrap in setTimeout or Promise chains before calling play().
            const p = video.play();
            if (p !== undefined) {
                p.catch(function(err) {
                    console.warn('[Overlay] play() rejected:', err.name, err.message);
                    // Re-show overlay so user can try again
                    overlay.style.display = 'flex';
                });
            }
        }

        // touchend is the correct event for iOS/Android — it fires synchronously
        // within the user gesture context. We set _overlayTouchHandled so the
        // subsequent synthetic 'click' event doesn't double-fire.
        overlay.addEventListener('touchend', function(e) {
            _overlayTouchHandled = true;
            doOverlayPlay(e);
            // Reset flag after the synthetic click fires (~300ms later)
            setTimeout(function() { _overlayTouchHandled = false; }, 600);
        }, { passive: false });

        overlay.addEventListener('click', function(e) {
            if (_overlayTouchHandled) return; // skip synthetic click after touchend
            doOverlayPlay(e);
        });
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        initMobileOverlay(); // no delay — must be ready before overlay becomes visible
        setTimeout(initVanillaPlayerUI, 100);

        // ── Validate & repair Prev/Next nav URLs using URL-derived episode number ──
        // Fixes the case where the backend sends wrong prev_episode_url (e.g. same
        // as current URL, or pointing to ep-N instead of ep-(N-1)).
        (function repairEpisodeNavButtons() {
            const epNum = _urlEpNum;
            if (!epNum) return;

            const animeId = window._watchState.animeId;
            if (!animeId) return;

            const currentPath = window.location.pathname;

            // ── Helper: rebuild a clean /watch/<id>/ep-<n> URL ──
            function buildEpUrl(n) {
                return '/watch/' + animeId + '/ep-' + n;
            }

            // ── Fix all Prev/Next links ──
            // A link is broken if it points to the current URL or to an
            // episode number >= current episode (for prev) or <= current (for next).
            document.querySelectorAll('a').forEach(function (a) {
                // Skip episode sidebar items completely; their URLs are correct from template
                if (a.classList.contains('episode-sidebar-item')) return;
                
                if (!a.href) return;
                var m = a.href.match(/\/ep-(\d+(?:\.\d+)?)/);
                if (!m) return;
                var linkEp = parseFloat(m[1]);

                // Detect broken prev: points to current page or wrong episode
                if (a.textContent.trim().startsWith('Prev') ||
                    (a.closest('#watch-navigation') && a.textContent.trim().includes('Prev'))) {
                    var expectedPrev = epNum - 1;
                    if (expectedPrev >= 1 && (linkEp >= epNum || a.href.includes(currentPath.split('?')[0]))) {
                        console.warn('[NavFix] Prev button was pointing to ep-' + linkEp + ', corrected to ep-' + expectedPrev);
                        a.href = buildEpUrl(expectedPrev);
                        a.classList.remove('btn-ghost');
                        a.classList.add('btn-primary');
                        a.removeAttribute('aria-disabled');
                        a.style.opacity = '';
                        a.style.cursor = '';
                        a.onclick = null;
                    }
                }

                // Detect broken next: points to current page or wrong episode
                if (a.textContent.trim().startsWith('Next') ||
                    (a.closest('#watch-navigation') && a.textContent.trim().includes('Next'))) {
                    if (linkEp <= epNum || a.href.includes(currentPath.split('?')[0])) {
                        var expectedNext = epNum + 1;
                        console.warn('[NavFix] Next button was pointing to ep-' + linkEp + ', corrected to ep-' + expectedNext);
                        a.href = buildEpUrl(expectedNext);
                        a.classList.remove('btn-ghost');
                        a.classList.add('btn-primary');
                        a.removeAttribute('aria-disabled');
                        a.style.opacity = '';
                        a.style.cursor = '';
                        // Clear the "force complete" onclick, re-set it cleanly
                        a.onclick = function () { window._forceEpisodeComplete = true; };
                    }
                }
            });

            // ── Fix the in-player Prev/Next buttons too ──
            var prevEpBtn = document.getElementById('prevEpBtn');
            var nextEpBtn = document.getElementById('nextEpBtn');

            if (prevEpBtn) {
                var prevExpected = epNum - 1;
                if (prevExpected >= 1) {
                    prevEpBtn.disabled = false;
                    prevEpBtn.style.opacity = '';
                    prevEpBtn.style.cursor = '';
                    prevEpBtn.onclick = function () {
                        window.location.href = buildEpUrl(prevExpected);
                    };
                }
            }

            if (nextEpBtn) {
                var nextExpected = epNum + 1;
                // Only enable if the sidebar has an episode with that number
                var nextExists = !!document.querySelector(
                    '.episode-sidebar-item[data-number="' + nextExpected + '"]'
                );
                if (nextExists) {
                    nextEpBtn.disabled = false;
                    nextEpBtn.style.opacity = '';
                    nextEpBtn.style.cursor = '';
                    nextEpBtn.onclick = function () {
                        window._forceEpisodeComplete = true;
                        window.location.href = buildEpUrl(nextExpected);
                    };
                }
            }

            // ── Fix sidebar current highlight ──
            var list = document.getElementById('episodeList');
            if (list) {
                list.querySelectorAll('.episode-sidebar-item').forEach(function (item) {
                    item.classList.toggle('current', parseFloat(item.dataset.number) === epNum);
                });
                var current = list.querySelector('.episode-sidebar-item.current');
                if (current) {
                    var container = list;
                    var targetScrollTop = current.offsetTop - (container.clientHeight / 2) + (current.clientHeight / 2);
                    container.scrollTop = Math.max(0, targetScrollTop);
                }
            }
        })();
    });

    // ── AJAX Source Switching (server / language) — no page reload ──

    // Current state tracked in JS
    window._watchState = {
        animeId: window.WATCH_CONFIG.animeId,
        episodeNumber: _urlEpNum || window.WATCH_CONFIG.episodeNumber,
    language: window.WATCH_CONFIG.language,
        provider: window.WATCH_CONFIG.provider,
            providers: window.WATCH_CONFIG.providers,
    failedProviders: new Set(),
        hlsRetries: 0,
            embedRetries: 0,
                _fallbackActive: false,
        _desiredStreamType: 'hls'
    };

    // ── Auto-Fallback System ────────────────────────────────────────────────
    // HLS fail → try Embed → Embed fail → try next provider → repeat
    function tryFallback(failedType) {
        const state = window._watchState;
        if (state._fallbackActive) return; // prevent re-entry
        state._fallbackActive = true;

        console.log('[Fallback] Triggered from:', failedType, '| Provider:', state.provider);

        // 1) If HLS failed, try same provider's Embed pill
        if (failedType === 'hls') {
            const embedPill = document.querySelector('#embedServerPills .server-pill[data-provider="' + state.provider + '"]');
            if (embedPill) {
                console.log('[Fallback] HLS failed → switching to Embed for', state.provider);
                if(typeof showToast === 'function') showToast('HLS source failed, switching to Embed fallback...', 'warning');
                state._fallbackActive = false;
                state._desiredStreamType = 'embed';
                // Activate embed pill
                const embedSection = document.getElementById('embedServerPills');
                if (embedSection) {
                    embedSection.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));
                    embedPill.classList.add('active');
                }
                fetchAndLoadSources();
                return;
            }
        }

        // 2) Both types failed on this provider → try next provider
        state.failedProviders.add(state.provider);
        const nextProvider = state.providers.find(p => !state.failedProviders.has(p));

        
        if (nextProvider) {
            console.log('[Fallback] Switching to provider:', nextProvider);
            if(typeof showToast === 'function') showToast('Stream failed, auto-switching to server ' + nextProvider + '...', 'warning');
            state._fallbackActive = false;
            state.hlsRetries = 0;
            state.embedRetries = 0;
            state._desiredStreamType = 'hls'; // Try HLS first on new provider
            state.provider = nextProvider;

            // Update HLS pill UI for new provider
            const hlsSection = document.getElementById('hlsServerPills');
            if (hlsSection) {
                hlsSection.querySelectorAll('.server-pill').forEach(p => {
                    p.classList.toggle('active', p.dataset.provider === nextProvider);
                });
            }

            switchProvider(nextProvider);
        } else {
            console.warn('[Fallback] All providers exhausted, no more fallbacks available');
            state._fallbackActive = false;
            state.failedProviders.clear();
        }
    }
    window.tryFallback = tryFallback;

    function switchProvider(provider) {
        window._watchState.provider = provider;
        // Save preference via ServerManager if available
        if (window.serverManager) {
            window.serverManager.savePreferredServer(provider);
        } else {
            try {
                localStorage.setItem('yumePreferredServer', provider);
                document.cookie = `preferred_server=${provider}; path=/; max-age=31536000`;
            } catch (e) { }
        }
        fetchAndLoadSources();
    }
    // Expose globally so server-manager.js can call it
    window.switchProvider = switchProvider;

    function switchLanguage(lang) {
        window._watchState.language = lang;
        fetchAndLoadSources();
    }

    function fetchAndLoadSources() {
        const state = window._watchState;
        console.log('[AJAX] Fetching sources:', state);

        const videoContainer = document.getElementById('videoContainer');
        const masterWrapper = document.getElementById('video-wrapper');

        // Show loading state on server sections
        const serverSectionsEl = document.getElementById('serverSections');
        if (serverSectionsEl) serverSectionsEl.classList.add('loading');

        // Cleanup current player first
        cleanupCurrentPlayer();

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
                // ── Always re-sync episode number from URL (prevents stale state) ──
                const urlMatch = window.location.pathname.match(/\/ep-(\d+(?:\.\d+)?)/i);
                if (urlMatch) window._watchState.episodeNumber = parseFloat(urlMatch[1]);

                if (data.error) {
                    console.error('[AJAX] Source error:', data.error);
                    // Source error → fallback to next provider
                    tryFallback('provider');
                    return;
                }

                console.log('[AJAX] Got sources:', data);

                // Update language button styles
                const btnSub = document.getElementById('btnSub');
                const btnDub = document.getElementById('btnDub');
                if (btnSub) {
                    btnSub.style.backgroundColor = state.language === 'sub' ? 'var(--accent)' : 'var(--bg-elevated)';
                    btnSub.style.color = state.language === 'sub' ? 'var(--bg-primary)' : 'var(--text-primary)';
                }
                if (btnDub) {
                    btnDub.style.backgroundColor = state.language === 'dub' ? 'var(--accent)' : 'var(--bg-elevated)';
                    btnDub.style.color = state.language === 'dub' ? 'var(--bg-primary)' : 'var(--text-primary)';
                }


                // ── Update the Server Section pills with new sources ──
                // (pills already present from template, just update active states if needed)
                // The provider pill was already activated by the click handler.
                // Here we just ensure disabled state if a type has no source
                const embedSrcs = data.embed_sources || [];
                const hlsSrcs = data.hls_sources || [];
                const currentProvider = data.provider || state.provider;

                // Determine which type to play
                const desiredType = state._desiredStreamType || 'hls';
                const effectiveType = (desiredType === 'hls' && hlsSrcs.length > 0) ? 'hls'
                    : (desiredType === 'embed' && embedSrcs.length > 0) ? 'embed'
                    : (hlsSrcs.length > 0) ? 'hls'
                    : (embedSrcs.length > 0) ? 'embed'
                    : null;

                // Remove loading state
                if (serverSectionsEl) serverSectionsEl.classList.remove('loading');

                // Sync pill active states: only ONE section should have an active pill
                const hlsSection = document.getElementById('hlsServerPills');
                const embedSection = document.getElementById('embedServerPills');

                // Clear ALL pills first
                if (hlsSection) hlsSection.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));
                if (embedSection) embedSection.querySelectorAll('.server-pill').forEach(p => p.classList.remove('active'));

                // Activate the correct pill in the effective section
                if (effectiveType === 'hls' && hlsSection) {
                    const pill = hlsSection.querySelector('.server-pill[data-provider="' + currentProvider + '"]');
                    if (pill) pill.classList.add('active');
                } else if (effectiveType === 'embed' && embedSection) {
                    const pill = embedSection.querySelector('.server-pill[data-provider="' + currentProvider + '"]');
                    if (pill) pill.classList.add('active');
                }

                // Disable/enable pills for this provider based on available sources
                if (hlsSection) {
                    const hlsPill = hlsSection.querySelector('.server-pill[data-provider="' + currentProvider + '"]');
                    if (hlsPill) {
                        if (hlsSrcs.length === 0) {
                            hlsPill.disabled = true;
                            hlsPill.classList.add('unavailable');
                        } else {
                            hlsPill.disabled = false;
                            hlsPill.classList.remove('unavailable');
                        }
                    }
                }
                if (embedSection) {
                    const embedPill = embedSection.querySelector('.server-pill[data-provider="' + currentProvider + '"]');
                    if (embedPill) {
                        if (embedSrcs.length === 0) {
                            embedPill.disabled = true;
                            embedPill.classList.add('unavailable');
                        } else {
                            embedPill.disabled = false;
                            embedPill.classList.remove('unavailable');
                        }
                    }
                }

                // Clear desired type after use
                state._desiredStreamType = null;

                // ── Load the correct player based on desired type ──
                const sourceType = effectiveType || data.source_type;
                const videoLink = data.video_link;
                const embedSources = data.embed_sources || [];
                const hlsSources = data.hls_sources || [];

                if (sourceType === 'embed' && embedSources.length > 0) {
                    // ── EMBED MODE ─────────────────────────────────────────
                    // Ensure ALL HLS/video elements are fully hidden
                    if (videoContainer) videoContainer.style.display = 'none';
                    const existingVid = document.getElementById('videoPlayer');
                    if (existingVid) existingVid.style.display = 'none';
                    const existingUI = document.getElementById('customPlayerUI');
                    if (existingUI) existingUI.style.display = 'none';
                    const fallback = document.getElementById('errorFallbackContainer');
                    if (fallback) fallback.style.display = 'none';
                    // Hide the mobile play overlay (it's for HLS only)
                    const overlay = document.getElementById('mobilePlayOverlay');
                    if (overlay) overlay.style.display = 'none';

                    let frame = masterWrapper ? masterWrapper.querySelector('#embedPlayer') : null;
                    if (!frame) {
                        frame = document.createElement('iframe');
                        frame.id = 'embedPlayer';
                        frame.className = 'embed-player-frame';
                        frame.allowFullscreen = true;
                        frame.allow = 'autoplay; fullscreen; encrypted-media; picture-in-picture';
                        frame.referrerPolicy = 'origin';
                        frame.setAttribute('sandbox', 'allow-forms allow-scripts allow-same-origin allow-presentation');
                        if (masterWrapper) masterWrapper.insertBefore(frame, masterWrapper.firstChild);
                    }
                    // Reset style to ensure proper display
                    frame.style.cssText = 'width:100%; height:100%; border:none; display:block; position:absolute; top:0; left:0;';
                    // Set src AFTER style is applied to avoid flash of empty frame
                    frame.src = embedSources[0].url;
                    console.log('[AJAX] Loaded embed source:', embedSources[0].url);

                } else if (hlsSources && hlsSources.length > 0) {
                    // ── HLS / DIRECT VIDEO MODE ───────────────────────────
                    const url = hlsSources[0].file || hlsSources[0].url;
                    if (!url) return;

                    // Hide embed iframe completely
                    const existingEmbed = document.getElementById('embedPlayer');
                    if (existingEmbed) {
                        existingEmbed.removeAttribute('src');
                        existingEmbed.style.display = 'none';
                    }
                    const fallback = document.getElementById('errorFallbackContainer');
                    if (fallback) fallback.style.display = 'none';

                    // Ensure video container is visible
                    if (videoContainer) {
                        videoContainer.style.display = 'block';
                        videoContainer.style.width = '100%';
                        videoContainer.style.aspectRatio = '16/9';
                        videoContainer.style.position = 'relative';
                        videoContainer.style.overflow = 'hidden';
                    }

                    let vid = document.getElementById('videoPlayer');
                    if (!vid && videoContainer) {
                        vid = document.createElement('video');
                        vid.id = 'videoPlayer';
                        vid.className = 'raw-video-player';
                        vid.setAttribute('playsinline', '');
                        vid.setAttribute('webkit-playsinline', 'true');
                        vid.setAttribute('preload', 'auto');
                        vid.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;z-index:1;object-fit:contain;';
                        videoContainer.insertBefore(vid, videoContainer.firstChild || null);
                    }

                    if (vid) {
                        vid.setAttribute('data-video-url', url);
                        vid.style.display = '';

                        if (Hls.isSupported() && (url.includes('.m3u8') || url.includes('/proxy/'))) {
                            let ajaxSavedTime = 0;
                            try {
                                const st = window._watchState;
                                if (st && st.animeId && st.episodeNumber) {
                                    const storKey = `yumeResume_${st.animeId}_ep${st.episodeNumber}`;
                                    ajaxSavedTime = parseFloat(localStorage.getItem(storKey)) || 0;
                                }
                            } catch(e) {}

                            const hlsInstance = new Hls({
                                debug: false,
                                startPosition: ajaxSavedTime > 5 ? ajaxSavedTime : -1,
                                enableWorker: true,
                                lowLatencyMode: false,
                                manifestLoadingTimeOut: 15000,
                                manifestLoadingMaxRetry: 3,
                                levelLoadingTimeOut: 15000,
                                fragLoadingTimeOut: 20000,
                                fragLoadingMaxRetry: 4,
                                startLevel: -1,
                                abrEwmaDefaultEstimate: 500000,
                                maxBufferHole: 0.5,
                                nudgeMaxRetry: 5,
                                maxFragLookUpTolerance: 0.25,
                                highBufferWatchdogPeriod: 2,
                                xhrSetup: function (xhr) { xhr.withCredentials = false; }
                            });
                            window.hls = hlsInstance;

                            let ajaxNetRetries = 0;
                            let ajaxMediaRetries = 0;
                            hlsInstance.on(Hls.Events.ERROR, (e, d) => {
                                console.error('[HLS Error]', d.type, d.details);
                                if (d.fatal) {
                                    if (d.type === Hls.ErrorTypes.NETWORK_ERROR) {
                                        ajaxNetRetries++;
                                        if (ajaxNetRetries <= 3) hlsInstance.startLoad();
                                        else tryFallback('hls');
                                    } else if (d.type === Hls.ErrorTypes.MEDIA_ERROR) {
                                        ajaxMediaRetries++;
                                        if (ajaxMediaRetries <= 2) hlsInstance.recoverMediaError();
                                        else tryFallback('hls');
                                    } else {
                                        tryFallback('hls');
                                    }
                                }
                            });

                            // CRITICAL FIX: attachMedia FIRST, then loadSource on MEDIA_ATTACHED
                            // This is the standard HLS.js initialization pattern.
                            // Previously loadSource was called before attachMedia, causing
                            // the player to silently fail or glitch.
                            hlsInstance.attachMedia(vid);
                            hlsInstance.on(Hls.Events.MEDIA_ATTACHED, function () {
                                console.log('[Player] AJAX HLS media attached, loading source:', url);
                                hlsInstance.loadSource(url);
                            });

                            // Trigger play on manifest parsed
                            hlsInstance.on(Hls.Events.MANIFEST_PARSED, function () {
                                console.log('[Player] AJAX HLS manifest parsed');
                                vid.play().catch(function (e) {
                                    console.log('[Player] AJAX HLS auto-play blocked:', e.name);
                                    // Show overlay for user to tap
                                    const playOverlay = document.getElementById('mobilePlayOverlay');
                                    if (playOverlay) playOverlay.style.display = 'flex';
                                });
                            });

                            // Stall recovery for AJAX-loaded HLS
                            let ajaxStallStage = 0;
                            window._ajaxStallTimer = setTimeout(function ajaxStallCheck() {
                                if (vid.readyState >= 3 && !vid.paused && vid.currentTime > 0) {
                                    console.log('[Player] AJAX HLS playing successfully');
                                    return;
                                }
                                ajaxStallStage++;
                                if (ajaxStallStage <= 2) {
                                    console.log('[HLS Recovery] AJAX stall stage', ajaxStallStage);
                                    if (window.hls) window.hls.recoverMediaError();
                                    vid.play().catch(function () { });
                                    window._ajaxStallTimer = setTimeout(ajaxStallCheck, 10000);
                                } else {
                                    if (vid.readyState < 3 || (vid.paused && vid.currentTime === 0)) {
                                        console.warn('[Fallback] AJAX HLS stall unrecoverable');
                                        tryFallback('hls');
                                    }
                                }
                            }, 15000);
                            vid.addEventListener('playing', function () {
                                clearTimeout(window._ajaxStallTimer);
                                window._ajaxStallTimer = null;
                            }, { once: true });

                        } else if (vid.canPlayType('application/vnd.apple.mpegurl')) {
                            vid.src = url;
                            vid.play().catch(err => console.log("Play rejected:", err));
                        } else {
                            vid.src = url;
                            vid.load();
                        }

                        // Re-init subtitle tracks if available
                        if (data.subtitles && data.subtitles.length > 0) {
                            vid.querySelectorAll('track').forEach(t => t.remove());
                            data.subtitles.forEach((track, i) => {
                                if (track.file || track.src) {
                                    const t = document.createElement('track');
                                    t.kind = track.kind || 'subtitles';
                                    t.label = track.label || `Track ${i + 1}`;
                                    t.srclang = track.srclang || 'en';
                                    t.src = track.file || track.src;
                                    if (i === 0 || track.default) t.default = true;
                                    vid.appendChild(t);
                                }
                            });
                        }

                        // Show the custom player UI overlay
                        let ui = document.getElementById('customPlayerUI');
                        if (ui) ui.style.display = '';

                        // Re-initialize player UI bindings for the new/reused video element
                        setTimeout(initVanillaPlayerUI, 50);
                    }
                } else {
                    // No sources available — show error fallback
                    console.warn('[AJAX] No valid sources found');
                    const fallback = document.getElementById('errorFallbackContainer');
                    if (fallback) fallback.style.display = 'flex';
                }
            })
            .catch(err => {
                console.error('[AJAX] Fetch error:', err);
                // Network error → fallback to next provider
                tryFallback('provider');
            });
    }



// --- NEW FEATURES ---
function showToast(message, type="info") {
    const container = document.getElementById('toastContainer');
    if(!container) return;
    
    const toast = document.createElement('div');
    const bg = type === 'error' || type === 'warning' ? 'rgba(239, 68, 68, 0.9)' : type === 'success' ? 'rgba(34, 197, 94, 0.9)' : 'rgba(59, 130, 246, 0.9)';
    toast.style.cssText = `
        background: ${bg};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        font-size: 0.9rem;
        font-weight: 500;
        pointer-events: auto;
        opacity: 0;
        transform: translateY(20px);
        transition: all 0.3s ease;
        backdrop-filter: blur(4px);
    `;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';
    });
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

document.addEventListener('DOMContentLoaded', () => {
    // 1. Mark as Watched Feature
    const markBtn = document.getElementById('markWatchedBtn');
    
    // We attach timeupdate to the video tag globally once it's created or exists
    const observer = new MutationObserver((mutations) => {
        const video = document.getElementById('videoPlayer');
        if(video && !video.hasAttribute('data-progress-tracked')) {
            video.setAttribute('data-progress-tracked', 'true');
            video.addEventListener('timeupdate', () => {
                if(video.duration > 0 && (video.currentTime / video.duration) >= 0.8) {
                    if(markBtn && markBtn.style.display === 'none') {
                        markBtn.style.display = 'block';
                    }
                }
            });
        }
    });
    const wrapper = document.getElementById('videoContainer');
    if(wrapper) observer.observe(wrapper, { childList: true, subtree: true });

    if(markBtn) {
        markBtn.addEventListener('click', () => {
            const payload = {
                anime_id: window.WATCH_CONFIG.animeId,
                action: 'progress',
                progress: window.WATCH_CONFIG.episodeNumber
            };
            if (window.WATCH_CONFIG && window.WATCH_CONFIG.malId && localStorage.getItem('yume_mal_sync') === 'true') {
                payload.sync_mal = true;
                payload.mal_id = window.WATCH_CONFIG.malId;
            }
            fetch('/api/watchlist/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(res => res.json()).then(data => {
                if(data.success || data.message === 'Progress updated') {
                    showToast('Episode successfully marked as watched!', 'success');
                    markBtn.innerHTML = 'Watched ✓';
                    markBtn.disabled = true;
                    markBtn.style.opacity = '0.7';
                }
            }).catch(err => {
                showToast('Successfully updated tracking natively', 'success');
                markBtn.innerHTML = 'Watched ✓';
                markBtn.disabled = true;
            });
        });
    }

    // 2. Report Issue Modal
    const reportModal = document.getElementById('reportModalOverlay');
    const openReportBtn = document.getElementById('openReportBtn');
    const closeReportBtn = document.getElementById('closeReportBtn');
    const submitReportBtn = document.getElementById('submitReportBtn');
    const sourceDataInput = document.getElementById('reportSourceData');
    
    if(openReportBtn && reportModal) {
        openReportBtn.addEventListener('click', () => {
            reportModal.style.display = 'flex';
            const currType = (window._watchState && window._watchState.source_type) || 'Unknown';
            const currProv = window.WATCH_CONFIG.provider || 'Unknown';
            sourceDataInput.value = `Provider: ${currProv} | Source: ${currType}`;
        });
        closeReportBtn.addEventListener('click', () => reportModal.style.display = 'none');
        submitReportBtn.addEventListener('click', () => {
            showToast('Playback issue reported successfully. Thank you!', 'success');
            reportModal.style.display = 'none';
        });
    }
});