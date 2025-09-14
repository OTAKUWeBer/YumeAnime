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
      completed: "bg-blue-600",
      paused: "bg-yellow-600",
      on_hold: "bg-yellow-600",
      dropped: "bg-red-600",
      plan_to_watch: "bg-orange-600",
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
        this.closeEditModal()
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
        <div class="anime-card bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow" data-anime-id="${item.anime_id}" data-status="${item.status}">
            <div class="relative">
                <a href="/anime/${item.anime_id}">
                    <div class="anime-poster aspect-[2/3] sm:aspect-[3/4] bg-gray-700 overflow-hidden">
                        ${
                          item.poster_url
                            ? `
                            <img src="${item.poster_url}" 
                                 alt="${item.anime_title}" 
                                 class="w-full h-full object-cover"
                                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                            <div class="w-full h-full bg-gray-700 flex items-center justify-center text-2xl sm:text-4xl" style="display: none;">
                                📺
                            </div>
                        `
                            : `
                            <div class="w-full h-full bg-gray-700 flex items-center justify-center text-2xl sm:text-4xl">
                                📺
                            </div>
                        `
                        }
                    </div>
                </a>
                
                <div class="play-button">
                </div>
                
                ${
                  item.rating
                    ? `
                    <div class="rating-badge absolute top-2 left-2 bg-red-600/90 text-white px-2 py-1 rounded text-xs font-bold">
                        ${item.rating}
                    </div>
                `
                    : ""
                }
                
                ${
                  item.episodes && (item.episodes.sub || item.episodes.dub)
                    ? `
                    <div class="absolute bottom-2 right-2 flex gap-1">
                        ${
                          item.episodes.sub
                            ? `
                            <div class="episode-badge bg-indigo-500/90 text-white px-2 py-1 rounded flex items-center gap-1 text-xs font-bold">
                                <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24">
                                    <path d="M18 11H6V9h12v2zm4-6v14c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V5c0-1.1.9-2 2-2h16c1.1 0 2 .9 2 2zm-2 0H4v14h16V5z"/>
                                    <path d="M7 15h2v-2H7v2zm4 0h2v-2h-2v2zm4 0h2v-2h-2v2z"/>
                                </svg>
                                ${item.episodes.sub}
                            </div>
                        `
                            : ""
                        }
                        ${
                          item.episodes.dub
                            ? `
                            <div class="episode-badge bg-emerald-500/90 text-white px-2 py-1 rounded flex items-center gap-1 text-xs font-bold">
                                <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24">
                                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                                </svg>
                                ${item.episodes.dub}
                            </div>
                        `
                            : ""
                        }
                    </div>
                `
                    : ""
                }
                
                <div class="status-badge absolute top-1 right-1 sm:top-2 sm:right-2 ${this.statusColors[item.status]} text-white px-1 py-0.5 sm:px-2 sm:py-1 rounded-full text-xs font-semibold">
                    ${this.statusDisplayNames[item.status] || item.status.charAt(0).toUpperCase() + item.status.slice(1).replace("_", " ")}
                </div>
            </div>
            
            <div class="p-2 sm:p-4">
                <a href="/anime/${item.anime_id}" class="hover:text-purple-400 transition-colors">
                    <h3 class="anime-title font-semibold mb-1 sm:mb-2 line-clamp-2 text-sm sm:text-base">${item.anime_title}</h3>
                </a>
                
                <div class="flex items-center justify-between text-xs sm:text-sm text-gray-400 mb-2 sm:mb-3">
                    <span>Progress:</span>
                    <span class="font-semibold">${watchedEpisodes}/${totalEpisodes}</span>
                </div>
                
                <div class="progress-bar w-full bg-gray-700 rounded-full h-2 sm:h-3 mb-2 sm:mb-3 overflow-hidden">
                    <div class="bg-gradient-to-r from-purple-500 to-purple-600 h-2 sm:h-2 rounded-full transition-all duration-500 ease-out relative" 
                         style="width: ${progressPercentage}%">
                        ${
                          progressPercentage > 0
                            ? `
                            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20 animate-pulse"></div>
                        `
                            : ""
                        }
                    </div>
                </div>
                
                ${
                  totalEpisodes !== "?"
                    ? `
                    <div class="text-xs text-center text-gray-400 mb-2 sm:mb-3">
                        ${progressPercentage}% Complete
                    </div>
                `
                    : ""
                }
                
                <div class="flex flex-col sm:flex-row gap-1 sm:gap-2 mb-2">
                    <button onclick="watchlistManager.quickUpdateEpisodes('${item.anime_id}', ${watchedEpisodes + 1}, ${item.total_episodes})" 
                            class="action-button bg-purple-600 hover:bg-purple-700 px-2 py-1 rounded text-xs font-semibold transition-colors"
                            ${watchedEpisodes >= (item.total_episodes || 999) ? "disabled" : ""}>
                        +1 Episode
                    </button>
                    <button onclick="watchlistManager.openEditModal('${item.anime_id}', '${item.anime_title.replace(/'/g, "\\'")}', '${item.status}', ${watchedEpisodes}, ${item.total_episodes})" 
                            class="action-button bg-gray-600 hover:bg-gray-500 px-2 py-1 rounded text-xs font-semibold transition-colors">
                        Edit
                    </button>
                </div>
                
                <div class="flex flex-col sm:flex-row gap-1 sm:gap-2">
                    <a href="/episodes/${item.anime_id}" class="action-button text-center bg-purple-600 hover:bg-purple-700 px-2 py-1 rounded text-xs font-semibold transition-colors">
                        Watch
                    </a>
                    <button onclick="watchlistManager.removeFromWatchlist('${item.anime_id}', '${item.anime_title.replace(/'/g, "\\'")}', this)" 
                            class="action-button bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs font-semibold transition-colors">
                        Remove
                    </button>
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

  openEditModal(animeId, animeTitle, status, watchedEps, totalEps) {
    const modal = document.createElement("div")
    modal.className = "fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
    modal.innerHTML = `
            <div class="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-xl font-bold mb-4">${animeTitle}</h3>
                
                <div class="mb-4">
                    <label class="block text-sm font-medium mb-2">Status:</label>
                    <select id="edit-status" class="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white">
                        <option value="watching" ${status === "watching" ? "selected" : ""}>Watching</option>
                        <option value="completed" ${status === "completed" ? "selected" : ""}>Completed</option>
                        <option value="paused" ${status === "paused" || status === "on_hold" ? "selected" : ""}>Paused</option>
                        <option value="dropped" ${status === "dropped" ? "selected" : ""}>Dropped</option>
                        <option value="plan_to_watch" ${status === "plan_to_watch" ? "selected" : ""}>Plan to watch</option>
                    </select>
                </div>
                
                <div class="mb-6">
                    <label class="block text-sm font-medium mb-2">Episodes Watched:</label>
                    <input type="number" id="edit-episodes" min="0" max="${totalEps || 999}" value="${watchedEps || 0}" 
                        class="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white">
                    <div class="text-xs text-gray-400 mt-1">Total: ${totalEps || "?"} episodes</div>
                </div>
                
                <div class="flex gap-3">
                    <button onclick="watchlistManager.saveEdit('${animeId}')" 
                        class="flex-1 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg font-semibold transition-colors">
                        Save Changes
                    </button>
                    <button onclick="watchlistManager.closeEditModal()" 
                        class="flex-1 bg-gray-600 hover:bg-gray-700 px-4 py-2 rounded-lg font-semibold transition-colors">
                        Cancel
                    </button>
                </div>
            </div>
        `

    document.body.appendChild(modal)
  }

  async saveEdit(animeId) {
    const newStatus = document.getElementById("edit-status").value
    const newEpisodes = Number.parseInt(document.getElementById("edit-episodes").value) || 0

    try {
      const statusResponse = await fetch("/api/watchlist/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anime_id: animeId,
          action: "status",
          status: newStatus,
        }),
      })

      const episodesResponse = await fetch("/api/watchlist/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          anime_id: animeId,
          action: "episodes",
          watched_episodes: newEpisodes,
        }),
      })

      if (statusResponse.ok && episodesResponse.ok) {
        const item = this.watchlistData.find((item) => item.anime_id === animeId)
        if (item) {
          item.status = newStatus
          item.watched_episodes = newEpisodes
        }

        this.closeEditModal()

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

  closeEditModal() {
    const modal = document.querySelector(".fixed.inset-0")
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
