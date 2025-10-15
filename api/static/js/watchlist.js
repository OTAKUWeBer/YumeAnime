// Watchlist Management Functionality
class WatchlistManager {
  constructor() {
    this.watchlistData = []
    this.currentFilter = "all"
    this.currentPage = 1
    this.totalPages = 1
    this.totalItems = 0
    this.itemsPerPage = 20
    this.isLoading = false
    this.hasMorePages = false
    this.loadedAnimeIds = new Set()

    this.statusColors = {
      watching: "bg-purple-600",
      completed: "bg-green-600",
      paused: "bg-yellow-600",
      on_hold: "bg-yellow-600",
      dropped: "bg-red-600",
      plan_to_watch: "bg-blue-600",
    }

    this.statusDisplayNames = {
      watching: "Watching",
      completed: "Completed",
      paused: "Paused",
      on_hold: "Paused",
      dropped: "Dropped",
      plan_to_watch: "Plan to watch",
    }

    this.init()
  }

  init() {
    document.addEventListener("DOMContentLoaded", () => {
      this.loadWatchlist(true)
      this.setupInfiniteScroll()
      this.setupEventListeners()
    })
  }

  setupEventListeners() {
    // Close modal when clicking outside
    document.addEventListener("click", (event) => {
      if (event.target.classList.contains("fixed") && event.target.classList.contains("inset-0")) {
        this.closeStatusModal()
      }
    })
  }

  async loadWatchlist(reset = true) {
    if (this.isLoading) return

    if (reset) {
      this.currentPage = 1
      this.watchlistData = []
      this.loadedAnimeIds.clear()
      document.getElementById("watchlist-grid").innerHTML = ""
    }

    this.isLoading = true
    this.showLoadingState(reset)

    try {
      let statusParam = ""
      if (this.currentFilter !== "all") {
        statusParam = this.currentFilter
      }

      const params = new URLSearchParams({
        page: this.currentPage,
        limit: this.itemsPerPage,
      })

      if (statusParam) {
        params.append("status", statusParam)
      }

      const response = await fetch(`/api/watchlist/paginated?${params}`)

      if (response.status === 401) {
        this.showLoginRequired()
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()

      if (reset) {
        this.watchlistData = data.data || []
        this.loadedAnimeIds.clear()
        this.watchlistData.forEach((item) => this.loadedAnimeIds.add(item.anime_id))
        await this.loadWatchlistStats()
      } else {
        const newItems = data.data || []
        const uniqueNewItems = newItems.filter((item) => {
          return item.anime_id && !this.loadedAnimeIds.has(item.anime_id)
        })

        if (uniqueNewItems.length > 0) {
          uniqueNewItems.forEach((item) => this.loadedAnimeIds.add(item.anime_id))
          this.watchlistData.push(...uniqueNewItems)
        }
      }

      if (data.pagination) {
        this.totalPages = data.pagination.total_pages
        this.totalItems = data.pagination.total_count
        this.hasMorePages = data.pagination.has_next && this.currentPage < this.totalPages
        this.updatePaginationInfo()
      }

      this.hideLoadingState(reset)

      if (this.watchlistData.length === 0) {
        this.showEmptyState()
      } else {
        this.renderWatchlist(reset)
        this.updateLoadMoreButton()
      }
    } catch (error) {
      console.error("Error loading watchlist:", error)
      this.hideLoadingState(reset)
      if (reset) this.showEmptyState()
      if (!reset) {
        this.currentPage = Math.max(1, this.currentPage - 1)
      }
    } finally {
      this.isLoading = false
    }
  }

  async loadWatchlistStats() {
    try {
      const response = await fetch("/api/watchlist/stats")
      if (response.ok) {
        const stats = await response.json()
        this.updateStatsDisplay(stats)
      }
    } catch (error) {
      console.error("Error loading stats:", error)
    }
  }

  updateStatsDisplay(stats) {
    document.getElementById("total-count").textContent = stats.total_anime || 0
    document.getElementById("watching-count").textContent = stats.watching || 0
    document.getElementById("completed-count").textContent = stats.completed || 0
    document.getElementById("watched-episodes").textContent = stats.watched_episodes || 0
    document.getElementById("watchlist-stats").classList.remove("hidden")
  }

  async loadMoreItems() {
    if (!this.hasMorePages || this.isLoading) return

    const nextPage = this.currentPage + 1
    this.currentPage = nextPage
    await this.loadWatchlist(false)
  }

  renderWatchlist(reset = true) {
    const grid = document.getElementById("watchlist-grid")

    if (reset) {
      grid.innerHTML = ""
    }

    document.getElementById("empty-state").classList.add("hidden")
    grid.classList.remove("hidden")

    const itemsToRender = reset ? this.watchlistData : this.watchlistData.slice(-this.itemsPerPage)

    const itemsHtml = itemsToRender.map((item) => this.renderWatchlistItem(item)).join("")

    if (reset) {
      grid.innerHTML = itemsHtml
    } else {
      grid.insertAdjacentHTML("beforeend", itemsHtml)
    }
  }

  renderWatchlistItem(item) {
    const totalEpisodes = item.total_episodes || "?"
    const watchedEpisodes = item.watched_episodes || 0
    const progressPercentage = totalEpisodes !== "?" ? Math.round((watchedEpisodes / totalEpisodes) * 100) : 0

    return `
        <div class="anime-card bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-2xl transition-all duration-300" data-anime-id="${item.anime_id}" data-status="${item.status}">
            <div class="relative group">
                <a href="/anime/${item.anime_id}">
                    <div class="anime-poster aspect-[2/3] bg-gray-700 overflow-hidden">
                        ${
                          item.poster_url
                            ? `
                            <img src="${item.poster_url}" 
                                 alt="${item.anime_title}" 
                                 class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                            <div class="w-full h-full bg-gray-700 flex items-center justify-center text-4xl" style="display: none;">
                                📺
                            </div>
                        `
                            : `
                            <div class="w-full h-full bg-gray-700 flex items-center justify-center text-4xl">
                                📺
                            </div>
                        `
                        }
                    </div>
                </a>
                
                <div class="play-button"></div>
                
                ${
                  item.rating
                    ? `
                    <div class="absolute top-2 left-2 bg-yellow-500/90 backdrop-blur-sm text-gray-900 px-2 py-1 rounded-md text-xs font-bold flex items-center gap-1">
                        <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24">
                            <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
                        </svg>
                        ${item.rating}
                    </div>
                `
                    : ""
                }
                
                <div class="status-badge absolute top-2 right-2 ${this.statusColors[item.status]} backdrop-blur-sm text-white px-2.5 py-1 rounded-md text-xs font-semibold shadow-lg">
                    ${this.statusDisplayNames[item.status] || item.status.charAt(0).toUpperCase() + item.status.slice(1).replace("_", " ")}
                </div>
            </div>
            
            <div class="p-3">
                <div class="flex items-start justify-between gap-2 mb-3">
                    <a href="/anime/${item.anime_id}" class="hover:text-purple-400 transition-colors flex-1">
                        <h3 class="font-semibold line-clamp-2 text-sm leading-tight">${item.anime_title}</h3>
                    </a>
                    <button onclick="watchlistManager.openStatusModal('${item.anime_id}', '${item.anime_title.replace(/'/g, "\\'")}', '${item.status}', ${watchedEpisodes}, ${item.total_episodes}, '${item.poster_url || ""}')" 
                            class="flex-shrink-0 w-8 h-8 bg-gray-700 hover:bg-gray-600 rounded-lg transition-all hover:scale-105 flex items-center justify-center">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/>
                        </svg>
                    </button>
                </div>
                
                <div class="mb-2">
                    <div class="flex items-baseline justify-between mb-2">
                        <div class="flex items-baseline gap-1.5">
                            <span class="text-2xl font-bold text-purple-400">${watchedEpisodes}</span>
                            <span class="text-gray-500 text-sm">/</span>
                            <span class="text-lg font-semibold text-gray-400">${totalEpisodes}</span>
                        </div>
                        ${
                          totalEpisodes !== "?"
                            ? `<span class="text-xs font-medium text-gray-400">${progressPercentage}%</span>`
                            : ""
                        }
                    </div>
                    
                    <div class="progress-bar w-full bg-gray-700 rounded-full h-1.5 overflow-hidden">
                        <div class="bg-gradient-to-r from-purple-500 to-pink-500 h-full rounded-full transition-all duration-500 ease-out" 
                             style="width: ${progressPercentage}%">
                        </div>
                    </div>
                </div>
            </div>
        </div>
        `
  }

  filterWatchlist(status) {
    if (this.isLoading) return

    this.currentFilter = status
    this.currentPage = 1
    this.hasMorePages = false
    this.loadedAnimeIds.clear()

    // Update active filter button
    document.querySelectorAll(".filter-btn").forEach((btn) => {
      btn.classList.remove("active", "bg-purple-600")
      btn.classList.add("bg-gray-700")
    })
    event.target.classList.add("active", "bg-purple-600")
    event.target.classList.remove("bg-gray-700")

    this.loadWatchlist(true)
  }

  async quickUpdateEpisodes(animeId, newCount, totalEpisodes) {
    try {
      const response = await fetch("/api/watchlist/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anime_id: animeId,
          action: "episodes",
          watched_episodes: Math.min(newCount, totalEpisodes || 999),
          total_episodes: totalEpisodes,
        }),
      })

      if (response.ok) {
        const item = this.watchlistData.find((item) => item.anime_id === animeId)
        if (item) {
          item.watched_episodes = Math.min(newCount, totalEpisodes || 999)
          this.renderWatchlist(true)
        }
      } else {
        throw new Error("Update failed")
      }
    } catch (error) {
      console.error("Error updating episodes:", error)
      alert("Failed to update episode count")
    }
  }

  async removeFromWatchlist(animeId, animeTitle, buttonElement) {
    if (!confirm(`Remove "${animeTitle}" from your watchlist?`)) return

    buttonElement.disabled = true
    buttonElement.textContent = "Removing..."

    try {
      const response = await fetch("/api/watchlist/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ anime_id: animeId }),
      })

      if (response.ok) {
        this.watchlistData = this.watchlistData.filter((item) => item.anime_id !== animeId)
        this.loadedAnimeIds.delete(animeId)

        const element = document.querySelector(`[data-anime-id="${animeId}"]`)
        if (element) {
          element.remove()
        }

        this.totalItems = Math.max(0, this.totalItems - 1)
        this.updatePaginationInfo()

        if (this.watchlistData.length === 0) {
          this.showEmptyState()
        }

        await this.loadWatchlistStats()
      } else {
        throw new Error("Remove failed")
      }
    } catch (error) {
      console.error("Error removing from watchlist:", error)
      alert("Failed to remove from watchlist")
      buttonElement.disabled = false
      buttonElement.textContent = "Remove"
    }
  }

  openStatusModal(animeId, animeTitle, status, watchedEps, totalEps, posterUrl) {
    const modal = document.createElement("div")
    modal.id = "status-modal"
    modal.className =
      "fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in"
    modal.onclick = (e) => {
      if (e.target === modal) this.closeStatusModal()
    }

    const statusOptions = [
      { value: "watching", label: "Watching", color: "purple" },
      { value: "completed", label: "Completed", color: "green" },
      { value: "paused", label: "On Hold", color: "yellow" },
      { value: "dropped", label: "Dropped", color: "red" },
      { value: "plan_to_watch", label: "Plan to Watch", color: "blue" },
    ]

    modal.innerHTML = `
      <div class="bg-gray-900 rounded-xl max-w-md w-full shadow-2xl animate-scale-in overflow-hidden border border-gray-800">
        <div class="relative bg-gradient-to-br from-purple-600 to-pink-600 p-4">
          <button onclick="watchlistManager.closeStatusModal()" 
                  class="absolute top-3 right-3 w-8 h-8 bg-black/30 hover:bg-black/50 backdrop-blur-sm rounded-full flex items-center justify-center transition-all">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
          <h3 class="text-lg font-bold text-white pr-8 line-clamp-2">${animeTitle}</h3>
        </div>
        
        <div class="p-5 space-y-5">
          <div>
            <label class="block text-xs font-bold mb-2 text-gray-400 uppercase tracking-wide">Status</label>
            <div class="grid grid-cols-2 gap-2">
              ${statusOptions
                .map(
                  (opt) => `
                <button onclick="watchlistManager.selectStatus('${opt.value}')" 
                        data-status="${opt.value}"
                        class="status-option p-3 rounded-lg border-2 transition-all text-sm font-semibold ${
                          status === opt.value || (status === "on_hold" && opt.value === "paused")
                            ? `border-${opt.color}-500 bg-${opt.color}-500/20`
                            : "border-gray-700 bg-gray-800/50 hover:border-gray-600"
                        }">
                  ${opt.label}
                </button>
              `,
                )
                .join("")}
            </div>
          </div>
          
          <div>
            <label class="block text-xs font-bold mb-2 text-gray-400 uppercase tracking-wide">Episodes</label>
            <div class="flex items-center gap-3">
              <button onclick="watchlistManager.adjustEpisodes(-1)" 
                      class="w-10 h-10 bg-gray-800 hover:bg-purple-600 border border-gray-700 rounded-lg flex items-center justify-center transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M20 12H4"/>
                </svg>
              </button>
              <div class="flex-1 text-center">
                <input type="number" 
                       id="modal-episodes" 
                       min="0" 
                       max="${totalEps || 999}" 
                       value="${watchedEps || 0}"
                       inputmode="numeric"
                       pattern="[0-9]*"
                       oninput="this.value = this.value.replace(/[^0-9]/g, '')"
                       class="w-full text-center text-2xl font-bold p-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:border-purple-500 focus:ring-1 focus:ring-purple-500 focus:outline-none transition-all">
                <div class="text-xs text-gray-500 mt-1">of ${totalEps || "?"}</div>
              </div>
              <button onclick="watchlistManager.adjustEpisodes(1)" 
                      class="w-10 h-10 bg-gray-800 hover:bg-purple-600 border border-gray-700 rounded-lg flex items-center justify-center transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"/>
                </svg>
              </button>
            </div>
          </div>
          
          <div class="flex gap-2 pt-2">
            <button onclick="watchlistManager.saveStatusChanges('${animeId}')" 
                    class="flex-1 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 px-4 py-3 rounded-lg font-semibold transition-all">
              Save
            </button>
            <button onclick="watchlistManager.deleteFromModal('${animeId}', '${animeTitle.replace(/'/g, "\\'")}')" 
                    class="px-4 py-3 bg-red-600/90 hover:bg-red-600 rounded-lg font-semibold transition-all">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    `

    document.body.appendChild(modal)
    this.currentModalAnimeId = animeId
    this.currentModalStatus = status === "on_hold" ? "paused" : status
    this.currentModalTotalEps = totalEps
  }

  selectStatus(status) {
    this.currentModalStatus = status
    const colorMap = {
      watching: "purple",
      completed: "green",
      paused: "yellow",
      on_hold: "yellow",
      dropped: "red",
      plan_to_watch: "blue",
    }

    document.querySelectorAll(".status-option").forEach((btn) => {
      const btnStatus = btn.dataset.status
      const color = colorMap[btnStatus]
      btn.className =
        "status-option p-3 rounded-lg border-2 transition-all text-sm font-semibold " +
        (btnStatus === status
          ? `border-${color}-500 bg-${color}-500/20`
          : "border-gray-700 bg-gray-800/50 hover:border-gray-600")
    })
  }

  adjustEpisodes(delta) {
    const input = document.getElementById("modal-episodes")
    const current = Number.parseInt(input.value) || 0
    const max = Number.parseInt(input.max) || 999
    const newValue = Math.max(0, Math.min(max, current + delta))
    input.value = newValue
  }

  async saveStatusChanges(animeId) {
    const input = document.getElementById("modal-episodes")
    const newEpisodes = Number.parseInt(input.value) || 0
    const maxEpisodes = Number.parseInt(input.max) || 999
    const newStatus = this.currentModalStatus

    // Validate episode count doesn't exceed maximum
    if (newEpisodes > maxEpisodes) {
      alert(`Episode count cannot exceed ${maxEpisodes}`)
      input.value = maxEpisodes
      return
    }

    try {
      const [statusResponse, episodesResponse] = await Promise.all([
        fetch("/api/watchlist/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            anime_id: animeId,
            action: "status",
            status: newStatus,
          }),
        }),
        fetch("/api/watchlist/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            anime_id: animeId,
            action: "episodes",
            watched_episodes: newEpisodes,
          }),
        }),
      ])

      if (statusResponse.ok && episodesResponse.ok) {
        const item = this.watchlistData.find((item) => item.anime_id === animeId)
        if (item) {
          item.status = newStatus
          item.watched_episodes = newEpisodes
        }

        this.closeStatusModal()

        if (this.currentFilter !== "all" && this.currentFilter !== newStatus) {
          this.loadWatchlist(true)
        } else {
          this.renderWatchlist(true)
        }

        await this.loadWatchlistStats()
      } else {
        throw new Error("Update failed")
      }
    } catch (error) {
      console.error("Error updating watchlist:", error)
      alert("Failed to update watchlist")
    }
  }

  async deleteFromModal(animeId, animeTitle) {
    if (!confirm(`Remove "${animeTitle}" from your watchlist?`)) return

    try {
      const response = await fetch("/api/watchlist/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ anime_id: animeId }),
      })

      if (response.ok) {
        this.watchlistData = this.watchlistData.filter((item) => item.anime_id !== animeId)
        this.loadedAnimeIds.delete(animeId)

        this.closeStatusModal()

        const element = document.querySelector(`[data-anime-id="${animeId}"]`)
        if (element) {
          element.remove()
        }

        this.totalItems = Math.max(0, this.totalItems - 1)
        this.updatePaginationInfo()

        if (this.watchlistData.length === 0) {
          this.showEmptyState()
        }

        await this.loadWatchlistStats()
      } else {
        throw new Error("Remove failed")
      }
    } catch (error) {
      console.error("Error removing from watchlist:", error)
      alert("Failed to remove from watchlist")
    }
  }

  closeStatusModal() {
    const modal = document.getElementById("status-modal")
    if (modal) {
      modal.remove()
    }
  }

  setupInfiniteScroll() {
    let scrollTimeout = null

    window.addEventListener(
      "scroll",
      () => {
        if (scrollTimeout) {
          clearTimeout(scrollTimeout)
        }

        scrollTimeout = setTimeout(() => {
          if (this.isLoading || !this.hasMorePages) {
            return
          }

          const scrollTop = window.pageYOffset || document.documentElement.scrollTop
          const windowHeight = window.innerHeight
          const documentHeight = document.documentElement.offsetHeight

          if (scrollTop + windowHeight >= documentHeight - 1000) {
            this.loadMoreItems()
          }
        }, 300)
      },
      { passive: true },
    )
  }

  showLoadingState(initial = true) {
    if (initial) {
      document.getElementById("loading").classList.remove("hidden")
      document.getElementById("watchlist-grid").classList.add("hidden")
      document.getElementById("empty-state").classList.add("hidden")
      document.getElementById("login-required").classList.add("hidden")
    } else {
      document.getElementById("loading-more").classList.remove("hidden")
      document.getElementById("load-more-btn").disabled = true
    }
  }

  hideLoadingState(initial = true) {
    if (initial) {
      document.getElementById("loading").classList.add("hidden")
    } else {
      document.getElementById("loading-more").classList.add("hidden")
      document.getElementById("load-more-btn").disabled = false
    }
  }

  showEmptyState() {
    document.getElementById("empty-state").classList.remove("hidden")
    document.getElementById("watchlist-grid").classList.add("hidden")
    document.getElementById("load-more-container").classList.add("hidden")
    document.getElementById("pagination-info").classList.add("hidden")
    document.getElementById("loading").classList.add("hidden")
  }

  showLoginRequired() {
    document.getElementById("login-required").classList.remove("hidden")
    document.getElementById("watchlist-grid").classList.add("hidden")
    document.getElementById("load-more-container").classList.add("hidden")
    document.getElementById("pagination-info").classList.add("hidden")
    document.getElementById("loading").classList.add("hidden")
  }

  updateLoadMoreButton() {
    const container = document.getElementById("load-more-container")
    if (this.hasMorePages && this.watchlistData.length > 0) {
      container.classList.remove("hidden")
    } else {
      container.classList.add("hidden")
    }
  }

  updatePaginationInfo() {
    const info = document.getElementById("pagination-info")
    const itemsShown = document.getElementById("items-shown")
    const totalItemsSpan = document.getElementById("total-items")

    itemsShown.textContent = this.watchlistData.length
    totalItemsSpan.textContent = this.totalItems

    if (this.totalItems > 0) {
      info.classList.remove("hidden")
    }
  }
}

// Initialize watchlist manager and make it globally available
const watchlistManager = new WatchlistManager()

// Global functions for backward compatibility
function filterWatchlist(status) {
  watchlistManager.filterWatchlist(status)
}

function loadMoreItems() {
  watchlistManager.loadMoreItems()
}

function openLoginModal() {
  // This function should be implemented based on your login modal system
  console.log("Open login modal")
}
