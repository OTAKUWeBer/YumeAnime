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

    // Disconnect MyAnimeList
    window.disconnectMAL = async function() {
        if (!confirm('Are you sure you want to disconnect your MyAnimeList account?')) return;

        try {
            const response = await fetch('/auth/mal/disconnect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();

            if (data.success) {
                location.reload();
            } else {
                alert(data.message || 'Failed to disconnect MyAnimeList');
            }
        } catch (e) {
            console.error('MAL Disconnect error:', e);
            alert('An error occurred');
        }
    };

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

    // Change Password Modal
    const changePwdBtn = document.getElementById('change-password-btn');
    const changePwdModal = document.getElementById('change-password-modal');
    const closePwdModal = document.getElementById('close-password-modal');
    const closePwdBackdrop = document.getElementById('close-password-backdrop');
    const changePwdForm = document.getElementById('change-password-form');
    const pwdErrorMsg = document.getElementById('password-error-msg');
    
    if (changePwdBtn && changePwdModal) {
        changePwdBtn.addEventListener('click', () => {
            changePwdModal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            if (pwdErrorMsg) pwdErrorMsg.style.display = 'none';
        });

        const closePwd = () => {
            changePwdModal.style.display = 'none';
            document.body.style.overflow = '';
            changePwdForm.reset();
            if (typeof turnstile !== 'undefined') {
                const tsEl = changePwdForm.querySelector('.cf-turnstile');
                if (tsEl && tsEl.dataset.turnstileId) {
                    turnstile.reset(tsEl.dataset.turnstileId);
                }
            }
        };

        closePwdModal.addEventListener('click', closePwd);
        if (closePwdBackdrop) {
            closePwdBackdrop.addEventListener('click', closePwd);
        }

        changePwdForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const currentPassword = document.getElementById('current-password').value;
            const newPassword = document.getElementById('new-password').value;
            
            const payload = { current_password: currentPassword, new_password: newPassword };
            
            if (typeof FormData !== 'undefined') {
                const formData = new FormData(changePwdForm);
                const tsToken = formData.get('cf-turnstile-response');
                if (tsToken) {
                    payload.cf_turnstile_response = tsToken;
                }
            }

            const btn = document.getElementById('submit-password-btn');
            const btnText = document.getElementById('submit-password-btn-text');
            const originalText = btnText ? btnText.textContent : btn.textContent;
            
            if (btnText) {
                btnText.textContent = 'Updating...';
            } else {
                btn.textContent = 'Updating...';
            }
            btn.disabled = true;
            if (pwdErrorMsg) pwdErrorMsg.style.display = 'none';

            try {
                const response = await fetch('/api/change-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Password changed successfully! You may need to log in again on other devices.');
                    closePwd();
                } else {
                    if (pwdErrorMsg) {
                        pwdErrorMsg.textContent = data.message || 'Failed to update password';
                        pwdErrorMsg.style.display = 'block';
                    }
                    if (typeof turnstile !== 'undefined') {
                        const tsEl = changePwdForm.querySelector('.cf-turnstile');
                        if (tsEl && tsEl.dataset.turnstileId) {
                            turnstile.reset(tsEl.dataset.turnstileId);
                        }
                    }
                }
            } catch (err) {
                console.error(err);
                if (pwdErrorMsg) {
                    pwdErrorMsg.textContent = 'A network error occurred. Please try again.';
                    pwdErrorMsg.style.display = 'block';
                }
            } finally {
                if (btnText) {
                    btnText.textContent = originalText;
                } else {
                    btn.textContent = originalText;
                }
                btn.disabled = false;
            }
        });
    }
});
