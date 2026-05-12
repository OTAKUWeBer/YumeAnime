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
        const posterSrc = entry.episodeImage || entry.poster || `https://via.placeholder.com/320x180/111/333?text=${encodeURIComponent(entry.animeName || 'Anime')}`;
        const fallbackPoster = entry.poster || `https://via.placeholder.com/320x180/111/333?text=${encodeURIComponent(entry.animeName || 'Anime')}`;
        
        const isCompleted = entry.completed;
        const timeAgoText = timeAgo(entry.watchedAt);
        const titleText = entry.episodeTitle ? `${entry.epNum}. ${entry.episodeTitle}` : (entry.animeName || entry.animeId.replace(/-/g, ' '));

        return `
            <div class="anime-card history-card" data-key="${entry._key}">
                <a href="/watch/${entry.animeId}/ep-${entry.epNum}" class="history-card-poster-link">
                    <div class="anime-card-poster" style="aspect-ratio: 16/9;">
                        <img src="${posterSrc}" alt="${entry.animeName || ''}" loading="lazy" onerror="if(this.src != '${fallbackPoster}') { this.src='${fallbackPoster}'; } else { this.src='https://via.placeholder.com/320x180/111/333?text=No+Image'; }">
                        
                        <div class="history-card-badges">
                            <span class="history-badge ep">EP ${entry.epNum}</span>
                            ${isCompleted ? '<span class="history-badge completed">Completed</span>' : ''}
                        </div>

                        <button class="history-remove-btn" data-key="${entry._key}" data-anime-id="${entry.animeId}" data-ep="${entry.epNum}" title="Remove from history">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>

                        <div class="anime-card-overlay">
                            <div class="play-icon-circle">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style="margin-left: 2px;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            </div>
                        </div>

                        ${entry.duration > 0 ? `
                        <div class="history-progress-wrap">
                            <div class="history-progress-bar" style="width: ${progress}%;"></div>
                        </div>
                        ` : ''}
                    </div>
                </a>
                <div class="history-card-details">
                    <h3 class="history-card-title">${titleText}</h3>
                    <div class="history-card-anime">${entry.animeName}</div>
                    <div class="history-card-footer">
                        <span class="history-card-time">${timeAgoText}</span>
                        ${entry.duration > 0 ? `<span class="history-card-duration">${formatTime(entry.timestamp)} / ${formatTime(entry.duration)}</span>` : ''}
                    </div>
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
