// UI state management for watchlist
class WatchlistUI {
  constructor() {
    this.currentPage = 1
    this.itemsPerPage = 24
    this.isLoading = false
  }

  showLoading() {
    this.toggleElement("loading", true)
    this.toggleElement("watchlist-grid", false)
    this.toggleElement("empty-state", false)
    this.toggleElement("login-required", false)
  }

  showWatchlist(items) {
    this.toggleElement("loading", false)
    this.toggleElement("watchlist-grid", true)
    this.toggleElement("empty-state", false)
    this.toggleElement("login-required", false)

    this.renderWatchlistItems(items)
  }

  showEmptyState() {
    this.toggleElement("loading", false)
    this.toggleElement("watchlist-grid", false)
    this.toggleElement("empty-state", true)
    this.toggleElement("login-required", false)
  }

  showLoginRequired() {
    this.toggleElement("loading", false)
    this.toggleElement("watchlist-grid", false)
    this.toggleElement("empty-state", false)
    this.toggleElement("login-required", true)
  }

  toggleElement(id, show) {
    const element = document.getElementById(id)
    if (element) {
      element.classList.toggle("hidden", !show)
    }
  }

  renderWatchlistItems(items) {
    const grid = document.getElementById("watchlist-grid")
    if (!grid) return

    grid.innerHTML = ""

    items.forEach((item) => {
      const itemElement = this.createWatchlistItem(item)
      grid.appendChild(itemElement)
    })

    this.updatePaginationInfo(items.length)
  }

  createWatchlistItem(item) {
    const div = document.createElement("div")
    div.className = "watchlist-item bg-gray-800 rounded-lg overflow-hidden hover:bg-gray-700 transition-colors"
    div.setAttribute("data-status", item.status)

    div.innerHTML = `
            <div class="aspect-[3/4] relative">
                <img src="${item.image_url || "/static/images/placeholder.jpg"}" 
                     alt="${item.title}" 
                     class="w-full h-full object-cover"
                     loading="lazy">
                <div class="absolute top-2 right-2">
                    <span class="status-badge px-2 py-1 text-xs rounded-full ${this.getStatusBadgeClass(item.status)}">
                        ${this.formatStatus(item.status)}
                    </span>
                </div>
            </div>
            <div class="p-3">
                <h3 class="font-semibold text-sm mb-1 line-clamp-2">${item.title}</h3>
                <div class="text-xs text-gray-400 mb-2">
                    ${item.episodes_watched || 0}/${item.total_episodes || "?"} episodes
                </div>
                <div class="flex gap-1">
                    <button onclick="updateWatchlistStatus('${item.id}', 'watching')" 
                            class="flex-1 px-2 py-1 text-xs bg-purple-600 hover:bg-purple-700 rounded transition-colors">
                        Watching
                    </button>
                    <button onclick="updateWatchlistStatus('${item.id}', 'completed')" 
                            class="flex-1 px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 rounded transition-colors">
                        Completed
                    </button>
                </div>
            </div>
        `

    return div
  }

  getStatusBadgeClass(status) {
    const classes = {
      watching: "bg-purple-600 text-white",
      completed: "bg-blue-600 text-white",
      paused: "bg-yellow-600 text-white",
      dropped: "bg-red-600 text-white",
      plan_to_watch: "bg-purple-600 text-white",
    }
    return classes[status] || "bg-gray-600 text-white"
  }

  formatStatus(status) {
    const formats = {
      plan_to_watch: "Plan to Watch",
      watching: "Watching",
      completed: "Completed",
      paused: "Paused",
      dropped: "Dropped",
    }
    return formats[status] || status
  }

  updatePaginationInfo(itemsShown) {
    const shownElement = document.getElementById("items-shown")
    const totalElement = document.getElementById("total-items")
    const paginationInfo = document.getElementById("pagination-info")

    if (shownElement) shownElement.textContent = itemsShown
    if (totalElement && window.watchlistManager) {
      totalElement.textContent = window.watchlistManager.getTotalItems()
    }
    if (paginationInfo && itemsShown > 0) {
      paginationInfo.classList.remove("hidden")
    }
  }

  showLoadMoreButton(show = true) {
    const container = document.getElementById("load-more-container")
    if (container) {
      container.classList.toggle("hidden", !show)
    }
  }

  showLoadingMore(show = true) {
    const loadingMore = document.getElementById("loading-more")
    const loadMoreBtn = document.getElementById("load-more-btn")

    if (loadingMore) loadingMore.classList.toggle("hidden", !show)
    if (loadMoreBtn) loadMoreBtn.classList.toggle("hidden", show)
  }
}

// Global functions for backward compatibility
function loadMoreItems() {
  if (window.watchlistManager) {
    window.watchlistManager.loadMore()
  }
}

function updateWatchlistStatus(itemId, status) {
  if (window.watchlistManager) {
    window.watchlistManager.updateItemStatus(itemId, status)
  }
}
