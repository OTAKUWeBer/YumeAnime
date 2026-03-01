// Watchlist filtering functionality
class WatchlistFilters {
  constructor() {
    this.currentFilter = "all"
    this.initializeFilters()
  }

  initializeFilters() {
    // Set up filter button event listeners
    document.querySelectorAll(".filter-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const filter = e.target.textContent.toLowerCase().replace(" ", "_")
        this.setActiveFilter(filter)
      })
    })
  }

  setActiveFilter(filter) {
    this.currentFilter = filter

    // Update button states
    document.querySelectorAll(".filter-btn").forEach((btn) => {
      btn.classList.remove("bg-purple-600")
      btn.classList.add("bg-gray-700")
    })

    event.target.classList.remove("bg-gray-700")
    event.target.classList.add("bg-purple-600")

    // Trigger filter update
    if (window.watchlistManager) {
      window.watchlistManager.filterItems(filter)
    }
  }

  getCurrentFilter() {
    return this.currentFilter
  }
}

// Global filter function for backward compatibility
function filterWatchlist(status) {
  if (window.watchlistFilters) {
    window.watchlistFilters.setActiveFilter(status)
  }
}
