// Global variables
let searchTimeout;
let otpTimerInterval = null;
let currentResetEmail = '';
let currentResetToken = '';

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
// ============================================
// Modal Logic
// ============================================

function openLoginModal(view = 'login') {
    const modal = document.getElementById('login-modal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Ensure Turnstile renders inside modals
    if (window.turnstile) {
        document.querySelectorAll('.cf-turnstile').forEach(el => turnstile.render(el));
    }

    if (view === 'signup') {
        showSignupView();
    } else {
        showLoginView();
    }
}

function closeLoginModal() {
    const modal = document.getElementById('login-modal');
    modal.style.display = 'none';
    document.body.style.overflow = '';
    
    // Reset views next time it opens
    setTimeout(() => {
        showLoginView();
        
        // Clear all forms and errors
        ['login', 'signup', 'forgot-password', 'verify-code', 'reset-password'].forEach(id => {
            const form = document.getElementById(`${id}-form`);
            if (form) form.reset();
            const error = document.getElementById(`${id.split('-')[0]}-error`);
            if (error) error.style.display = 'none';
        });

        if (otpTimerInterval) {
            clearInterval(otpTimerInterval);
        }
    }, 300);
}

function hideAllAuthViews() {
    ['login-view', 'signup-view', 'forgot-password-view', 'verify-code-view', 'reset-password-view'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
}

function showLoginView() {
    hideAllAuthViews();
    document.getElementById('login-view').style.display = 'block';
}

function showSignupView() {
    hideAllAuthViews();
    document.getElementById('signup-view').style.display = 'block';
}

function showForgotPasswordView() {
    hideAllAuthViews();
    document.getElementById('forgot-password-view').style.display = 'block';
    setTimeout(() => document.getElementById('fp-email-input').focus(), 100);
}

function showVerifyCodeView() {
    hideAllAuthViews();
    document.getElementById('verify-code-view').style.display = 'block';
    
    // Clear any existing OTP values
    const inputs = document.querySelectorAll('.otp-input');
    inputs.forEach(input => {
        input.value = '';
        input.classList.remove('error', 'success');
    });
    setTimeout(() => inputs[0].focus(), 100);
}

function showResetPasswordView() {
    hideAllAuthViews();
    document.getElementById('reset-password-view').style.display = 'block';
    setTimeout(() => document.getElementById('reset-new-password').focus(), 100);
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
                    if (link.id !== 'watch-now-btn' && !link.classList.contains('episode-sidebar-item') && !link.closest('.watch-main')) {
                        link.setAttribute('href', `/watch/${animeId}/ep-${latestWatched[animeId]}`);
                    }
                }
            }
        });
    } catch (e) {
        console.error("Error auto-updating watch links:", e);
    }
});

// ============================================
// Password Reset Flow
// ============================================

function startOtpTimer(durationSeconds) {
    if (otpTimerInterval) clearInterval(otpTimerInterval);
    
    let timer = durationSeconds;
    const countdownEl = document.getElementById('otp-countdown');
    const timerContainerEl = document.getElementById('otp-timer');
    const resendBtn = document.getElementById('resend-btn');
    
    timerContainerEl.classList.remove('expiring', 'expired');
    resendBtn.style.color = 'var(--text-muted)';
    resendBtn.disabled = true;

    otpTimerInterval = setInterval(() => {
        let minutes = parseInt(timer / 60, 10);
        let seconds = parseInt(timer % 60, 10);

        minutes = minutes < 10 ? "0" + minutes : minutes;
        seconds = seconds < 10 ? "0" + seconds : seconds;

        countdownEl.textContent = minutes + ":" + seconds;

        if (timer <= 60 && timer > 0) {
            timerContainerEl.classList.add('expiring');
        }

        if (--timer < 0) {
            clearInterval(otpTimerInterval);
            countdownEl.textContent = "00:00";
            timerContainerEl.classList.remove('expiring');
            timerContainerEl.classList.add('expired');
            resendBtn.style.color = 'var(--accent)';
            resendBtn.disabled = false;
        }
    }, 1000);
}

async function handleForgotPassword(e) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('forgot-btn');
    const btnText = document.getElementById('forgot-btn-text');
    const errorDiv = document.getElementById('forgot-error');
    const email = form.email.value.trim();

    if (!email) return;

    btn.disabled = true;
    btnText.textContent = 'Sending...';
    errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        // Don't leak whether email exists; proceed to code verification either way
        // to prevent email enumeration, unless rate limited.
        if (response.status === 429) {
            errorDiv.textContent = 'Too many requests. Please wait a moment.';
            errorDiv.style.display = 'block';
            return;
        }

        currentResetEmail = email;
        document.getElementById('verify-email-display').textContent = email;
        showVerifyCodeView();
        startOtpTimer(300); // 5 minutes
    } catch (err) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Send Reset Code';
    }
}

async function handleResendCode() {
    if (!currentResetEmail) return;
    
    const btn = document.getElementById('resend-btn');
    if (btn.disabled) return;
    
    btn.textContent = 'Resending...';
    btn.disabled = true;

    try {
        const response = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: currentResetEmail })
        });

        if (response.status === 429) {
            alert('Too many requests. Please wait a moment.');
            btn.textContent = "Didn't receive it? Resend code";
            btn.disabled = false;
            return;
        }
        
        startOtpTimer(300);
        btn.textContent = "Code resent!";
        setTimeout(() => {
            btn.textContent = "Didn't receive it? Resend code";
        }, 3000);
    } catch (err) {
        btn.textContent = "Didn't receive it? Resend code";
        btn.disabled = false;
    }
}

async function handleVerifyCode(e) {
    e.preventDefault();
    const inputs = document.querySelectorAll('#verify-code-form .otp-input');
    const btn = document.getElementById('verify-btn');
    const btnText = document.getElementById('verify-btn-text');
    const errorDiv = document.getElementById('verify-error');
    
    let code = '';
    inputs.forEach(input => code += input.value);

    if (code.length !== 6) {
        errorDiv.textContent = 'Please enter the 6-digit code.';
        errorDiv.style.display = 'block';
        return;
    }

    btn.disabled = true;
    btnText.textContent = 'Verifying...';
    errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/auth/verify-reset-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: currentResetEmail,
                code: code
            })
        });
        
        const data = await response.json();

        if (data.success) {
            clearInterval(otpTimerInterval);
            currentResetToken = data.reset_token;
            inputs.forEach(input => {
                input.classList.remove('error');
                input.classList.add('success');
            });
            setTimeout(() => {
                showResetPasswordView();
            }, 500);
        } else {
            errorDiv.textContent = data.message || 'Invalid or expired code.';
            errorDiv.style.display = 'block';
            inputs.forEach(input => {
                input.classList.add('error');
                setTimeout(() => input.classList.remove('error'), 400);
            });
        }
    } catch (err) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
    } finally {
        btn.disabled = false;
        btnText.textContent = 'Verify Code';
    }
}

async function handleResetPassword(e) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('reset-btn');
    const btnText = document.getElementById('reset-btn-text');
    const errorDiv = document.getElementById('reset-error');
    const successDiv = document.getElementById('reset-success');
    
    const newPassword = form.new_password.value;
    const confirmPassword = form.confirm_password.value;

    if (newPassword !== confirmPassword) {
        errorDiv.textContent = 'Passwords do not match.';
        errorDiv.style.display = 'block';
        return;
    }

    // OTP verification guarantees code knowledge, but we need to send it again
    // We already have 'currentResetEmail' and 'currentResetToken'
    
    // We need the original code typed for re-verification if the server enforces it
    // In our backend implementation, verify_reset_code is called again.
    let code = '';
    document.querySelectorAll('#verify-code-form .otp-input').forEach(input => code += input.value);

    btn.disabled = true;
    btnText.textContent = 'Resetting...';
    errorDiv.style.display = 'none';

    try {
        const response = await fetch('/api/auth/reset-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: currentResetEmail,
                code: code,
                new_password: newPassword,
                reset_token: currentResetToken
            })
        });
        
        const data = await response.json();

        if (data.success) {
            successDiv.textContent = 'Password reset successfully! Redirecting...';
            successDiv.style.display = 'block';
            setTimeout(() => {
                window.location.reload(); // Simple reload handles everything nicely
            }, 1500);
        } else {
            errorDiv.textContent = data.message || 'Failed to reset password.';
            errorDiv.style.display = 'block';
            btn.disabled = false;
            btnText.textContent = 'Reset Password';
        }
    } catch (err) {
        errorDiv.textContent = 'An error occurred. Please try again.';
        errorDiv.style.display = 'block';
        btn.disabled = false;
        btnText.textContent = 'Reset Password';
    }
}

// OTP Input Handling (arrow navigation, paste, backspace)
document.addEventListener('DOMContentLoaded', () => {
    const otpInputs = document.querySelectorAll('.otp-input');
    
    if (otpInputs.length === 0) return;

    otpInputs.forEach((input, index) => {
        // Prevent non-numeric chars mostly
        input.addEventListener('keydown', (e) => {
            if (['e', 'E', '+', '-', '.'].includes(e.key)) {
                e.preventDefault();
            }
            if (e.key === 'Backspace' && !input.value && index > 0) {
                // Focus previous input on backspace if empty
                otpInputs[index - 1].focus();
            } else if (e.key === 'ArrowLeft' && index > 0) {
                otpInputs[index - 1].focus();
            } else if (e.key === 'ArrowRight' && index < 5) {
                otpInputs[index + 1].focus();
            }
        });

        // Focus next input organically
        input.addEventListener('input', (e) => {
            // Remove non-digits just in case
            input.value = input.value.replace(/[^0-9]/g, '');
            input.classList.remove('error');
            
            if (input.value && index < 5) {
                otpInputs[index + 1].focus();
            }
            
            // Auto submit when 6th digit filled
            if (index === 5 && input.value) {
                let code = '';
                otpInputs.forEach(i => code += i.value);
                if (code.length === 6) {
                    document.getElementById('verify-btn').click();
                }
            }
        });

        // Handle Paste
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            let pastedData = (e.clipboardData || window.clipboardData).getData('text').trim();
            // keep only digits
            let digits = pastedData.replace(/[^0-9]/g, '');
            
            if (!digits) return;
            
            // Fill inputs starting from current index
            let startIdx = 0; // Better UX: paste usually starts from 0th box regardless where focused if full sequence
            if (digits.length < 6) startIdx = index;
            
            for (let i = 0; i < digits.length && (startIdx + i) < 6; i++) {
                otpInputs[startIdx + i].value = digits[i];
                otpInputs[startIdx + i].classList.remove('error');
            }
            
            // Focus next empty input or last input
            let nextIdx = startIdx + Math.min(digits.length, 6) - 1;
            if (nextIdx < 5) nextIdx++;
            otpInputs[nextIdx].focus();
            
            // Auto submit if all 6 filled
            let code = '';
            otpInputs.forEach(i => code += i.value);
            if (code.length === 6) {
                document.getElementById('verify-btn').click();
            }
        });
    });
});

