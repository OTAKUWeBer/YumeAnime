document.addEventListener('DOMContentLoaded', () => {
        const watchlistContent = document.getElementById('watchlist-content');
        const watchlistTabs = document.getElementById('watchlist-tabs');
        const searchInput = document.getElementById('local-search-input');

        // Sentinel for infinite scroll
        let sentinel = null;

        let currentStatus = '';
        let searchQuery = '';
        let currentPage = 1;
        let isLoading = false;
        let hasMore = true;

        // Status labels mapping
        const statusLabels = {
            'watching': 'Watching',
            'completed': 'Completed',
            'on_hold': 'On Hold',
            'dropped': 'Dropped',
            'plan_to_watch': 'Plan to Watch'
        };

        // Fetch stats
        async function fetchStats() {
            try {
                const response = await fetch('/api/watchlist/stats');
                const stats = await response.json();

                if (document.getElementById('stat-watching')) document.getElementById('stat-watching').textContent = stats.watching || 0;
                if (document.getElementById('stat-total')) document.getElementById('stat-total').textContent = stats.total || stats.total_anime || 0;
                if (document.getElementById('stat-days') && stats.minutes_watched) {
                    document.getElementById('stat-days').textContent = (stats.minutes_watched / 1440).toFixed(1);
                }
            } catch (e) {
                console.error('Stats error:', e);
            }
        }

        // Create and append loading sentinel
        function createSentinel() {
            if (sentinel) sentinel.remove();

            const sentinelDiv = document.createElement('div');
            sentinelDiv.id = 'watchlist-sentinel';
            sentinelDiv.className = 'watchlist-loading';
            sentinelDiv.style.opacity = '0';
            sentinelDiv.style.minHeight = '1px';
            sentinelDiv.style.transition = 'opacity 0.2s';
            sentinelDiv.innerHTML = `
                <div class="loading-spinner" style="margin: 0 auto;"></div>
                <p class="text-muted" style="margin-top: var(--space-md);">Loading more...</p>
            `;
            if (watchlistContent && watchlistContent.parentNode) {
                watchlistContent.parentNode.appendChild(sentinelDiv);
            }
            return sentinelDiv;
        }

        // Fetch watchlist
        // Helper to get a fresh page token from the cookie
        function getFreshPageToken() {
            const m = document.cookie.match(/(^|;)\s*__pt=([^;]+)/);
            return m ? decodeURIComponent(m[2]) : '';
        }

        async function fetchWatchlist(status = '', page = 1, append = false, _retry = false) {
            if (isLoading) return;
            isLoading = true;

            if (!append) {
                if (watchlistContent) {
                    watchlistContent.innerHTML = `
                        <div class="watchlist-loading">
                            <div class="loading-spinner" style="margin: 0 auto;"></div>
                            <p class="text-muted" style="margin-top: var(--space-md);">Loading watchlist...</p>
                        </div>
                    `;
                }
                currentPage = 1;
                hasMore = true;
                if (!sentinel) sentinel = createSentinel();
                sentinel.style.display = 'block';
                sentinel.style.opacity = '0';
            } else {
                if (sentinel) sentinel.style.opacity = '1';
            }

            try {
                const params = new URLSearchParams({ page, limit: 30 });
                if (status) params.append('status', status);

                const response = await fetch(`/api/watchlist/paginated?${params}`);

                // Handle 403 — page token missing/stale. Retry once with fresh token.
                if (response.status === 403 && !_retry) {
                    isLoading = false;
                    const freshPt = getFreshPageToken();
                    if (freshPt) {
                        // Update the global fetch wrapper's token
                        const metaEl = document.querySelector('meta[name="pt"]');
                        if (metaEl) metaEl.setAttribute('content', freshPt);
                    }
                    // Small delay then retry once
                    await new Promise(r => setTimeout(r, 500));
                    return fetchWatchlist(status, page, append, true);
                }

                const data = await response.json();

                if (data.error) {
                    throw new Error(data.error);
                }

                let items = data.data || [];
                const pagination = data.pagination || {};

                // Basic local search filtering
                if (searchQuery) {
                    items = items.filter(i => {
                        const t = i.anime_title ? i.anime_title.toLowerCase() : '';
                        return t.includes(searchQuery.toLowerCase());
                    });
                }

                hasMore = pagination.has_next && page < pagination.total_pages && !searchQuery;

                if (items.length === 0 && !append) {
                    if (watchlistContent) {
                        watchlistContent.innerHTML = `
                            <div class="watchlist-empty">
                                <div style="font-size: 4rem; margin-bottom: var(--space-md);">📚</div>
                                <h3>No anime found</h3>
                                <p class="text-muted" style="margin-bottom: var(--space-lg);">
                                    ${searchQuery ? 'No results match your search.' : 'Start adding anime to track your progress!'}
                                </p>
                                <a href="{{ url_for('main.home_routes.home') }}" class="btn btn-primary">Browse Anime</a>
                            </div>
                        `;
                    }
                    if (sentinel) sentinel.style.display = 'none';
                    return;
                }

                const itemsHTML = items.map(item => {
                    const statusClass = 'status-dot-' + (item.status || 'other');

                    // Media status hint (Airing, Finished, etc.)
                    const mediaHints = {
                        'RELEASING': { label: 'Airing', color: '#2ecc71', bg: 'rgba(46,204,113,0.12)' },
                        'FINISHED': { label: 'Finished', color: '#3498db', bg: 'rgba(52,152,219,0.12)' },
                        'NOT_YET_RELEASED': { label: 'Upcoming', color: '#f1c40f', bg: 'rgba(241,196,15,0.12)' },
                        'CANCELLED': { label: 'Cancelled', color: '#e74c3c', bg: 'rgba(231,76,60,0.12)' },
                        'HIATUS': { label: 'Hiatus', color: '#e67e22', bg: 'rgba(230,126,34,0.12)' },
                    };
                    const hint = mediaHints[item.media_status] || null;
                    const hintHTML = hint
                        ? `<span style="display:inline-flex;align-items:center;gap:3px;font-size:0.6rem;color:${hint.color};background:${hint.bg};padding:1px 6px;border-radius:3px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;white-space:nowrap;flex-shrink:0;line-height:1.4;vertical-align:middle;margin-left:6px;"><span style="width:4px;height:4px;border-radius:50%;background:${hint.color};display:inline-block;flex-shrink:0;"></span>${hint.label}</span>`
                        : '';

                    // We encode item data as JSON string in data attribute to populate the modal later easily
                    const itemData = encodeURIComponent(JSON.stringify(item));

                    return `
                    <div class="list-row" data-id="${item.anime_id}" onclick="openEditModal(event, this)" data-item="${itemData}">
                        <div>
                            <div class="status-indicator ${statusClass}" title="${statusLabels[item.status] || item.status || 'Unknown'}"></div>
                        </div>
                        
                        <div style="display: flex; align-items: center; gap: 16px; min-width: 0;">
                            <img src="${item.poster_url || item.poster || 'https://via.placeholder.com/48x68?text=No+Image'}" alt="${item.anime_title}" class="row-cover" loading="lazy">
                            <div style="display:flex;align-items:center;flex-wrap:wrap;gap:2px;min-width:0;">
                                <span class="row-title" style="flex-shrink:1;">${item.anime_title}</span>${hintHTML}
                            </div>
                        </div>
                        
                        <div class="row-score">
                            ${item.score && item.score > 0 ? item.score : '-'}
                        </div>
                        
                        <div class="row-progress">
                            <span class="ep-text">${item.watched_episodes || 0} / ${item.total_episodes || '?'}</span>
                        </div>
                    </div>
                `}).join('');

                if (watchlistContent) {
                    if (!append) {
                        watchlistContent.innerHTML = itemsHTML;
                    } else {
                        // remove loading state if needed
                        const loader = watchlistContent.querySelector('.watchlist-loading');
                        if (loader) loader.remove();
                        watchlistContent.insertAdjacentHTML('beforeend', itemsHTML);
                    }
                }

            } catch (e) {
                console.error('Watchlist error:', e);
                if (!append && watchlistContent) {
                    watchlistContent.innerHTML = `
                        <div class="watchlist-empty">
                            <div style="font-size: 4rem; margin-bottom: var(--space-md);">⚠️</div>
                            <h3>Error loading watchlist</h3>
                            <p class="text-muted">${e.message}</p>
                        </div>
                    `;
                }
            } finally {
                isLoading = false;
                if (!hasMore && sentinel) {
                    sentinel.style.display = 'none';
                } else if (sentinel) {
                    sentinel.style.opacity = '0';
                }
            }
        }

        // Intersection Observer
        function initInfiniteScroll() {
            if (!sentinel) sentinel = createSentinel();

            const observer = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting && hasMore && !isLoading && !searchQuery) {
                    sentinel.style.opacity = '1';
                    currentPage++;
                    fetchWatchlist(currentStatus, currentPage, true);
                }
            }, {
                root: null,
                rootMargin: '100px',
                threshold: 0.1
            });

            if (sentinel) observer.observe(sentinel);
        }

        // Global functions
        window.updateStatus = async function (animeId, status) {
            try {
                const response = await fetch('/api/watchlist/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ anime_id: animeId, action: 'status', status })
                });
                const data = await response.json();
                if (!data.success) {
                    alert(data.message || 'Failed to update status');
                } else {
                    if (currentStatus && currentStatus !== status && currentStatus !== '') {
                        const item = document.querySelector(`.list-row[data-id="${animeId}"]`);
                        if (item) {
                            item.style.transform = 'scale(0.95)';
                            item.style.opacity = '0';
                            setTimeout(() => {
                                item.remove();
                                if (document.querySelectorAll('.list-row').length === 0) {
                                    fetchWatchlist(currentStatus, 1, false);
                                }
                            }, 200);
                        }
                    } else {
                        // Just update the dot color
                        const item = document.querySelector(`.list-row[data-id="${animeId}"]`);
                        if (item) {
                            const indicator = item.querySelector('.status-indicator');
                            if (indicator) {
                                indicator.className = 'status-indicator status-dot-' + status;
                            }
                        }
                    }
                    fetchStats();
                }
            } catch (e) {
                console.error('Update error:', e);
            }
        };

        // Modal Handlers
        let activeEditItemId = null;

        // Convert old DB statuses to AniList's standard
        const localToAnilistStatus = {
            'watching': 'CURRENT',
            'completed': 'COMPLETED',
            'on_hold': 'PAUSED',
            'dropped': 'DROPPED',
            'plan_to_watch': 'PLANNING'
        };

        window.openEditModal = function (e, rowElement) {
            e.preventDefault();
            e.stopPropagation();
            const itemStr = rowElement.getAttribute('data-item');
            if (!itemStr) return;
            const item = JSON.parse(decodeURIComponent(itemStr));

            activeEditItemId = item.anime_id;

            document.getElementById('edit-modal-title').textContent = item.anime_title;
            document.getElementById('edit-modal-poster').src = item.poster_url || item.poster;
            document.getElementById('edit-modal-link').href = '/anime/' + item.anime_id;

            // Set up the Watch button — continue from next unwatched episode
            const watchedEps = item.watched_episodes || 0;
            const nextEp = watchedEps + 1;

            // Determine max available episode
            const totalEps = item.total_episodes || 0;
            const nextAiring = item.next_airing_episode || 0;
            let maxAvailable = totalEps;
            if (nextAiring > 0) {
                // If it's airing, the max available is the one before the next airing
                maxAvailable = nextAiring - 1;
            } else if (totalEps === 0 && item.media_status !== 'RELEASING' && item.media_status !== 'NOT_YET_RELEASED') {
                // In some cases totalEps is 0 but it's finished (rare but possible), default to watchedEps
                maxAvailable = watchedEps;
            }

            let watchText = '';
            let targetEp = nextEp;

            if (maxAvailable > 0 && nextEp > maxAvailable) {
                // User has caught up or finished
                if (item.media_status === 'RELEASING') {
                    // Ongoing show
                    targetEp = maxAvailable; // Point them to the latest they CAN watch, or just leave it at the last available
                    watchText = `Caught Up (Wait for Ep ${nextAiring})`;
                } else {
                    // Completed show or movie
                    targetEp = maxAvailable; // Last episode
                    watchText = maxAvailable === 1 ? 'Watch Again' : `Completed (Re-watch Ep ${maxAvailable})`;
                }
            } else {
                // There are still eps to watch
                if (watchedEps === 0) {
                    watchText = 'Start Watching';
                    targetEp = 1;
                } else {
                    watchText = `Continue Ep ${nextEp}`;
                    targetEp = nextEp;
                }
            }

            const watchLink = document.getElementById('edit-modal-watch');
            watchLink.href = '/watch/' + item.anime_id + '/ep-' + targetEp;
            watchLink.textContent = '';
            watchLink.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="5 3 19 12 5 21 5 3"/></svg> ${watchText}`;

            // Map status
            let mappedStatus = localToAnilistStatus[item.status] || item.status || 'CURRENT';
            // It might already be AniList formatted if backend uses AniList proxy
            if (!['CURRENT', 'COMPLETED', 'PAUSED', 'DROPPED', 'PLANNING'].includes(mappedStatus)) {
                mappedStatus = 'CURRENT';
            }
            document.getElementById('edit-status').value = mappedStatus;

            const displayTotalEps = item.total_episodes || 0;
            const totalEpsDisplay = displayTotalEps > 0 ? displayTotalEps : '?';
            document.getElementById('edit-episode-label').textContent = `Episode Progress (${totalEpsDisplay} EPS)`;

            // Set max attribute on progress input to limit episode count
            const progressInput = document.getElementById('edit-progress');
            progressInput.value = item.watched_episodes || 0;
            if (displayTotalEps > 0) {
                progressInput.max = displayTotalEps;
                // Clamp current value if it exceeds max
                if (parseInt(progressInput.value) > displayTotalEps) {
                    progressInput.value = displayTotalEps;
                }
            } else {
                progressInput.removeAttribute('max');
            }

            document.getElementById('edit-score').value = item.score || '';
            document.getElementById('edit-rewatches').value = item.repeat || 0;
            document.getElementById('edit-notes').value = item.notes || '';

            // Format dates (YYYY-MM-DD expected for <input type="date">)
            const formatDateForInput = (dateObj) => {
                if (!dateObj || (!dateObj.year && !dateObj.month && !dateObj.day)) return '';
                const y = dateObj.year || new Date().getFullYear();
                const m = String(dateObj.month || 1).padStart(2, '0');
                const d = String(dateObj.day || 1).padStart(2, '0');
                return `${y}-${m}-${d}`;
            };

            document.getElementById('edit-start-date').value = formatDateForInput(item.startedAt);
            document.getElementById('edit-end-date').value = formatDateForInput(item.completedAt);

            document.getElementById('edit-modal-overlay').classList.add('active');
        };

        window.closeEditModal = function () {
            document.getElementById('edit-modal-overlay').classList.remove('active');
            activeEditItemId = null;
        };

        window.saveEntry = async function () {
            if (!activeEditItemId) return;

            // Parse dates back to AniList format
            const parseDateInput = (val) => {
                if (!val) return { year: null, month: null, day: null };
                const dt = new Date(val);
                if (isNaN(dt.getTime())) return { year: null, month: null, day: null };
                // Using UTC parts to avoid timezone shift on local boundary selection
                return {
                    year: dt.getUTCFullYear(),
                    month: dt.getUTCMonth() + 1,
                    day: dt.getUTCDate()
                };
            };

            const progressInput = document.getElementById('edit-progress');
            let progressValue = parseInt(progressInput.value) || 0;
            const maxEps = parseInt(progressInput.max);

            // Clamp progress to total episodes if known
            if (!isNaN(maxEps) && maxEps > 0 && progressValue > maxEps) {
                progressValue = maxEps;
                progressInput.value = maxEps;
            }

            const payload = {
                anime_id: activeEditItemId,
                status: document.getElementById('edit-status').value,
                progress: progressValue,
                score: parseFloat(document.getElementById('edit-score').value) || 0,
                repeat: parseInt(document.getElementById('edit-rewatches').value) || 0,
                notes: document.getElementById('edit-notes').value,
                startedAt: parseDateInput(document.getElementById('edit-start-date').value),
                completedAt: parseDateInput(document.getElementById('edit-end-date').value)
            };

            const btn = document.querySelector('.btn-save');
            const originalText = btn.textContent;
            btn.textContent = 'Saving...';
            btn.disabled = true;

            try {
                const response = await fetch('/api/watchlist/advanced_update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (data.success) {
                    closeEditModal();

                    const row = document.querySelector(`.list-row[data-id="${activeEditItemId}"]`);
                    if (row) {
                        try {
                            const itemDataStr = row.getAttribute('data-item');
                            const itemDataObj = itemDataStr ? JSON.parse(decodeURIComponent(itemDataStr)) : {};

                            // Map AniList status back to local status for the UI
                            const anilistToLocalStatus = {
                                'CURRENT': 'watching',
                                'COMPLETED': 'completed',
                                'PAUSED': 'on_hold',
                                'DROPPED': 'dropped',
                                'PLANNING': 'plan_to_watch',
                                'REPEATING': 'watching'
                            };

                            const newLocalStatus = anilistToLocalStatus[payload.status] || payload.status.toLowerCase();

                            // Check if row should be removed due to active filter tab
                            if (currentStatus && currentStatus !== newLocalStatus && currentStatus !== '') {
                                row.style.transform = 'scale(0.95)';
                                row.style.opacity = '0';
                                setTimeout(() => {
                                    row.remove();
                                    if (document.querySelectorAll('.list-row').length === 0) {
                                        fetchWatchlist(currentStatus, 1, false);
                                    }
                                    fetchStats();
                                }, 200);
                                return;
                            }

                            // Update stored item data
                            itemDataObj.status = newLocalStatus;
                            itemDataObj.watched_episodes = payload.progress;
                            itemDataObj.score = payload.score;
                            itemDataObj.repeat = payload.repeat;
                            itemDataObj.notes = payload.notes;
                            itemDataObj.startedAt = payload.startedAt;
                            itemDataObj.completedAt = payload.completedAt;

                            row.setAttribute('data-item', encodeURIComponent(JSON.stringify(itemDataObj)));

                            // Update DOM visually
                            const indicator = row.querySelector('.status-indicator');
                            if (indicator) {
                                indicator.className = 'status-indicator status-dot-' + newLocalStatus;
                                indicator.title = statusLabels[newLocalStatus] || newLocalStatus;
                            }

                            const scoreEl = row.querySelector('.row-score');
                            if (scoreEl) {
                                scoreEl.textContent = payload.score && payload.score > 0 ? payload.score : '-';
                            }

                            const progressSpan = row.querySelector('.row-progress .ep-text');
                            if (progressSpan) {
                                progressSpan.textContent = `${payload.progress} / ${itemDataObj.total_episodes || '?'}`;
                            }
                        } catch (e) {
                            console.error("Error updating row visually:", e);
                            fetchWatchlist(currentStatus, 1, false); // fallback
                        }
                    } else {
                        fetchWatchlist(currentStatus, 1, false); // fallback
                    }

                    fetchStats();
                } else {
                    // Don't show confusing 'Missing page token' to user
                    const errMsg = data.message || 'Unknown error';
                    if (errMsg.toLowerCase().includes('page token') || errMsg.toLowerCase().includes('forbidden')) {
                        alert('Session expired. Please refresh the page and try again.');
                    } else {
                        alert('Error saving: ' + errMsg);
                    }
                }
            } catch (e) {
                alert('Connection error. Please refresh the page and try again.');
                console.error(e);
            } finally {
                btn.textContent = originalText;
                btn.disabled = false;
            }
        };

        window.deleteEntry = async function () {
            if (!activeEditItemId) return;
            if (!confirm("Are you sure you want to completely remove this from your watchlist?")) return;

            const btn = document.getElementById('edit-delete-btn');
            btn.disabled = true;
            btn.innerHTML = '...';

            try {
                const response = await fetch('/api/watchlist/remove', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ anime_id: activeEditItemId })
                });
                const data = await response.json();
                if (data.success) {
                    closeEditModal();
                    fetchWatchlist(currentStatus, 1, false);
                } else {
                    alert('Error deleting: ' + (data.message || 'Unknown error'));
                }
            } catch (e) {
                alert('Connection error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>`;
            }
        };

        // Tab handlers
        if (watchlistTabs) {
            watchlistTabs.querySelectorAll('.filter-btn').forEach(tab => {
                tab.addEventListener('click', function () {
                    const active = watchlistTabs.querySelector('.active');
                    if (active) active.classList.remove('active');
                    this.classList.add('active');
                    currentStatus = this.dataset.status;

                    currentPage = 1;
                    hasMore = true;
                    isLoading = false;
                    fetchWatchlist(currentStatus, 1, false);
                });
            });
        }

        // Local search handler
        if (searchInput) {
            let debounceTimer;
            searchInput.addEventListener('input', function () {
                clearTimeout(debounceTimer);
                searchQuery = this.value;
                debounceTimer = setTimeout(() => {
                    currentPage = 1;
                    fetchWatchlist(currentStatus, 1, false);
                }, 300);
            });
        }

        // Close modal when clicking overlay (outside modal) — critical for mobile touch
        const editOverlay = document.getElementById('edit-modal-overlay');
        if (editOverlay) {
            editOverlay.addEventListener('click', function (e) {
                if (e.target === editOverlay) {
                    closeEditModal();
                }
            });
        }

        // ESC key closes edit modal
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                const overlay = document.getElementById('edit-modal-overlay');
                if (overlay && overlay.classList.contains('active')) {
                    closeEditModal();
                }
            }
        });

        // +/- buttons for episode progress in the edit modal
        window.adjustEditProgress = function (delta) {
            const input = document.getElementById('edit-progress');
            const current = parseInt(input.value) || 0;
            const max = parseInt(input.max);
            let newVal = current + delta;
            if (newVal < 0) newVal = 0;
            if (!isNaN(max) && max > 0 && newVal > max) newVal = max;
            input.value = newVal;

            // Auto-set status to COMPLETED when reaching max episodes
            if (!isNaN(max) && max > 0 && newVal === max) {
                document.getElementById('edit-status').value = 'COMPLETED';
            }
            // Auto-set status to CURRENT if decrementing from completed
            if (!isNaN(max) && max > 0 && newVal < max && document.getElementById('edit-status').value === 'COMPLETED') {
                document.getElementById('edit-status').value = 'CURRENT';
            }
        };

        // Initialize
        fetchStats();
        fetchWatchlist();
        initInfiniteScroll();

    });
