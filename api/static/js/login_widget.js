// Ensure modals are appended to document.body so `position: fixed` truly covers viewport
(function ensureModalsOnBody() {
  const loginModalWidget = document.getElementById('loginModalWidget');
  const syncModalWidget = document.getElementById('syncModalWidget');
  
  if (loginModalWidget && loginModalWidget.parentElement !== document.body) {
    document.body.appendChild(loginModalWidget);
  }
  if (syncModalWidget && syncModalWidget.parentElement !== document.body) {
    document.body.appendChild(syncModalWidget);
  }
})();

class LoginWidget {
  constructor() {
    // DOM refs will be initialized in initializeElements()
    this.loginBtnWidget = null;
    this.loginModalWidget = null;
    this.syncModalWidget = null;
    this.closeLoginWidget = null;
    this.closeSyncWidget = null;
    this.loginFormWidget = null;
    this.cancelLoginWidget = null;

    this.signupFormWidget = null;
    this.showSignupWidget = null;
    this.showLoginWidget = null;
    this.cancelSignupWidget = null;

    this.profileBoxWidget = null; // container in navbar where we inject profile button
    this.profileBtn = null;       // injected profile button
    this.profileDropdown = null;  // appended to body
    this.logoutBtnWidget = null;  // inside appended dropdown

    this.loginMsgWidget = null;
    this.signupMsgWidget = null;

    // AniList buttons
    this.anilistLoginBtn = null;
    this.anilistSignupBtn = null;

    // Sync elements
    this.startSyncWidget = null;
    this.cancelSyncWidget = null;
    this.syncResultWidget = null;
    this.syncProgressWidget = null;
    this.progressFill = null;
    this.progressText = null;

    // Sync progress tracking
    this.syncProgressInterval = null;
    this.syncInProgress = false;

    this.isLoggedIn = false;
    this.currentUser = null;

    this.initializeElements();
    this.attachEventListeners();
    this.checkServerSession();
  }

  initializeElements() {
    // login / modal
    this.loginBtnWidget = document.getElementById('loginBtnWidget');
    this.loginModalWidget = document.getElementById('loginModalWidget');
    this.syncModalWidget = document.getElementById('syncModalWidget');
    this.closeLoginWidget = document.getElementById('closeLoginWidget');
    this.closeSyncWidget = document.getElementById('closeSyncWidget');
    this.loginFormWidget = document.getElementById('loginFormWidget');
    this.cancelLoginWidget = document.getElementById('cancelLoginWidget');

    // signup
    this.signupFormWidget = document.getElementById('signupFormWidget');
    this.showSignupWidget = document.getElementById('showSignupWidget');
    this.showLoginWidget = document.getElementById('showLoginWidget');
    this.cancelSignupWidget = document.getElementById('cancelSignupWidget');

    // AniList buttons
    this.anilistLoginBtn = document.getElementById('anilistLoginBtn');
    this.anilistSignupBtn = document.getElementById('anilistSignupBtn');

    // Sync elements
    this.startSyncWidget = document.getElementById('startSyncWidget');
    this.cancelSyncWidget = document.getElementById('cancelSyncWidget');
    this.syncResultWidget = document.getElementById('syncResultWidget');
    this.syncProgressWidget = document.getElementById('syncProgressWidget');
    this.progressFill = document.getElementById('progressFill');
    this.progressText = document.getElementById('progressText');

    // profile container in navbar (empty in DOM, we inject button)
    this.profileBoxWidget = document.getElementById('profileBoxWidget');

    // messages
    this.loginMsgWidget = document.getElementById('loginMsgWidget');
    this.signupMsgWidget = document.getElementById('signupMsgWidget');
  }

  attachEventListeners() {
    // open login modal
    this.loginBtnWidget?.addEventListener('click', () => this.showLoginModal());

    // modal close / cancel
    this.closeLoginWidget?.addEventListener('click', () => this.hideLoginModal());
    this.closeSyncWidget?.addEventListener('click', () => this.hideSyncModal());
    this.cancelLoginWidget?.addEventListener('click', () => this.hideLoginModal());
    this.cancelSignupWidget?.addEventListener('click', () => this.hideLoginModal());
    this.cancelSyncWidget?.addEventListener('click', () => this.hideSyncModal());

    // form submits
    this.loginFormWidget?.addEventListener('submit', (e) => this.handleLogin(e));
    this.signupFormWidget?.addEventListener('submit', (e) => this.handleSignup(e));

    // sync
    this.startSyncWidget?.addEventListener('click', () => this.handleSyncAniList());

    // switch forms
    this.showSignupWidget?.addEventListener('click', () => this.switchToSignup());
    this.showLoginWidget?.addEventListener('click', () => this.switchToLogin());

    // AniList OAuth buttons
    this.anilistLoginBtn?.addEventListener('click', () => this.handleAniListAuth());
    this.anilistSignupBtn?.addEventListener('click', () => this.handleAniListAuth());

    // Close modal by clicking backdrop
    this.loginModalWidget?.addEventListener('click', (e) => {
      if (e.target === this.loginModalWidget) this.hideLoginModal();
    });

    this.syncModalWidget?.addEventListener('click', (e) => {
      if (e.target === this.syncModalWidget) this.hideSyncModal();
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (this.loginModalWidget && !this.loginModalWidget.classList.contains('hidden')) {
          this.hideLoginModal();
        }
        if (this.syncModalWidget && !this.syncModalWidget.classList.contains('hidden')) {
          this.hideSyncModal();
        }
      }
    });

    // Global click: close our appended dropdown if click outside
    document.addEventListener('click', (e) => {
      if (this.profileDropdown && !this.profileDropdown.contains(e.target) && !this.profileBoxWidget.contains(e.target)) {
        this.profileDropdown.classList.add('hidden');
      }
    });
  }

  resetTurnstile(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    const turnstileWidget = form.querySelector('.cf-turnstile');
    if (turnstileWidget && window.turnstile) {
      // Reset the Turnstile widget
      window.turnstile.reset(turnstileWidget);
    }
  }

  generateStateParameter() {
    return Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
  }

  handleAniListAuth() {
    // Generate state parameter for security
    const state = this.generateStateParameter();
    sessionStorage.setItem('anilist_oauth_state', state);
    
    // Hide modal first
    this.hideLoginModal();
    
    // Build OAuth URL - Use callback route instead of link route for regular login/signup
    const clientId = this.getAniListClientId();
    const redirectUri = this.getAniListRedirectUri();
    
    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: 'code',
      state: state
    });
    
    const authUrl = `https://anilist.co/api/v2/oauth/authorize?${params.toString()}`;
    window.location.href = authUrl;
  }

  getAniListClientId() {
    // You'll need to make this available to the frontend
    // Either through a meta tag or a separate endpoint
    return document.querySelector('meta[name="anilist-client-id"]')?.content || '29621';
  }

  getAniListRedirectUri() {
    // Build redirect URI based on current domain
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = window.location.port;
    const portSuffix = port ? `:${port}` : '';
    return `${protocol}//${hostname}${portSuffix}/auth/anilist/callback`;
  }

  showLoginModal() {
    this.loginModalWidget?.classList.remove('hidden');
    this.loginModalWidget?.classList.add('visible');
    this.switchToLogin();
    document.getElementById('loginUsernameWidget')?.focus();
  }

  hideLoginModal() {
    this.loginModalWidget?.classList.remove('visible');
    this.loginModalWidget?.classList.add('hidden');
    this.loginFormWidget?.reset();
    this.signupFormWidget?.reset();
    this.clearMessages();
    this.switchToLogin();
  }

  showSyncModal() {
    if (!this.currentUser || !this.currentUser.anilist_authenticated) {
      this.showMessage(null, 'Please connect your AniList account first.', 'error');
      return;
    }
    this.syncModalWidget?.classList.remove('hidden');
    this.syncModalWidget?.classList.add('visible');
    this.syncResultWidget?.classList.add('hidden');
    this.syncProgressWidget?.classList.add('hidden');
  }

  hideSyncModal() {
    this.syncModalWidget?.classList.remove('visible');
    this.syncModalWidget?.classList.add('hidden');
    this.syncResultWidget?.classList.add('hidden');
    this.syncProgressWidget?.classList.add('hidden');
    this.stopSyncProgressPolling();
  }

  switchToLogin() {
    this.loginFormWidget?.classList.remove('hidden');
    this.signupFormWidget?.classList.add('hidden');
    this.clearMessages();
  }

  switchToSignup() {
    this.loginFormWidget?.classList.add('hidden');
    this.signupFormWidget?.classList.remove('hidden');
    this.clearMessages();
    document.getElementById('signupUsernameWidget')?.focus();
  }

  clearMessages() {
    if (this.loginMsgWidget) this.loginMsgWidget.textContent = '';
    if (this.signupMsgWidget) this.signupMsgWidget.textContent = '';
  }

  showMessage(element, message, type = 'info') {
    if (!element) return;
    element.textContent = message;
    element.style.color = type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#6b7280';
  }

  async handleSignup(event) {
    event.preventDefault();
    const username = document.getElementById('signupUsernameWidget')?.value.trim();
    const email = document.getElementById('signupEmailWidget')?.value.trim();
    const password = document.getElementById('signupPasswordWidget')?.value;
    const confirmPassword = document.getElementById('confirmPasswordWidget')?.value;

    // Grab Turnstile token
    const turnstileToken = document.querySelector('#signupFormWidget [name="cf-turnstile-response"]')?.value;

    if (!username || !email || !password || !confirmPassword) {
      this.showMessage(this.signupMsgWidget, 'Please fill in all fields.', 'error');
      return;
    }
    if (username.length < 3) {
      this.showMessage(this.signupMsgWidget, 'Username must be at least 3 characters long.', 'error');
      return;
    }
    if (password.length < 6) {
      this.showMessage(this.signupMsgWidget, 'Password must be at least 6 characters long.', 'error');
      return;
    }
    if (password !== confirmPassword) {
      this.showMessage(this.signupMsgWidget, 'Passwords do not match.', 'error');
      return;
    }
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(email)) {
      this.showMessage(this.signupMsgWidget, 'Please enter a valid email address.', 'error');
      return;
    }
    if (!turnstileToken) {
      this.showMessage(this.signupMsgWidget, 'Please complete the security check.', 'error');
      return;
    }

    this.setButtonLoading('submitSignupWidget', true);
    this.showMessage(this.signupMsgWidget, 'Creating your account...');

    try {
      const response = await fetch('/api/signup', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify({ username, email, password, cf_turnstile_response: turnstileToken })
      });
      const data = await response.json();

      if (data.success) {
        this.isLoggedIn = true;
        this.currentUser = data.user || data;
        this.showMessage(this.signupMsgWidget, 'Account created successfully!', 'success');
        setTimeout(() => window.location.reload(), 300);
      } else {
        this.showMessage(this.signupMsgWidget, data.message || 'Registration failed.', 'error');
        // Reset Turnstile after failed signup
        this.resetTurnstile('signupFormWidget');
      }
    } catch (err) {
      this.showMessage(this.signupMsgWidget, 'An error occurred. Check your network.', 'error');
      // Reset Turnstile after network error
      this.resetTurnstile('signupFormWidget');
    } finally {
      this.setButtonLoading('submitSignupWidget', false);
    }
  }

  async handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('loginUsernameWidget')?.value.trim();
    const password = document.getElementById('loginPasswordWidget')?.value;
    const remember = document.getElementById('rememberWidget')?.checked;

    // Grab Turnstile token
    const turnstileToken = document.querySelector('#loginFormWidget [name="cf-turnstile-response"]')?.value;

    if (!username || !password) {
      this.showMessage(this.loginMsgWidget, 'Please fill in all fields.', 'error');
      return;
    }
    if (password.length < 6) {
      this.showMessage(this.loginMsgWidget, 'Password must be at least 6 characters.', 'error');
      return;
    }
    if (!turnstileToken) {
      this.showMessage(this.loginMsgWidget, 'Please complete the security check.', 'error');
      return;
    }

    this.setButtonLoading('submitLoginWidget', true);
    this.showMessage(this.loginMsgWidget, 'Signing you in...');

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify({ username, password, cf_turnstile_response: turnstileToken })
      });
      const data = await response.json();

      if (data.success) {
        this.isLoggedIn = true;
        this.currentUser = data.user || data;
        this.showMessage(this.loginMsgWidget, 'Login successful!', 'success');
        setTimeout(() => window.location.reload(), 300);
      } else {
        this.showMessage(this.loginMsgWidget, data.message || 'Login failed.', 'error');
        // Reset Turnstile after failed login
        this.resetTurnstile('loginFormWidget');
      }
    } catch (err) {
      this.showMessage(this.loginMsgWidget, 'An error occurred. Check your network.', 'error');
      // Reset Turnstile after network error
      this.resetTurnstile('loginFormWidget');
    } finally {
      this.setButtonLoading('submitLoginWidget', false);
    }
  }

  async handleSyncAniList() {
    if (!this.currentUser || !this.currentUser.anilist_authenticated) {
      this.showSyncResult('Please connect your AniList account first.', 'error');
      return;
    }

    this.setButtonLoading('startSyncWidget', true);
    this.syncProgressWidget?.classList.remove('hidden');
    this.syncInProgress = true;
    
    // Start progress polling
    this.startSyncProgressPolling();
    
    // Show initial progress
    this.updateSyncProgress(0, 'Starting sync...');

    try {
      const response = await fetch('/api/sync-anilist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin'
      });

      const data = await response.json();

      if (data.success) {
        this.updateSyncProgress(100, `Sync completed! Synced ${data.synced_count}/${data.total_count} entries`);
        this.showSyncResult(
          `Sync completed successfully! Added ${data.synced_count} new entries, skipped ${data.skipped_count} duplicates. ${data.failed_count > 0 ? `${data.failed_count} entries could not be matched.` : ''}`,
          'success'
        );
        
        // Auto-close modal after 4 seconds
        setTimeout(() => {
          this.hideSyncModal();
        }, 4000);
      } else {
        this.showSyncResult(data.message || 'Sync failed. Please try again.', 'error');
      }
    } catch (err) {
      this.showSyncResult('Network error occurred. Please try again.', 'error');
    } finally {
      this.setButtonLoading('startSyncWidget', false);
      this.syncInProgress = false;
      this.stopSyncProgressPolling();
    }
  }

  startSyncProgressPolling() {
    if (this.syncProgressInterval) {
      clearInterval(this.syncProgressInterval);
    }
    
    this.syncProgressInterval = setInterval(async () => {
      if (!this.syncInProgress) {
        this.stopSyncProgressPolling();
        return;
      }
      
      try {
        const response = await fetch('/api/sync-progress', {
          method: 'GET',
          credentials: 'same-origin'
        });
        
        if (response.ok) {
          const progress = await response.json();
          
          if (progress.status === 'syncing' || progress.status === 'starting') {
            const percentage = progress.percentage || 0;
            const message = this.formatProgressMessage(progress);
            this.updateSyncProgress(percentage, message);
          } else if (progress.status === 'completed') {
            const message = `Completed! Synced ${progress.synced || 0}, skipped ${progress.skipped || 0}, failed ${progress.failed || 0}`;
            this.updateSyncProgress(100, message);
            this.stopSyncProgressPolling();
          } else if (progress.status === 'error') {
            this.updateSyncProgress(0, `Error: ${progress.message || 'Unknown error'}`);
            this.stopSyncProgressPolling();
          }
        }
      } catch (error) {
        // Silently continue - the main request will handle final error display
        console.warn('Progress polling error:', error);
      }
    }, 1000); // Poll every second
  }

  stopSyncProgressPolling() {
    if (this.syncProgressInterval) {
      clearInterval(this.syncProgressInterval);
      this.syncProgressInterval = null;
    }
  }

  formatProgressMessage(progress) {
    const processed = progress.processed || 0;
    const total = progress.total || 0;
    const synced = progress.synced || 0;
    const skipped = progress.skipped || 0;
    const failed = progress.failed || 0;
    const eta = progress.estimated_remaining || 0;
    
    if (total === 0) {
      return 'Starting sync...';
    }
    
    let message = `Processing ${processed}/${total} entries`;
    if (synced > 0 || skipped > 0 || failed > 0) {
      message += ` (✓${synced} ⭯${skipped} ✗${failed})`;
    }
    
    if (eta > 0 && eta < 300) { // Only show ETA if less than 5 minutes
      const etaText = eta > 60 ? `${Math.round(eta/60)}m` : `${Math.round(eta)}s`;
      message += ` • ETA: ${etaText}`;
    }
    
    return message;
  }

  updateSyncProgress(percentage, message) {
    if (this.progressFill) {
      this.progressFill.style.width = `${Math.min(100, Math.max(0, percentage))}%`;
    }
    if (this.progressText) {
      this.progressText.textContent = message;
    }
  }

  showSyncResult(message, type) {
    if (!this.syncResultWidget) return;
    
    const typeClass = type === 'success' ? 'success' : type === 'error' ? 'error' : 'warning';
    
    this.syncResultWidget.innerHTML = `
      <div class="sync-status ${typeClass}">
        <p class="text-sm">${message}</p>
      </div>
    `;
    
    this.syncResultWidget.classList.remove('hidden');
  }

  async handleLogout() {
    try {
      await fetch('/api/logout', { 
        method: 'POST',
        credentials: 'same-origin'
      });
    } catch (e) {
      console.warn('Logout API failed, clearing state anyway.');
    }
    
    this.isLoggedIn = false;
    this.currentUser = null;
    
    // Refresh page after logout
    window.location.reload();
  }

  setButtonLoading(buttonId, loading) {
    const button = document.getElementById(buttonId);
    const text = document.getElementById(buttonId.replace('submit', '').replace('start', 'sync').replace('Widget', 'BtnTextWidget'));
    const spinner = document.getElementById(buttonId.replace('submit', '').replace('start', 'sync').replace('Widget', 'SpinnerWidget'));
    
    if (button && text && spinner) {
      button.disabled = loading;
      if (loading) {
        text.classList.add('hidden');
        spinner.classList.remove('hidden');
      } else {
        text.classList.remove('hidden');
        spinner.classList.add('hidden');
      }
    }
  }

  // Enhanced profile button renderer with AniList avatar support
  renderProfileButton() {
    if (!this.profileBoxWidget) return;

    // Check if user has AniList avatar
    const hasAvatar = this.currentUser && this.currentUser.avatar;
    const isAniListUser = this.currentUser && this.currentUser.anilist_authenticated;

    if (hasAvatar) {
      // Render with AniList avatar
      this.profileBoxWidget.innerHTML = `
        <button id="profileBtnWidget" aria-label="Open profile" 
                class="relative w-10 h-10 rounded-full flex items-center justify-center hover:ring-2 hover:ring-purple-500/50 transition-all">
          <img src="${this.currentUser.avatar}" alt="Profile" class="profile-avatar">
          ${isAniListUser ? `
            <div class="anilist-badge absolute -bottom-1 -right-1">
              <svg class="anilist-icon" viewBox="0 0 24 24">
                <path d="M6.361 2.943 0 21.056h4.06l1.077-3.133h6.875l1.077 3.133H17.15L10.789 2.943zm1.77 5.392 2.18 6.336H5.951zm10.365 9.794V8.113c3.02.501 4.473 2.273 4.473 4.728 0 2.456-1.453 4.227-4.473 4.728z"/>
              </svg>
            </div>` : ''}
        </button>
      `;
    } else {
      // Render default SVG profile icon
      this.profileBoxWidget.innerHTML = `
        <button id="profileBtnWidget" aria-label="Open profile" 
                class="w-10 h-10 rounded-full flex items-center justify-center hover:bg-purple-700/20">
          <svg role="img" aria-hidden="false" aria-label="Profile icon" width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="text-white">
            <path d="M12 12c2.761 0 5-2.239 5-5s-2.239-5-5-5-5 2.239-5 5 2.239 5 5 5z" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M20 21c0-3.866-3.582-7-8-7s-8 3.134-8 7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      `;
    }

    this.profileBtn = document.getElementById('profileBtnWidget');
    this.createProfileDropdown(); // ensure dropdown exists

    // Toggle dropdown and position it under the button
    this.profileBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!this.profileDropdown) return;
      this.positionDropdownUnderButton(this.profileBtn, this.profileDropdown);
      this.profileDropdown.classList.toggle('hidden');
    });
  }

  // Enhanced profile dropdown with AniList info and sync option
  createProfileDropdown() {
    if (this.profileDropdown) return;
    // If there is a static #profileDropdown in DOM, hide it to avoid duplicates
    const staticDd = document.getElementById('profileDropdown');
    if (staticDd) staticDd.classList.add('hidden');

    const isAniListUser = this.currentUser && this.currentUser.anilist_authenticated;
    
    const dd = document.createElement('div');
    dd.id = 'profileDropdownApp';
    dd.className = 'hidden absolute mt-2 w-56 bg-gray-900 border border-white/10 rounded-lg shadow-xl z-50';
    dd.setAttribute('role', 'menu');
    
    let userInfoSection = '';
    if (this.currentUser) {
      userInfoSection = `
        <div class="px-4 py-3 border-b border-white/10">
                // Show notification that progress will persist
                this.showSyncResult(
                    `Sync started! You can close this page - progress will be shown in notifications.`,
                    'info'
                );
                
          <div class="flex items-center space-x-3">
            ${this.currentUser.avatar ? 
              `<img src="${this.currentUser.avatar}" alt="Profile" class="w-8 h-8 rounded-full object-cover border border-white/20">` :
              `<div class="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center">
                 <span class="text-white font-semibold text-sm">${this.currentUser.username.charAt(0).toUpperCase()}</span>
               </div>`
            }
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-white truncate">${this.currentUser.username}</p>
              ${isAniListUser ? `
                <div class="anilist-badge">
                  <svg class="anilist-icon" viewBox="0 0 24 24">
                    <path d="M6.361 2.943 0 21.056h4.06l1.077-3.133h6.875l1.077 3.133H17.15L10.789 2.943zm1.77 5.392 2.18 6.336H5.951zm10.365 9.794V8.113c3.02.501 4.473 2.273 4.473 4.728 0 2.456-1.453 4.227-4.473 4.728z"/>
                  </svg>
                  AniList
                </div>` : ''}
            </div>
          </div>
        </div>
      `;
    }

    dd.innerHTML = `
      ${userInfoSection}
      <div class="py-2">
        <a href="/profile" class="flex items-center px-4 py-2 text-sm text-white hover:bg-white/5 transition-colors" role="menuitem">
          <svg class="w-4 h-4 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
          </svg>
          Profile
        </a>
        <a href="/watchlist" class="flex items-center px-4 py-2 text-sm text-white hover:bg-white/5 transition-colors" role="menuitem">
          <svg class="w-4 h-4 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path>
          </svg>
          Watchlist
        </a>
        <a href="/settings" class="flex items-center px-4 py-2 text-sm text-white hover:bg-white/5 transition-colors" role="menuitem">
          <svg class="w-6 h-6 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M11.049 2.927c.3-.921 1.603-.921 1.902 0a1.724 1.724 0 002.573.948c.833-.48 1.86.448 1.38 1.28a1.724 1.724 0 00.947 2.573c.921.3.921 1.603 0 1.902a1.724 1.724 0 00-.947 2.573c.48.832-.448 1.86-1.28 1.38a1.724 1.724 0 00-2.573.947c-.3.921-1.603.921-1.902 0a1.724 1.724 0 00-2.573-.947c-.832.48-1.86-.448-1.38-1.28a1.724 1.724 0 00-.947-2.573c-.921-.3-.921-1.603 0-1.902a1.724 1.724 0 00.947-2.573c-.48-.832.448-1.86 1.28-1.38.97.56 2.196.082 2.573-.947z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          Settings
        </a>
        <hr class="border-white/10 my-2">
        <button id="logoutBtnWidget" class="flex items-center w-full px-4 py-2 text-sm text-white hover:bg-white/5 transition-colors" role="menuitem">
          <svg class="w-4 h-4 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
          </svg>
          Logout
        </button>
      </div>
    `;
    document.body.appendChild(dd);
    this.profileDropdown = dd;

    // wire logout
    this.logoutBtnWidget = document.getElementById('logoutBtnWidget');
    this.logoutBtnWidget?.addEventListener('click', (e) => {
      e.stopPropagation();
      this.handleLogout();
    });

    // wire sync button if it exists
    const syncBtn = document.getElementById('syncAnilistBtnDropdown');
    if (syncBtn) {
      syncBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.profileDropdown.classList.add('hidden');
        this.showSyncModal();
      });
    }
  }

  // Position dropdown absolutely under the button
  positionDropdownUnderButton(buttonEl, dropdownEl) {
    if (!buttonEl || !dropdownEl) return;
    const rect = buttonEl.getBoundingClientRect();
    const top = rect.bottom + window.scrollY + 8; // 8px gap
    // Align dropdown's right edge to button's right edge
    const right = window.innerWidth - rect.right - window.scrollX;
    dropdownEl.style.position = 'absolute';
    dropdownEl.style.top = `${top}px`;
    dropdownEl.style.right = `${right}px`;
    dropdownEl.style.left = 'auto';
  }

  updateUI() {
    if (this.isLoggedIn && this.currentUser) {
      // hide login button and show profile button/avatar
      this.loginBtnWidget?.classList.add('hidden');
      this.loginBtnWidget?.classList.remove('opacity-0');
      if (this.profileBoxWidget) {
        this.profileBoxWidget.classList.remove('hidden', 'opacity-0');
        this.profileBoxWidget.classList.add('flex');
        this.renderProfileButton();
      }
    } else {
      // show login button and remove profile button
      this.loginBtnWidget?.classList.remove('hidden', 'opacity-0');
      if (this.profileBoxWidget) {
        this.profileBoxWidget.classList.add('hidden', 'opacity-0');
        this.profileBoxWidget.classList.remove('flex');
        this.profileBoxWidget.innerHTML = '';
      }
      if (this.profileDropdown) this.profileDropdown.classList.add('hidden');
    }
  }

  // Check server session instead of localStorage
  async checkServerSession() {
    try {
      const response = await fetch('/api/me', {
        method: 'GET',
        credentials: 'same-origin',
      });
      
      if (response.ok) {
        const userData = await response.json();
        if (userData && userData.username) {
          this.currentUser = userData;
          this.isLoggedIn = true;
        } else {
          this.currentUser = null;
          this.isLoggedIn = false;
        }
      } else {
        this.currentUser = null;
        this.isLoggedIn = false;
      }
    } catch (error) {
      console.warn('Error checking session:', error);
      this.currentUser = null;
      this.isLoggedIn = false;
    } finally {
      // Always update UI after session check completes
      this.updateUI();
    }
  }
}

// Initialize after DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.yumeAnimeLoginWidget = new LoginWidget();
});
