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

    function fmt(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) seconds = 0;
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        return h ? h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') : m + ':' + String(s).padStart(2, '0');
    }

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
                return data;
            });
        })
        .then(function (data) {
            if (data.room) applySnapshot(data.room);
            return data;
        })
        .catch(function (error) {
            setStatus((error && (error.message || error.error)) || 'Room update failed');
            throw error;
        });
    }

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
            button.addEventListener('click', function () {
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
            text.textContent = member.name + (member.is_self ? ' (You)' : '');
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
            item.className = 'wt-chat-message';
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

        if (playback.updated_by === clientId() && !force) return;

        var target = effectivePosition(playback, serverTime);
        if (Number.isFinite(video.duration) && video.duration > 0) {
            target = Math.min(target, Math.max(0, video.duration - 0.2));
        }

        applyingRemote = true;
        try {
            if (Math.abs((video.playbackRate || 1) - (playback.rate || 1)) > 0.01) {
                video.playbackRate = playback.rate || 1;
            }
            var drift = Math.abs((video.currentTime || 0) - target);
            if (drift > 1.25 || playback.event === 'seek' || force) {
                video.currentTime = target;
            } else if (!playback.paused && drift > 0.45) {
                var direction = (video.currentTime || 0) < target ? 1 : -1;
                video.playbackRate = Math.max(0.75, Math.min(1.25, (playback.rate || 1) + direction * 0.06));
                setTimeout(function () {
                    if (video && !applyingRemote) video.playbackRate = playback.rate || 1;
                }, 1800);
            }
            if (playback.paused) {
                if (!video.paused) video.pause();
            } else if (video.paused) {
                video.play().catch(function () {
                    setStatus('Tap play to sync');
                });
            }
        } finally {
            setTimeout(function () { applyingRemote = false; }, 600);
        }
    }

    function applySnapshot(roomData) {
        if (!roomData) return;
        room = roomData;
        renderMembers(roomData);
        renderProviders(roomData);
        appendMessages(roomData.messages || []);
        if (roomData.provider && roomData.provider !== currentProvider) {
            currentProvider = roomData.provider;
            loadSource(true);
        }
        applyPlayback(roomData.playback, roomData.server_time, false);
        var by = roomData.playback && roomData.playback.updated_by_name;
        setStatus(by ? 'Synced by ' + by : 'Synced');
    }

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
                    setTimeout(function () { applyPlayback(room.playback, room.server_time, true); }, 350);
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

    function sendPlayback(type) {
        if (applyingRemote) return;
        postEvent(type).catch(function () {});
    }

    function bindVideo() {
        video.addEventListener('play', function () { sendPlayback('play'); });
        video.addEventListener('pause', function () { sendPlayback('pause'); });
        video.addEventListener('seeked', function () { sendPlayback('seek'); });
        video.addEventListener('ratechange', function () { sendPlayback('ratechange'); });
        video.addEventListener('timeupdate', function () {
            var skip = document.getElementById('wt-skip');
            if (!skip) return;
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
                if (skipTarget !== null) {
                    video.currentTime = skipTarget;
                    sendPlayback('seek');
                }
            });
        }
    }

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
            applySnapshot(data.room);
            loadSource(true);
            clearInterval(pollTimer);
            clearInterval(heartbeatTimer);
            pollTimer = setInterval(poll, 1000);
            heartbeatTimer = setInterval(function () {
                postEvent('heartbeat').catch(function () {});
            }, 60000);
        })
        .catch(function () {
            setStatus('Could not join room');
        });
    }

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

    document.addEventListener('DOMContentLoaded', function () {
        video = document.getElementById('wt-video');
        if (!video || !room.room_id) return;
        currentProvider = room.provider;
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
