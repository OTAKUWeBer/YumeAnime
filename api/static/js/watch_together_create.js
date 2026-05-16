(function () {
    function clientId() {
        try {
            var stored = localStorage.getItem('yume_watch_together_client_id') || localStorage.getItem('yumeWatchTogetherClientId');
            if (stored) return stored;
            var id = 'wt_' + Math.random().toString(36).slice(2) + Date.now().toString(36);
            localStorage.setItem('yume_watch_together_client_id', id);
            localStorage.setItem('yumeWatchTogetherClientId', id);
            return id;
        } catch (e) {
            return 'wt_' + Math.random().toString(36).slice(2);
        }
    }

    function savedName() {
        try { return localStorage.getItem('yume_watch_together_name') || localStorage.getItem('yumeWatchTogetherName') || ''; }
        catch (e) { return ''; }
    }



    document.addEventListener('DOMContentLoaded', function () {
        var form = document.getElementById('wt-create-form');
        if (!form) return;
        var cfg = window.WT_CREATE_CONFIG || {};
        var status = document.getElementById('wt-create-status');
        var name = document.getElementById('wt-create-name');
        if (name && savedName()) name.value = savedName();

        form.addEventListener('submit', function (event) {
            event.preventDefault();
            var btn = form.querySelector('button[type="submit"]');
            if (status) status.textContent = '';
            if (btn) { btn.disabled = true; btn.textContent = 'Creating...'; }

            var displayName = cfg.isLoggedIn ? cfg.username : (name ? name.value.trim() : savedName());
            if (!cfg.isLoggedIn && displayName) {
                try {
                    localStorage.setItem('yume_watch_together_name', displayName);
                    localStorage.setItem('yumeWatchTogetherName', displayName);
                } catch (e) {}
            }

            fetch('/api/watch-together/rooms', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    client_id: clientId(),
                    display_name: displayName,
                    anime_id: document.getElementById('wt-create-anime').value.trim(),
                    episode_number: document.getElementById('wt-create-episode').value,
                    language: document.getElementById('wt-create-language').value
                })
            })
            .then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok || !data.success) throw data;
                    return data;
                });
            })
            .then(function (data) {
                window.location.href = data.room_url;
            })
            .catch(function (error) {
                if (status) status.textContent = (error && (error.message || error.error)) || 'Could not create room';
                if (btn) { btn.disabled = false; btn.textContent = 'Create Room'; }
            });
        });
    });
})();
