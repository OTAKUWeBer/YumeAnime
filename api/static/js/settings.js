document.addEventListener('DOMContentLoaded', () => {
    // Toggle functionality
    document.querySelectorAll('.toggle').forEach(toggle => {
        toggle.addEventListener('click', function () {
            this.classList.toggle('active');
            const setting = this.dataset.setting;
            const value = this.classList.contains('active');
            localStorage.setItem(`yume_${setting}`, value);
        });

        // Load saved state
        const setting = toggle.dataset.setting;
        const saved = localStorage.getItem(`yume_${setting}`);
        if (saved === 'true') {
            toggle.classList.add('active');
        } else if (saved === 'false') {
            toggle.classList.remove('active');
        }
    });

    // Language preference
    const langSelect = document.getElementById('preferred-lang');
    if (langSelect) {
        langSelect.value = localStorage.getItem('yume_preferred_lang') || 'sub';
        langSelect.addEventListener('change', function () {
            localStorage.setItem('yume_preferred_lang', this.value);
        });
    }

    // Player preference (Internal/External)
    const playerSelect = document.getElementById('preferred-player');
    if (playerSelect) {
        playerSelect.value = localStorage.getItem('preferred_player') || 'internal';
        playerSelect.addEventListener('change', function () {
            localStorage.setItem('preferred_player', this.value);
        });
    }

    // Disconnect AniList
    const disconnectBtn = document.getElementById('disconnect-anilist');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', async function () {
            if (!confirm('Are you sure you want to disconnect your AniList account?')) return;

            try {
                const response = await fetch('/auth/anilist/disconnect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();

                if (data.success) {
                    location.reload();
                } else {
                    alert(data.message || 'Failed to disconnect');
                }
            } catch (e) {
                console.error('Disconnect error:', e);
                alert('An error occurred');
            }
        });
    }

    // Clear history
    const clearBtn = document.getElementById('clear-history');
    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (!confirm('Are you sure you want to clear your watch history? This cannot be undone.')) return;

            // Clear local storage watch data
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith('yume_watch_') || key.startsWith('yume_progress_')) {
                    localStorage.removeItem(key);
                }
            });

            alert('Watch history cleared!');
        });
    }
});
