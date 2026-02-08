/**
 * Search Functionality Manager
 * Handles all search-related operations including suggestions, error handling, and user interactions
 * Supports desktop, mobile, and dropdown search interfaces
 */

class SearchManager {
    constructor() {
        // Initialize elements
        this.initializeElements();

        // Initialize variables
        this.debounceTimeouts = {
            desktop: null,
            mobile: null,
            dropdown: null
        };

        this.abortControllers = {
            desktop: null,
            mobile: null,
            dropdown: null
        };

        // Cache for suggestions to improve performance
        this.suggestionCache = new Map();

        // Click outside handler state
        this.isClickOutsideEnabled = true;

        // Initialize all event listeners
        this.initializeEventListeners();
    }

    /**
     * Initialize DOM elements for all search interfaces
     */
    initializeElements() {
        // Desktop search elements
        this.elements = {
            desktop: {
                form: document.getElementById('search-form'),
                input: document.getElementById('search-input'),
                error: document.getElementById('search-error'),
                loading: document.getElementById('search-loading'),
                suggestionBox: document.getElementById('suggestion-box'),
                suggestionsContent: document.getElementById('suggestions-content')
            },
            mobile: {
                overlay: document.getElementById('mobile-search-overlay'),
                toggle: document.getElementById('mobile-search-toggle'),
                closeBtn: document.getElementById('mobile-search-close'),
                form: document.getElementById('mobile-search-form'),
                input: document.getElementById('mobile-search-input'),
                error: document.getElementById('mobile-search-error'),
                loading: document.getElementById('mobile-search-loading'),
                suggestionBox: document.getElementById('mobile-suggestion-box'),
                suggestionsContent: document.getElementById('mobile-suggestions-content')
            },
            dropdown: {
                toggle: document.getElementById('search-dropdown-toggle'),
                container: document.getElementById('search-dropdown'),
                form: document.getElementById('dropdown-search-form'),
                input: document.getElementById('dropdown-search-input'),
                error: document.getElementById('dropdown-search-error'),
                loading: document.getElementById('dropdown-search-loading'),
                suggestionBox: document.getElementById('dropdown-suggestion-box'),
                suggestionsContent: document.getElementById('dropdown-suggestions-content')
            }
        };
    }

    /**
     * Initialize all event listeners
     */
    initializeEventListeners() {
        this.initializeFormHandlers();
        this.initializeInputHandlers();
        this.initializeSuggestionHandlers();
        this.initializeMobileHandlers();
        this.initializeDropdownHandlers();
        this.initializeKeyboardHandlers();
        this.initializeClickOutsideHandlers();
    }

    /**
     * Initialize form submission handlers
     */
    initializeFormHandlers() {
        // Desktop form handler
        this.elements.desktop.form?.addEventListener('submit', (e) => {
            const value = this.elements.desktop.input.value.trim();
            if (!value) {
                e.preventDefault();
                this.showSearchError('Please enter a search query.', 'desktop');
                return false;
            }
            this.elements.desktop.suggestionBox.classList.add('hidden');
        });

        // Mobile form handler
        this.elements.mobile.form?.addEventListener('submit', (e) => {
            const value = this.elements.mobile.input.value.trim();
            if (!value) {
                e.preventDefault();
                this.showSearchError('Please enter a search query.', 'mobile');
                return false;
            }
            this.elements.mobile.suggestionBox?.classList.add('hidden');
        });

        // Dropdown form handler
        this.elements.dropdown.form?.addEventListener('submit', (e) => {
            const value = this.elements.dropdown.input.value.trim();
            if (!value) {
                e.preventDefault();
                this.showSearchError('Please enter a search query.', 'dropdown');
                return false;
            }
            this.elements.dropdown.suggestionBox?.classList.add('hidden');
            this.elements.dropdown.container?.classList.add('hidden');
        });
    }

    /**
     * Initialize input change handlers
     */
    initializeInputHandlers() {
        // Desktop input handler
        this.elements.desktop.input?.addEventListener('input', () => {
            if (this.elements.desktop.input.value.trim()) {
                this.clearSearchError('desktop');
            }
            this.handleInputChange('desktop');
        });

        // Mobile input handler
        this.elements.mobile.input?.addEventListener('input', () => {
            if (this.elements.mobile.input.value.trim()) {
                this.clearSearchError('mobile');
            }
            this.handleInputChange('mobile');
        });

        // Dropdown input handler
        this.elements.dropdown.input?.addEventListener('input', () => {
            if (this.elements.dropdown.input.value.trim()) {
                this.clearSearchError('dropdown');
            }
            this.handleInputChange('dropdown');
        });
    }

    /**
     * Handle input change with debouncing and suggestion fetching
     * @param {string} searchType - Type of search interface (desktop, mobile, dropdown)
     */
    handleInputChange(searchType) {
        const input = this.elements[searchType].input;
        const query = input.value.trim();

        // Abort previous request
        if (this.abortControllers[searchType]) {
            this.abortControllers[searchType].abort();
        }

        // Clear previous timeout
        clearTimeout(this.debounceTimeouts[searchType]);
        this.hideLoading(searchType);

        if (!query) {
            this.elements[searchType].suggestionBox?.classList.add('hidden');
            if (this.elements[searchType].suggestionsContent) {
                this.elements[searchType].suggestionsContent.innerHTML = '';
            }
            return;
        }

        // Debounce the API call
        this.debounceTimeouts[searchType] = setTimeout(() => {
            this.fetchSuggestions(query, searchType);
        }, 200);
    }

    /**
     * Initialize suggestion click handlers
     */
    initializeSuggestionHandlers() {
        // Desktop suggestions
        this.elements.desktop.suggestionBox?.addEventListener('click', (e) => {
            this.handleSuggestionClick(e, 'desktop');
        });

        // Mobile suggestions
        this.elements.mobile.suggestionBox?.addEventListener('click', (e) => {
            this.handleSuggestionClick(e, 'mobile');
        });

        // Dropdown suggestions
        this.elements.dropdown.suggestionBox?.addEventListener('click', (e) => {
            this.handleSuggestionClick(e, 'dropdown');
        });
    }

    /**
     * Handle suggestion item clicks
     * @param {Event} e - Click event
     * @param {string} searchType - Type of search interface
     */
    handleSuggestionClick(e, searchType) {
        const target = e.target.closest('[data-id]');
        if (target) {
            const animeId = target.getAttribute('data-id');

            // Hide suggestions
            this.elements[searchType].suggestionBox?.classList.add('hidden');

            // Hide mobile overlay if mobile search
            if (searchType === 'mobile') {
                this.elements.mobile.overlay?.classList.add('hidden');
            }

            // Hide dropdown container if dropdown search
            if (searchType === 'dropdown') {
                this.elements.dropdown.container?.classList.add('hidden');
            }

            // Navigate to anime page
            window.location.href = `/anime/${animeId}`;
        }
    }

    /**
     * Initialize mobile-specific handlers
     */
    initializeMobileHandlers() {
        // Open mobile search overlay
        this.elements.mobile.toggle?.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent default button behavior
            this.openMobileSearch();
        });

        // Close mobile search overlay
        this.elements.mobile.closeBtn?.addEventListener('click', () => {
            this.elements.mobile.overlay?.classList.add('hidden');
        });

        // Close on overlay background click
        this.elements.mobile.overlay?.addEventListener('click', (e) => {
            if (e.target === this.elements.mobile.overlay) {
                this.elements.mobile.overlay.classList.add('hidden');
            }
        });
    }

    /**
     * Initialize dropdown-specific handlers
     */
    initializeDropdownHandlers() {
        // Toggle dropdown
        this.elements.dropdown.toggle?.addEventListener('click', () => {
            this.elements.dropdown.container?.classList.toggle('hidden');
            if (!this.elements.dropdown.container?.classList.contains('hidden')) {
                setTimeout(() => {
                    this.elements.dropdown.input?.focus();
                }, 100);
            }
        });

        // Close dropdown on outside click
        document.addEventListener('click', (e) => {
            if (!this.elements.dropdown.toggle?.contains(e.target) &&
                !this.elements.dropdown.container?.contains(e.target)) {
                this.elements.dropdown.container?.classList.add('hidden');
            }
        });
    }

    /**
     * Initialize keyboard handlers
     */
    initializeKeyboardHandlers() {
        // Global escape key handler
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.handleEscapeKey();
            }
        });

        // Desktop search input keyboard handler
        this.elements.desktop.input?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.elements.desktop.suggestionBox?.classList.add('hidden');
                this.elements.desktop.input.blur();
            } else if (e.key === 'Enter') {
                this.elements.desktop.suggestionBox?.classList.add('hidden');
            }
        });

        // Mobile search input keyboard handler
        this.elements.mobile.input?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.elements.mobile.suggestionBox?.classList.add('hidden');
                this.elements.mobile.overlay?.classList.add('hidden');
            } else if (e.key === 'Enter') {
                this.elements.mobile.suggestionBox?.classList.add('hidden');
            }
        });

        // Dropdown search input keyboard handler
        this.elements.dropdown.input?.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.elements.dropdown.suggestionBox?.classList.add('hidden');
                this.elements.dropdown.container?.classList.add('hidden');
            } else if (e.key === 'Enter') {
                this.elements.dropdown.suggestionBox?.classList.add('hidden');
            }
        });
    }

    /**
     * Handle escape key press
     */
    handleEscapeKey() {
        // Close mobile search overlay
        if (!this.elements.mobile.overlay?.classList.contains('hidden')) {
            this.elements.mobile.overlay.classList.add('hidden');
        }

        // Close dropdown
        if (!this.elements.dropdown.container?.classList.contains('hidden')) {
            this.elements.dropdown.container.classList.add('hidden');
        }
    }

    /**
     * Initialize click outside handlers
     */
    initializeClickOutsideHandlers() {
        // Click outside to close desktop suggestions
        document.addEventListener('click', (e) => {
            if (!this.isClickOutsideEnabled) return;

            const searchContainer = this.elements.desktop.form?.parentElement;
            if (searchContainer && !searchContainer.contains(e.target)) {
                this.elements.desktop.suggestionBox?.classList.add('hidden');
            }
        });

        // Disable click outside when hovering over suggestions
        this.elements.desktop.suggestionBox?.addEventListener('mouseenter', () => {
            this.isClickOutsideEnabled = false;
        });

        this.elements.desktop.suggestionBox?.addEventListener('mouseleave', () => {
            this.isClickOutsideEnabled = true;
        });
    }

    /**
     * Show search error message
     * @param {string} msg - Error message to display
     * @param {string} searchType - Type of search interface
     */
    showSearchError(msg, searchType = 'desktop') {
        const errorEl = this.elements[searchType].error;
        const inputEl = this.elements[searchType].input;

        if (!errorEl || !inputEl) return;

        const errorSpan = errorEl.querySelector('span');
        if (errorSpan) {
            errorSpan.textContent = msg;
        }

        errorEl.classList.remove('hidden');
        inputEl.classList.add('ring-2', 'ring-red-400/50', 'border-red-400/50', 'focus:ring-red-400/30');

        // Subtle shake animation
        inputEl.animate([
            { transform: 'translateX(0)' },
            { transform: 'translateX(-2px)' },
            { transform: 'translateX(2px)' },
            { transform: 'translateX(0)' }
        ], { duration: 200, iterations: 2 });

        setTimeout(() => inputEl.focus(), 100);
    }

    /**
     * Clear search error message
     * @param {string} searchType - Type of search interface
     */
    clearSearchError(searchType = 'desktop') {
        const errorEl = this.elements[searchType].error;
        const inputEl = this.elements[searchType].input;

        if (!errorEl || !inputEl) return;

        errorEl.classList.add('hidden');
        inputEl.classList.remove('ring-2', 'ring-red-400/50', 'border-red-400/50', 'focus:ring-red-400/30');
    }

    /**
     * Show loading indicator
     * @param {string} searchType - Type of search interface
     */
    showLoading(searchType = 'desktop') {
        const loadingEl = this.elements[searchType].loading;
        if (loadingEl) {
            loadingEl.classList.remove('hidden');
        }
    }

    /**
     * Hide loading indicator
     * @param {string} searchType - Type of search interface
     */
    hideLoading(searchType = 'desktop') {
        const loadingEl = this.elements[searchType].loading;
        if (loadingEl) {
            loadingEl.classList.add('hidden');
        }
    }

    /**
     * Fetch search suggestions from API
     * @param {string} query - Search query
     * @param {string} searchType - Type of search interface
     */
    async fetchSuggestions(query, searchType = 'desktop') {
        // Check cache first
        if (this.suggestionCache.has(query)) {
            this.displaySuggestions(this.suggestionCache.get(query), searchType);
            return;
        }

        this.showLoading(searchType);

        try {
            // Create new abort controller
            const controller = new AbortController();
            this.abortControllers[searchType] = controller;

            const response = await fetch(`/search/suggestions?q=${encodeURIComponent(query)}`, {
                signal: controller.signal
            });

            this.hideLoading(searchType);

            if (!response.ok) {
                console.error('Search suggestions API error:', response.status);
                return;
            }

            const json = await response.json();
            const suggestions = json.suggestions || json.animes || json.data || [];

            // Cache the results
            this.suggestionCache.set(query, suggestions);

            // Limit cache size
            if (this.suggestionCache.size > 50) {
                const firstKey = this.suggestionCache.keys().next().value;
                this.suggestionCache.delete(firstKey);
            }

            this.displaySuggestions(suggestions, searchType);
        } catch (error) {
            this.hideLoading(searchType);
            if (error.name !== 'AbortError') {
                console.error('Error fetching suggestions:', error);
            }
        }
    }

    /**
     * Display suggestions in the UI
     * @param {Array} suggestions - Array of suggestion objects
     * @param {string} searchType - Type of search interface
     */
    displaySuggestions(suggestions, searchType = 'desktop') {
        const suggestionBoxEl = this.elements[searchType].suggestionBox;
        const suggestionsContentEl = this.elements[searchType].suggestionsContent;

        if (!suggestionBoxEl || !suggestionsContentEl) return;

        if (!suggestions.length) {
            suggestionBoxEl.classList.add('hidden');
            suggestionsContentEl.innerHTML = '';
            return;
        }

        const isMobile = searchType === 'mobile';
        const suggestionHTML = suggestions
            .slice(0, 8)
            .map(s => `
                <div class="suggestion-item group" data-id="${s.id}" data-name="${s.name}">
                    <img src="${s.poster || '/static/images/placeholder.jpg'}" 
                         alt="${s.name}" 
                         class="suggestion-poster" 
                         onerror="this.src='/static/images/placeholder.jpg'" 
                         loading="lazy" />
                    <div class="suggestion-info">
                        <h4 class="suggestion-title group-hover:text-blue-300 transition-colors duration-200">${s.name || s.title || 'Unknown'}</h4>
                        ${(s.jname || s.japanese_title) ? `<p class="text-xs text-gray-400 truncate font-medium">${s.jname || s.japanese_title}</p>` : ''}
                        ${(s.moreInfo && s.moreInfo.length) ? `
                            <div class="suggestion-meta">
                                ${s.moreInfo.slice(0, 2).map((info, idx) => `<span>${info}${idx < Math.min(s.moreInfo.length - 1, 1) ? ' • ' : ''}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `)
            .join('');

        suggestionsContentEl.innerHTML = suggestionHTML;
        suggestionBoxEl.classList.remove('hidden');
    }

    /**
     * Public method to open mobile search overlay
     */
    openMobileSearch() {
        this.elements.mobile.overlay?.classList.remove('hidden');
        // Use requestAnimationFrame for better reliability on mobile devices
        requestAnimationFrame(() => {
            setTimeout(() => {
                this.elements.mobile.input?.focus();
            }, 100);
        });
    }

    /**
     * Public method to get search manager instance
     */
    static getInstance() {
        if (!SearchManager.instance) {
            SearchManager.instance = new SearchManager();
        }
        return SearchManager.instance;
    }
}

// Initialize search manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    // Create global search manager instance
    window.searchManager = SearchManager.getInstance();
});

// Export for module usage if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SearchManager;
}
