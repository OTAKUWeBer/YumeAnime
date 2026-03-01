// Watchlist statistics calculation and display
class WatchlistStats {
  constructor() {
    this.stats = {
      total: 0,
      watching: 0,
      completed: 0,
      paused: 0,
      dropped: 0,
      planToWatch: 0,
      totalEpisodes: 0,
    }
  }

  calculateStats(watchlistData) {
    this.stats = {
      total: watchlistData.length,
      watching: 0,
      completed: 0,
      paused: 0,
      dropped: 0,
      planToWatch: 0,
      totalEpisodes: 0,
    }

    watchlistData.forEach((item) => {
      switch (item.status) {
        case "watching":
          this.stats.watching++
          break
        case "completed":
          this.stats.completed++
          break
        case "paused":
          this.stats.paused++
          break
        case "dropped":
          this.stats.dropped++
          break
        case "plan_to_watch":
          this.stats.planToWatch++
          break
      }

      if (item.episodes_watched) {
        this.stats.totalEpisodes += Number.parseInt(item.episodes_watched) || 0
      }
    })

    this.updateStatsDisplay()
  }

  updateStatsDisplay() {
    const elements = {
      "total-count": this.stats.total,
      "watching-count": this.stats.watching,
      "completed-count": this.stats.completed,
      "watched-episodes": this.stats.totalEpisodes,
    }

    Object.entries(elements).forEach(([id, value]) => {
      const element = document.getElementById(id)
      if (element) {
        this.animateNumber(element, value)
      }
    })

    // Show stats if there are items
    const statsContainer = document.getElementById("watchlist-stats")
    if (statsContainer && this.stats.total > 0) {
      statsContainer.classList.remove("hidden")
    }
  }

  animateNumber(element, targetValue) {
    const startValue = Number.parseInt(element.textContent) || 0
    const duration = 500
    const startTime = performance.now()

    const animate = (currentTime) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)

      const currentValue = Math.floor(startValue + (targetValue - startValue) * progress)
      element.textContent = currentValue

      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }

    requestAnimationFrame(animate)
  }

  getStats() {
    return this.stats
  }
}
