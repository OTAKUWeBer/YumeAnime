/**
 * Manga Module — client-side logic for manga pages
 * Handles source switching, search, reader controls, and NSFW filtering.
 */

(function () {
    'use strict';

    // ── NSFW Filter ──────────────────────────────────────────────────
    const NSFW_KEY = 'yume_manga_hide_nsfw';

    function isNsfwHidden() {
        return localStorage.getItem(NSFW_KEY) === 'true';
    }

    function applyNsfwFilter() {
        const hide = isNsfwHidden();
        document.querySelectorAll('[data-is-adult="true"]').forEach(el => {
            el.style.display = hide ? 'none' : '';
        });
    }

    // ── Source Tab Switching ──────────────────────────────────────────
    function initSourceTabs() {
        const tabs = document.querySelectorAll('.manga-source-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', function (e) {
                // If it's an anchor, let it navigate
                if (this.tagName === 'A') return;
                e.preventDefault();
                const source = this.dataset.source;
                if (source) {
                    const url = new URL(window.location);
                    url.searchParams.set('source', source);
                    url.searchParams.delete('q');
                    window.location.href = url.pathname + '?' + url.searchParams.toString();
                }
            });
        });
    }

    // ── Manga Search ─────────────────────────────────────────────────
    function initMangaSearch() {
        const form = document.getElementById('manga-search-form');
        if (!form) return;

        form.addEventListener('submit', function (e) {
            const input = form.querySelector('input[name="q"]');
            const source = form.querySelector('input[name="source"]');
            if (!input || !input.value.trim()) {
                e.preventDefault();
                return;
            }
        });
    }

    // ── Reader Controls ──────────────────────────────────────────────
    function initReader() {
        const readerImages = document.querySelector('.manga-reader-images');
        if (!readerImages) return;

        // Lazy load images
        const images = readerImages.querySelectorAll('img[data-src]');
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        observer.unobserve(img);

                        // Remove loading placeholder
                        const placeholder = img.previousElementSibling;
                        if (placeholder && placeholder.classList.contains('page-loading')) {
                            placeholder.remove();
                        }
                    }
                });
            }, { rootMargin: '600px' });

            images.forEach(img => observer.observe(img));
        } else {
            // Fallback: load all
            images.forEach(img => {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            });
        }

        // Keyboard navigation
        document.addEventListener('keydown', function (e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            const prevBtn = document.getElementById('reader-prev');
            const nextBtn = document.getElementById('reader-next');

            if (e.key === 'ArrowLeft' && prevBtn && !prevBtn.disabled) {
                prevBtn.click();
            } else if (e.key === 'ArrowRight' && nextBtn && !nextBtn.disabled) {
                nextBtn.click();
            }
        });

        // Progress tracking
        let ticking = false;
        window.addEventListener('scroll', function () {
            if (!ticking) {
                requestAnimationFrame(() => {
                    updateReadProgress();
                    ticking = false;
                });
                ticking = true;
            }
        });
    }

    function updateReadProgress() {
        const progressBar = document.getElementById('reader-progress');
        if (!progressBar) return;

        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = docHeight > 0 ? Math.min((scrollTop / docHeight) * 100, 100) : 0;
        progressBar.style.width = progress + '%';
    }

    // ── Image Error Handling ─────────────────────────────────────────
    function initImageErrors() {
        document.querySelectorAll('.manga-card-poster img, .manga-detail-cover img').forEach(img => {
            img.addEventListener('error', function () {
                this.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iIzFhMWEyZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjNjY2IiBmb250LXNpemU9IjE0Ij5ObyBDb3ZlcjwvdGV4dD48L3N2Zz4=';
            });
        });
    }

    // ── Init ─────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        initSourceTabs();
        initMangaSearch();
        initReader();
        initImageErrors();
        applyNsfwFilter();
    });

    // Expose NSFW toggle for settings page
    window.MangaSettings = {
        isNsfwHidden: isNsfwHidden,
        toggleNsfw: function (hide) {
            localStorage.setItem(NSFW_KEY, hide ? 'true' : 'false');
            applyNsfwFilter();
        }
    };
})();
