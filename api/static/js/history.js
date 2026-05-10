document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('history-grid');
    const emptyState = document.getElementById('history-empty');
    const clearAllBtn = document.getElementById('history-clear-all');
    const filterBtns = document.querySelectorAll('.tab-btn[data-filter]');
    let currentFilter = 'all'; // all, progress, completed

    // Helper: format seconds to mm:ss or hh:mm:ss
    function formatTime(seconds) {
        if (!seconds || isNaN(seconds) || seconds <= 0) return '00:00';
        seconds = Math.floor(seconds);
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        if (h > 0) {
            return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        }
        return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }

    // Helper: relative time
    function timeAgo(timestamp) {
        if (!timestamp) return '';
        const diff = Date.now() - timestamp;
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'Just now';
        if (mins < 60) return mins + 'm ago';
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return hrs + 'h ago';
        const days = Math.floor(hrs / 24);
        if (days < 7) return days + 'd ago';
        return Math.floor(days / 7) + 'w ago';
    }

    // Collect history entries
    function getHistoryEntries() {
        const entries = [];
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith('yumeHistory_')) {
                    try {
                        const data = JSON.parse(localStorage.getItem(key));
                        if (data && data.animeId) {
                            data._key = key;
                            // Update completion status to be safe
                            if (data.duration > 0 && data.timestamp / data.duration >= 0.9) {
                                data.completed = true;
                            }
                            entries.push(data);
                        }
                    } catch (e) { }
                }
            }
        } catch (e) { }
        
        // Sort by watchedAt (most recent first)
        entries.sort((a, b) => (b.watchedAt || 0) - (a.watchedAt || 0));
        return entries;
    }

    // Deduplicate: keep only the latest entry per anime
    function dedupeByAnime(entries) {
        const seen = new Map();
        const result = [];
        for (const entry of entries) {
            if (!seen.has(entry.animeId)) {
                seen.set(entry.animeId, true);
                result.push(entry);
            }
        }
        return result;
    }

    function createCardHTML(entry) {
        const progress = (entry.duration > 0) ? Math.min((entry.timestamp / entry.duration) * 100, 100) : 0;
        const posterSrc = entry.poster || `https://via.placeholder.com/320x180/111/333?text=${encodeURIComponent(entry.animeName || 'Anime')}`;
        
        const isCompleted = entry.completed;
        const timeAgoText = timeAgo(entry.watchedAt);
        const titleText = entry.episodeTitle ? `${entry.epNum}. ${entry.episodeTitle}` : (entry.animeName || entry.animeId.replace(/-/g, ' '));

        return `
            <div class="anime-card" style="position: relative;" data-key="${entry._key}">
                <a href="/watch/${entry.animeId}/ep-${entry.epNum}" style="display: block; position: relative;">
                    <div class="anime-card-poster" style="aspect-ratio: 16/9;">
                        <img src="${posterSrc}" alt="${entry.animeName || ''}" loading="lazy" style="object-fit: cover;">
                        
                        <!-- Badges Overlay -->
                        <div style="position: absolute; top: 8px; left: 8px; display: flex; flex-direction: column; gap: 4px; z-index: 2;">
                            <span class="badge" style="background: rgba(0,0,0,0.7); backdrop-filter: blur(4px);">EP ${entry.epNum}</span>
                            ${isCompleted ? '<span class="badge" style="background: var(--success); color: #fff;">Completed</span>' : ''}
                        </div>

                        <!-- Remove Button -->
                        <button class="history-remove-btn" data-key="${entry._key}" data-anime-id="${entry.animeId}" data-ep="${entry.epNum}" title="Remove from history" style="position: absolute; top: 8px; right: 8px; z-index: 5; background: rgba(0,0,0,0.6); color: #fff; border: none; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; cursor: pointer; backdrop-filter: blur(4px);">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>

                        <div class="anime-card-overlay">
                            <span class="btn btn-primary btn-sm">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" style="margin-right:4px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                                Resume
                            </span>
                        </div>

                        <!-- Progress Bar -->
                        ${entry.duration > 0 ? `
                        <div style="position: absolute; bottom: 0; left: 0; width: 100%; height: 4px; background: rgba(255,255,255,0.2);">
                            <div style="height: 100%; width: ${progress}%; background: var(--accent);"></div>
                        </div>
                        ` : ''}
                    </div>
                </a>
                <div class="anime-card-info" style="padding-top: 10px;">
                    <h3 class="anime-card-title" style="margin-bottom: 4px; font-size: 0.95rem;">${titleText}</h3>
                    <div class="anime-card-meta" style="justify-content: space-between;">
                        <span style="color: var(--text-muted);">${entry.animeName}</span>
                        ${entry.duration > 0 ? `<span style="font-size: 0.75rem;">${formatTime(entry.timestamp)} / ${formatTime(entry.duration)}</span>` : ''}
                    </div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">${timeAgoText}</div>
                </div>
            </div>
        `;
    }

    function render() {
        const allEntries = getHistoryEntries();
        const deduped = dedupeByAnime(allEntries);

        let filtered = deduped;
        if (currentFilter === 'progress') {
            filtered = deduped.filter(e => !e.completed && e.duration > 0 && (e.timestamp / e.duration) < 0.9);
        } else if (currentFilter === 'completed') {
            filtered = deduped.filter(e => e.completed || (e.duration > 0 && (e.timestamp / e.duration) >= 0.9));
        }

        if (filtered.length === 0) {
            grid.style.display = 'none';
            emptyState.style.display = 'block';
            clearAllBtn.style.display = 'none';
        } else {
            grid.style.display = 'grid';
            emptyState.style.display = 'none';
            clearAllBtn.style.display = 'inline-flex';
            
            grid.innerHTML = filtered.map(createCardHTML).join('');

            // Attach remove listeners
            grid.querySelectorAll('.history-remove-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const key = btn.getAttribute('data-key');
                    const animeId = btn.getAttribute('data-anime-id');
                    const epNum = btn.getAttribute('data-ep');
                    
                    try { localStorage.removeItem(key); } catch (err) {}
                    try { localStorage.removeItem(`yumeResume_${animeId}_ep${epNum}`); } catch (err) {}
                    
                    const card = btn.closest('.anime-card');
                    card.style.transition = 'opacity 0.3s, transform 0.3s';
                    card.style.opacity = '0';
                    card.style.transform = 'scale(0.95)';
                    
                    setTimeout(() => {
                        render();
                    }, 300);
                });
            });
        }
    }

    // Filter tabs
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.getAttribute('data-filter');
            render();
        });
    });

    // Clear all
    clearAllBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to clear all your watch history? This cannot be undone.')) {
            const entries = getHistoryEntries();
            for (const entry of entries) {
                try {
                    localStorage.removeItem(entry._key);
                    localStorage.removeItem(`yumeResume_${entry.animeId}_ep${entry.epNum}`);
                } catch (e) { }
            }
            render();
        }
    });

    // Initial render
    render();
});
