(function () {
    var cfg = window.WT_ROOM_CONFIG || {};
    var room = cfg.room || {};
    var video = null;
    var hls = null;
    var clientIdValue = null;
    var displayName = '';
    var sinceChatSeq = 0;
    var lastPlaybackSeq = 0;
    var currentProvider = room.provider || '';
    var pollTimer = null;
    var heartbeatTimer = null;
    var applyingRemote = false;
    var sourceLoading = false;
    var failedProviders = {};
    var intro = null;
    var outro = null;
    var skipTarget = null;
    var isHost = false;

    /* ── Formatting ── */
    function fmt(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        return h ? h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') : m + ':' + String(s).padStart(2, '0');
    }

    /* ── Identity helpers ── */
    function clientId() {
        if (clientIdValue) return clientIdValue;
        try {
            var stored = localStorage.getItem('yume_watch_together_client_id') || localStorage.getItem('yumeWatchTogetherClientId');
            if (stored) {
                clientIdValue = stored;
                localStorage.setItem('yume_watch_together_client_id', stored);
                return stored;
            }
            clientIdValue = 'wt_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
            localStorage.setItem('yume_watch_together_client_id', clientIdValue);
            localStorage.setItem('yumeWatchTogetherClientId', clientIdValue);
            return clientIdValue;
        } catch (e) {
            clientIdValue = 'wt_' + Math.random().toString(36).slice(2);
            return clientIdValue;
        }
    }

    function getDisplayName() {
        if (cfg.isLoggedIn && cfg.username) return cfg.username;
        if (displayName) return displayName;
        try { displayName = localStorage.getItem('yume_watch_together_name') || localStorage.getItem('yumeWatchTogetherName') || ''; }
        catch (e) { displayName = ''; }
        return displayName;
    }

    /* ── UI helpers ── */
    function setStatus(text) {
        var el = document.getElementById('wt-sync-status');
        if (el) el.textContent = text || 'Syncing';
    }

    function setLoading(text, show) {
        var el = document.getElementById('wt-loading');
        if (!el) return;
        el.textContent = text || 'Loading HLS';
        el.classList.toggle('is-hidden', show === false);
    }

    /* ── Host / guest control enforcement ── */
    function updateHostState(roomData) {
        var previousHost = isHost;
        isHost = (clientId() === roomData.host_id);

        if (!video) return;

        // Everyone gets native controls (fullscreen, volume, etc.)
        video.controls = true;

        // Manage the guest badge (small non-blocking indicator)
        var overlay = document.getElementById('wt-guest-overlay');
        if (!isHost) {
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'wt-guest-overlay';
                overlay.className = 'wt-guest-overlay';
                overlay.innerHTML = '<span class="wt-guest-overlay-icon">🔒</span><span>Host controls playback</span>';
                var wrap = document.querySelector('.wt-player-wrap');
                if (wrap) wrap.appendChild(overlay);
            }
            overlay.classList.remove('is-hidden');
        } else if (overlay) {
            overlay.classList.add('is-hidden');
        }

        // Provider pills: disable for non-hosts
        var pills = document.querySelectorAll('.wt-provider-pill');
        pills.forEach(function (pill) {
            pill.disabled = !isHost;
            pill.style.pointerEvents = isHost ? '' : 'none';
            pill.style.opacity = isHost ? '' : '0.5';
        });

        // Skip button: only host can skip
        var skip = document.getElementById('wt-skip');
        if (skip) {
            skip.style.display = isHost ? '' : 'none';
        }

        // If host status changed, show a brief status
        if (previousHost !== isHost && previousHost !== false) {
            setStatus(isHost ? 'You are the host' : 'Host controls playback');
        }
    }

    /* ── Network helpers ── */
    function payload(type, extra) {
        var base = {
            type: type,
            client_id: clientId(),
            display_name: getDisplayName(),
            position: video ? video.currentTime || 0 : 0,
            duration: video && Number.isFinite(video.duration) ? video.duration : 0,
            paused: video ? video.paused : true,
            rate: video ? video.playbackRate || 1 : 1,
            since_chat_seq: sinceChatSeq
        };
        return Object.assign(base, extra || {});
    }

    function postEvent(type, extra) {
        return fetch('/api/watch-together/rooms/' + encodeURIComponent(room.room_id) + '/events', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload(type, extra))
        })
        .then(function (response) {
            return response.json().then(function (data) {
                if (!response.ok || !data.success) throw data;
                // Keep client_id in sync with server
                if (data.client_id && data.client_id !== clientIdValue) {
                    clientIdValue = data.client_id;
                    try { localStorage.setItem('yume_watch_together_client_id', data.client_id); } catch (e) {}
                }
                return data;
            });
        })
        .then(function (data) {
            if (data.room) applySnapshot(data.room);
            return data;
        })
        .catch(function (error) {
            // Friendly messages instead of raw API errors
            if (error && error.message && error.message.indexOf('host') !== -1) {
                setStatus('Host controls playback');
            } else {
                // Don't show confusing raw errors to users
                setStatus('Sync paused');
            }
            throw error;
        });
    }

    /* ── Provider labels ── */
    function providerLabel(provider) {
        var names = {
            'kiwi': 'Miku',
            'ax-mimi': 'Shinra',
            'ax-wave': 'Nami',
            'ax-shiro': 'Shiro',
            'ax-yuki': 'Yuki',
            'ax-zen': 'Senku',
            'bee': 'Hachi'
        };
        return names[provider] || provider;
    }

    function renderProviders(roomData) {
        var wrap = document.getElementById('wt-provider-pills');
        if (!wrap) return;
        wrap.innerHTML = '';
        (roomData.hls_providers || []).forEach(function (provider) {
            var button = document.createElement('button');
            button.className = 'wt-provider-pill' + (provider === roomData.provider ? ' active' : '');
            button.type = 'button';
            button.textContent = providerLabel(provider);
            button.dataset.provider = provider;
            // Only host can switch providers
            button.disabled = !isHost;
            button.style.pointerEvents = isHost ? '' : 'none';
            button.style.opacity = isHost ? '' : '0.5';
            button.addEventListener('click', function () {
                if (!isHost) return;
                if (provider === currentProvider) return;
                postEvent('server_change', { provider: provider });
            });
            wrap.appendChild(button);
        });
    }

    function renderMembers(roomData) {
        var members = document.getElementById('wt-members');
        var count = document.getElementById('wt-member-count');
        if (count) count.textContent = String((roomData.members || []).length);
        if (!members) return;
        members.innerHTML = '';
        (roomData.members || []).forEach(function (member) {
            var item = document.createElement('div');
            item.className = 'wt-member' + (member.is_host ? ' host' : '');
            var text = document.createElement('span');
            var label = member.name + (member.is_self ? ' (You)' : '');
            if (member.is_host) label += ' ★';
            text.textContent = label;
            item.appendChild(text);
            members.appendChild(item);
        });
    }

    function appendMessages(messages) {
        if (!messages || !messages.length) return;
        var list = document.getElementById('wt-chat-list');
        var count = document.getElementById('wt-chat-count');
        if (!list) return;
        messages.forEach(function (message) {
            if (message.seq <= sinceChatSeq) return;
            sinceChatSeq = message.seq;
            var item = document.createElement('div');
            item.className = 'wt-chat-message' + (message.is_system ? ' wt-chat-system' : '');
            var head = document.createElement('div');
            head.className = 'wt-chat-author';
            var author = document.createElement('span');
            author.textContent = message.author || 'Guest';
            var time = document.createElement('span');
            time.className = 'wt-chat-time';
            time.textContent = message.created_at ? new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
            var body = document.createElement('div');
            body.className = 'wt-chat-body';
            body.textContent = message.body || '';
            head.appendChild(author);
            head.appendChild(time);
            item.appendChild(head);
            item.appendChild(body);
            list.appendChild(item);
        });
        while (list.children.length > 200) list.removeChild(list.firstElementChild);
        if (count) count.textContent = String(list.children.length);
        list.scrollTop = list.scrollHeight;
    }


    /* ── Playback sync ── */
    function effectivePosition(playback, serverTime) {
        var position = Number(playback.position || 0);
        var rate = Number(playback.rate || 1);
        if (!playback.paused && playback.updated_at && serverTime) {
            position += Math.max(0, Number(serverTime) - Number(playback.updated_at)) * rate;
        }
        return position;
    }

    function applyPlayback(playback, serverTime, force) {
        if (!video || !playback) return;
        if (!force && playback.seq <= lastPlaybackSeq) return;
        lastPlaybackSeq = playback.seq;

        // Host originated this event — no need to re-apply to host
        if (playback.updated_by === clientId() && !force) return;

        var target = effectivePosition(playback, serverTime);
        if (Number.isFinite(video.duration) && video.duration > 0) {
            target = Math.min(target, Math.max(0, video.duration - 0.2));
        }

        applyingRemote = true;
        try {
            // Sync playback rate
            if (Math.abs((video.playbackRate || 1) - (playback.rate || 1)) > 0.01) {
                video.playbackRate = playback.rate || 1;
            }

            var drift = Math.abs((video.currentTime || 0) - target);

            // TIGHTER thresholds for faster sync:
            // Hard seek if drift > 0.8s (was 1.25s) or on explicit seek/force
            if (drift > 0.8 || playback.event === 'seek' || force) {
                video.currentTime = target;
            }
            // Soft correction: gentle speed nudge for 0.3s–0.8s drift (was 0.45s–1.25s)
            else if (!playback.paused && drift > 0.3) {
                var direction = (video.currentTime || 0) < target ? 1 : -1;
                video.playbackRate = Math.max(0.8, Math.min(1.2, (playback.rate || 1) + direction * 0.08));
                setTimeout(function () {
                    if (video && !applyingRemote) video.playbackRate = playback.rate || 1;
                }, 1200);
            }

            // Sync play/pause state
            if (playback.paused) {
                if (!video.paused) video.pause();
            } else if (video.paused) {
                video.play().catch(function () {
                    setStatus('Tap play to sync');
                });
            }
        } finally {
            // Shorter guard window (200ms, was 600ms) so next poll can correct faster
            setTimeout(function () { applyingRemote = false; }, 200);
        }
    }

    function applySnapshot(roomData) {
        if (!roomData) return;
        room = roomData;
        updateHostState(roomData);
        renderMembers(roomData);
        renderProviders(roomData);
        appendMessages(roomData.messages || []);
        if (roomData.provider && roomData.provider !== currentProvider) {
            currentProvider = roomData.provider;
            loadSource(true);
        }
        applyPlayback(roomData.playback, roomData.server_time, false);
        var by = roomData.playback && roomData.playback.updated_by_name;
        if (isHost) {
            setStatus('You are the host');
        } else {
            setStatus(by ? 'Synced · ' + by : 'Synced');
        }
    }

    /* ── Source loading ── */
    function loadSource(forcePlayback) {
        if (sourceLoading) return;
        sourceLoading = true;
        setLoading('Loading HLS', true);
        fetch('/api/watch-together/rooms/' + encodeURIComponent(room.room_id) + '/source?client_id=' + encodeURIComponent(clientId()) + '&display_name=' + encodeURIComponent(getDisplayName()))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data.success || !data.available || !(data.hls_sources || []).length) {
                    throw data;
                }
                currentProvider = data.provider;
                failedProviders[currentProvider] = false;
                intro = data.intro || null;
                outro = data.outro || null;
                var src = data.hls_sources[0].file || data.hls_sources[0].url;
                attachHls(src);
                setLoading('', false);
                if (forcePlayback && room.playback) {
                    setTimeout(function () { applyPlayback(room.playback, room.server_time, true); }, 250);
                }
            })
            .catch(function () {
                failedProviders[currentProvider] = true;
                setLoading('Trying next HLS server', true);
                fallbackProvider();
            })
            .finally(function () {
                sourceLoading = false;
            });
    }

    function attachHls(src) {
        if (hls) {
            hls.destroy();
            hls = null;
        }
        if (window.Hls && Hls.isSupported()) {
            hls = new Hls({ enableWorker: true, lowLatencyMode: false });
            hls.on(Hls.Events.ERROR, function (_, data) {
                if (data && data.fatal) {
                    failedProviders[currentProvider] = true;
                    fallbackProvider();
                }
            });
            hls.loadSource(src);
            hls.attachMedia(video);
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = src;
        } else {
            setLoading('HLS is not supported in this browser', true);
        }
    }

    function fallbackProvider() {
        // Only the host can change servers
        if (!isHost) return;
        var providers = room.hls_providers || [];
        if (!providers.length) return;
        var index = providers.indexOf(currentProvider);
        var next = '';
        for (var offset = 1; offset <= providers.length; offset += 1) {
            var candidate = providers[(index + offset + providers.length) % providers.length];
            if (candidate && candidate !== currentProvider && !failedProviders[candidate]) {
                next = candidate;
                break;
            }
        }
        if (!next) {
            setLoading('No HLS server available', true);
            return;
        }
        postEvent('server_change', { provider: next }).catch(function () {});
    }

    /* ── Playback event dispatcher (host only) ── */
    function sendPlayback(type) {
        // Non-hosts NEVER send playback events
        if (!isHost) return;
        if (applyingRemote) return;
        postEvent(type).catch(function () {});
    }

    function bindVideo() {
        video.addEventListener('play', function () { sendPlayback('play'); });
        video.addEventListener('pause', function () { sendPlayback('pause'); });
        video.addEventListener('seeked', function () { sendPlayback('seek'); });
        video.addEventListener('ratechange', function () { sendPlayback('ratechange'); });
        video.addEventListener('timeupdate', function () {
            // Skip button only visible for host
            var skip = document.getElementById('wt-skip');
            if (!skip || !isHost) return;
            var cur = video.currentTime || 0;
            skipTarget = null;
            if (intro && cur >= intro.start && cur <= intro.end) {
                skip.textContent = 'Skip Intro';
                skipTarget = intro.end;
            } else if (outro && cur >= outro.start && cur <= outro.end) {
                skip.textContent = 'Skip Outro';
                skipTarget = outro.end;
            }
            skip.hidden = !skipTarget;
        });

        var skip = document.getElementById('wt-skip');
        if (skip) {
            skip.addEventListener('click', function () {
                if (!isHost) return;
                if (skipTarget !== null) {
                    video.currentTime = skipTarget;
                    sendPlayback('seek');
                }
            });
        }

        // Block non-host clicks on the video element itself (prevents tap-to-play on mobile)
        video.addEventListener('click', function (e) {
            if (!isHost) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);

        // Block keyboard space/k to toggle play for non-hosts
        document.addEventListener('keydown', function (e) {
            if (!isHost && video) {
                if (e.code === 'Space' || e.key === 'k' || e.key === 'K') {
                    // Check if focus is on chat input — allow space in chat
                    var active = document.activeElement;
                    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;
                    e.preventDefault();
                }
            }
        });
    }

    /* ── Polling ── */
    function poll() {
        fetch('/api/watch-together/rooms/' + encodeURIComponent(room.room_id) + '/snapshot?client_id=' + encodeURIComponent(clientId()) + '&display_name=' + encodeURIComponent(getDisplayName()) + '&since_chat_seq=' + encodeURIComponent(sinceChatSeq))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data.success) throw data;
                applySnapshot(data.room);
            })
            .catch(function () {
                setStatus('Room unavailable');
                clearInterval(pollTimer);
                clearInterval(heartbeatTimer);
            });
    }

    /* ── Join ── */
    function join() {
        return fetch('/api/watch-together/rooms/' + encodeURIComponent(room.room_id) + '/join', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId(), display_name: getDisplayName() })
        })
        .then(function (response) {
            return response.json().then(function (data) {
                if (!response.ok || !data.success) throw data;
                return data;
            });
        })
        .then(function (data) {
            // Sync client_id with server (server may have cleaned/mapped it)
            if (data.client_id && data.client_id !== clientIdValue) {
                clientIdValue = data.client_id;
                try { localStorage.setItem('yume_watch_together_client_id', data.client_id); } catch (e) {}
            }
            applySnapshot(data.room);
            loadSource(true);
            clearInterval(pollTimer);
            clearInterval(heartbeatTimer);
            pollTimer = setInterval(poll, 500);
            heartbeatTimer = setInterval(function () {
                postEvent('heartbeat').catch(function () {});
            }, 60000);
        })
        .catch(function () {
            setStatus('Could not join room');
        });
    }

    /* ── Name gate for guests ── */
    function initNameGate() {
        var modal = document.getElementById('wt-name-modal');
        var form = document.getElementById('wt-name-form');
        var input = document.getElementById('wt-name-input');
        if (!modal || !form || cfg.isLoggedIn) {
            return join();
        }
        if (getDisplayName()) {
            return join();
        }
        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            displayName = input.value.trim();
            if (!displayName) return;
            try {
                localStorage.setItem('yume_watch_together_name', displayName);
                localStorage.setItem('yumeWatchTogetherName', displayName);
            } catch (e) {}
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
            join();
        });
    }

    /* ── Chat ── */
    function bindChat() {
        var form = document.getElementById('wt-chat-form');
        var input = document.getElementById('wt-chat-input');
        if (!form || !input) return;
        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var body = input.value.trim();
            if (!body) return;
            input.value = '';
            postEvent('chat', { body: body }).catch(function () {
                input.value = body;
            });
        });
    }

    /* ── Copy link ── */
    function bindCopy() {
        var btn = document.getElementById('wt-copy-link');
        if (!btn) return;
        btn.addEventListener('click', function () {
            var link = window.location.href;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(link).then(function () {
                    btn.textContent = 'Copied';
                    setTimeout(function () { btn.textContent = 'Copy Link'; }, 1200);
                });
            }
        });
    }

    /* ── Init ── */
    document.addEventListener('DOMContentLoaded', function () {
        video = document.getElementById('wt-video');
        if (!video || !room.room_id) return;
        currentProvider = room.provider;
        // Initially disable controls until we know host status
        video.controls = false;
        renderProviders(room);
        bindVideo();
        bindChat();
        bindCopy();
        initNameGate();
    });

    window.addEventListener('beforeunload', function () {
        if (!room.room_id || !navigator.sendBeacon) return;
        var body = JSON.stringify({ client_id: clientId() });
        navigator.sendBeacon('/api/watch-together/rooms/' + encodeURIComponent(room.room_id) + '/leave', new Blob([body], { type: 'application/json' }));
    });
})();
