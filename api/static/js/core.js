// Dropdown toggle
function toggleDropdown(id) {
    const dropdown = document.getElementById(id);
    if (dropdown) {
        dropdown.classList.toggle('open');
    }
}

// Close dropdowns when clicking outside
document.addEventListener('click', function (e) {
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        if (!dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });
});

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', () => {
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const mobileNav = document.getElementById('mobile-nav');

    if (mobileMenuToggle && mobileNav) {
        mobileMenuToggle.addEventListener('click', () => {
            mobileNav.classList.toggle('open');
        });
    }

    // Auto-hide flash messages
    setTimeout(() => {
        const flashContainer = document.getElementById('flash-container');
        if (flashContainer) {
            flashContainer.querySelectorAll('.flash-message').forEach((msg, i) => {
                setTimeout(() => {
                    msg.style.animation = 'slideIn 0.3s ease reverse';
                    setTimeout(() => msg.remove(), 300);
                }, i * 200);
            });
        }
    }, 5000);
});

// Login Modal Functions
function openLoginModal() {
    document.getElementById('login-modal').style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeLoginModal() {
    document.getElementById('login-modal').style.display = 'none';
    document.body.style.overflow = '';
}

function showLoginView() {
    document.getElementById('login-view').style.display = 'block';
    document.getElementById('signup-view').style.display = 'none';
}

function showSignupView() {
    document.getElementById('login-view').style.display = 'none';
    document.getElementById('signup-view').style.display = 'block';
}

async function handleLogin(e) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('login-btn');
    const btnText = document.getElementById('login-btn-text');
    const errorDiv = document.getElementById('login-error');

    const turnstileToken = form.querySelector('[name="cf-turnstile-response"]')?.value;
    if (!turnstileToken) {
        errorDiv.textContent = 'Please complete the security check.';
        errorDiv.style.display = 'block';
        return;
    }

    btn.disabled = true;
    btnText.textContent = 'Signing in...';
    errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: form.username.value,
                password: form.password.value,
                cf_turnstile_response: turnstileToken
            })
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            errorDiv.textContent = data.message || 'Login failed';
            errorDiv.style.display = 'block';
            if (window.turnstile) {
                const widget = form.querySelector('.cf-turnstile');
                if (widget) turnstile.reset(widget);
            }
        }
    } catch (err) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Sign In';
    }
}

async function handleSignup(e) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('signup-btn');
    const btnText = document.getElementById('signup-btn-text');
    const errorDiv = document.getElementById('signup-error');

    const turnstileToken = form.querySelector('[name="cf-turnstile-response"]')?.value;
    if (!turnstileToken) {
        errorDiv.textContent = 'Please complete the security check.';
        errorDiv.style.display = 'block';
        return;
    }

    btn.disabled = true;
    btnText.textContent = 'Creating account...';
    errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: form.username.value,
                email: form.email.value,
                password: form.password.value,
                cf_turnstile_response: turnstileToken
            })
        });

        const data = await response.json();

        if (data.success) {
            window.location.reload();
        } else {
            errorDiv.textContent = data.message || 'Signup failed';
            errorDiv.style.display = 'block';
            if (window.turnstile) {
                const widget = form.querySelector('.cf-turnstile');
                if (widget) turnstile.reset(widget);
            }
        }
    } catch (err) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Create Account';
    }
}

// Close modal on Escape
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeLoginModal();
});

// Handle logout via API
async function handleLogout(e) {
    e.preventDefault();
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            window.location.href = '/';
        } else {
            alert('Logout failed. Please try again.');
        }
    } catch (err) {
        console.error('Logout error:', err);
        window.location.href = '/';
    }
}

// Global Auto-Resume Link Updater
document.addEventListener('DOMContentLoaded', () => {
    try {
        const latestWatched = {};
        const latestTimestamps = {};

        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith('yumeResume_')) {
                const match = key.match(/^yumeResume_([^_]+)_ep(\d+)$/);
                if (match) {
                    const animeId = match[1];
                    const epNum = parseInt(match[2]);

                    try {
                        const data = JSON.parse(localStorage.getItem(key));
                        const lastUpdated = data.lastUpdated || 0;

                        if (!latestTimestamps[animeId] || lastUpdated > latestTimestamps[animeId]) {
                            latestTimestamps[animeId] = lastUpdated;
                            latestWatched[animeId] = epNum;
                        }
                    } catch (e) { }
                }
            }
        }

        const watchLinks = document.querySelectorAll('a[href^="/watch/"]');
        watchLinks.forEach(link => {
            const href = link.getAttribute('href');
            const hrefMatch = href.match(/^\/watch\/([^\/]+)(\/ep-1)?$/);
            if (hrefMatch) {
                const animeId = hrefMatch[1];
                if (latestWatched[animeId] && latestWatched[animeId] > 1) {
                    if (link.id !== 'watch-now-btn') {
                        link.setAttribute('href', `/watch/${animeId}/ep-${latestWatched[animeId]}`);
                    }
                }
            }
        });
    } catch (e) {
        console.error("Error auto-updating watch links:", e);
    }
});
