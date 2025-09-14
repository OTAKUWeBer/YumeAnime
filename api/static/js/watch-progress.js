// Watch progress management system
class WatchProgressManager {
  constructor() {
    this.watchData = this.loadWatchData()
    this.currentAnimeId = this.extractAnimeId()
    this.currentEpisodeId = this.extractEpisodeId()
    this.currentEpisodeNumber = this.extractEpisodeNumber()
    this.updateInterval = null
    this.video = null
    this.lastSavedTime = 0
    this.videoStarted = false
    this.resumeTime = 0
    this.autoSaveInterval = null
    this.settings = this.loadSettings()

    this.initializeProgress()
  }

  loadSettings() {
    try {
      const saved = localStorage.getItem('yumeAnimeSettings');
      return saved ? JSON.parse(saved) : {
        autoplayNext: true,
        skipIntro: true,
        rememberPosition: true,
        defaultVolume: 80
      };
    } catch (error) {
      return {
        autoplayNext: true,
        skipIntro: true,
        rememberPosition: true,
        defaultVolume: 80
      };
    }
  }
  loadWatchData() {
    try {
      const data = localStorage.getItem("animeWatchData")
      return data ? JSON.parse(data) : {}
    } catch (error) {
      console.error("Error loading watch data:", error)
      return {}
    }
  }

  saveWatchData() {
    try {
      localStorage.setItem("animeWatchData", JSON.stringify(this.watchData))
    } catch (error) {
      console.error("Error saving watch data:", error)
    }
  }

  extractAnimeId() {
    const path = window.location.pathname
    const match = path.match(/\/watch\/([^?]+)/)
    return match ? match[1] : null
  }

  extractEpisodeId() {
    const urlParams = new URLSearchParams(window.location.search)
    const ep = urlParams.get("ep")
    if (!ep) return null

    // Remove -sub or -dub suffix to get the base episode ID
    return ep.replace(/-(sub|dub)$/, "")
  }

  extractEpisodeNumber() {
    const urlParams = new URLSearchParams(window.location.search)
    const ep = urlParams.get("ep")
    if (!ep) return null

    // Try to extract episode number from the URL parameter
    // This might need adjustment based on your URL structure
    const episodeElement = document.querySelector("p.text-lg.md\\:text-xl.text-gray-300")
    if (episodeElement) {
      const match = episodeElement.textContent.match(/Episode (\d+)/)
      return match ? Number.parseInt(match[1]) : null
    }
    return null
  }

  getEpisodeKey(animeId, episodeId) {
    const urlParams = new URLSearchParams(window.location.search)
    const ep = urlParams.get("ep")
    const langType = ep && ep.includes("-") ? ep.split("-").pop() : "default"
    return `${animeId}_${episodeId}_${langType}`
  }

  getCurrentProgress() {
    const key = this.getEpisodeKey(this.currentAnimeId, this.currentEpisodeId)
    return this.watchData[key] || { watchTime: 0, totalTime: 0, completed: false }
  }

  saveProgress(watchTime, totalTime = null, completed = false) {
    if (!this.currentAnimeId || !this.currentEpisodeId) return

    const key = this.getEpisodeKey(this.currentAnimeId, this.currentEpisodeId)
    const current = this.watchData[key] || {}

    this.watchData[key] = {
      ...current,
      watchTime: Math.floor(watchTime),
      totalTime: totalTime || current.totalTime || 0,
      completed: completed,
      lastWatched: Date.now(),
      episodeNumber: this.currentEpisodeNumber,
    }

    this.lastSavedTime = watchTime
    this.saveWatchData()
    this.updateUI()
  }

  initializeProgress() {
    this.updateAllEpisodesProgress()
    const currentProgress = this.getCurrentProgress()

    // Show current episode progress in banner
    if (currentProgress.watchTime > 0) {
      this.updateCurrentProgressDisplay(currentProgress)
    }
  }

  updateAllEpisodesProgress() {
    const episodeCards = document.querySelectorAll(".episode-card")
    episodeCards.forEach((card) => {
      const episodeNumber = card.getAttribute("data-episode")
      const animeId = card.getAttribute("data-anime-id")
      const epId = card.getAttribute("data-ep-id")

      if (animeId && epId) {
        const key = this.getEpisodeKey(animeId, epId)
        const progress = this.watchData[key]

        if (progress) {
          this.updateEpisodeCard(episodeNumber, progress)
        }
      }
    })
  }

  updateEpisodeCard(episodeNumber, progress) {
    const progressBar = document.getElementById(`progress-${episodeNumber}`)
    const timeDisplay = document.getElementById(`time-${episodeNumber}`)
    const numberElement = document.getElementById(`number-${episodeNumber}`)

    if (progress.watchTime > 0 && progress.totalTime > 0) {
      const percentage = Math.min((progress.watchTime / progress.totalTime) * 100, 100)

      if (progressBar) {
        progressBar.style.width = `${percentage}%`
      }

      if (timeDisplay) {
        const watchTimeFormatted = this.formatTime(progress.watchTime)
        const totalTimeFormatted = this.formatTime(progress.totalTime)
        timeDisplay.textContent = `${watchTimeFormatted}/${totalTimeFormatted}`
        timeDisplay.style.display = "block"
      }

      // Add watched indicator for completed episodes
      if (progress.completed || percentage >= 90) {
        if (numberElement && !numberElement.querySelector(".episode-watched-indicator")) {
          const indicator = document.createElement("div")
          indicator.className = "episode-watched-indicator"
          numberElement.appendChild(indicator)
        }
      }
    }
  }

  updateCurrentProgressDisplay(progress) {
    const currentProgressElement = document.getElementById("currentProgress")
    if (currentProgressElement && progress.watchTime > 0) {
      const watchTimeFormatted = this.formatTime(Math.floor(progress.watchTime))
      const totalTimeFormatted = progress.totalTime
        ? `/${this.formatTime(Math.floor(progress.totalTime))}`
        : ""
      currentProgressElement.textContent = `${watchTimeFormatted}${totalTimeFormatted}`
    }
  }

  updateUI() {
    const currentProgress = this.getCurrentProgress()
    this.updateCurrentProgressDisplay(currentProgress)
    this.updateEpisodeCard(this.currentEpisodeNumber, currentProgress)
  }

  formatTime(seconds) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
    } else {
      return `${minutes}:${secs.toString().padStart(2, "0")}`
    }
  }

  showResumeNotification(watchTime) {
    const container = document.getElementById("videoContainer")
    const notification = document.createElement("div")
    notification.className = "resume-notification"
    notification.innerHTML = `
            <div class="flex items-center gap-3">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h1.01M15 10h1.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <span>Resume from ${this.formatTime(watchTime)}?</span>
                <button class="resume-button" onclick="progressManager.resumeVideo()">Resume</button>
                <button class="resume-button" onclick="progressManager.startFromBeginning()">Start Over</button>
                <button class="resume-button" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `

    container.appendChild(notification)
    this.resumeTime = watchTime

    // Auto-hide after 10 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove()
      }
    }, 10000)
  }

  resumeVideo() {
    const notification = document.querySelector(".resume-notification")
    if (notification) notification.remove()

    if (this.video) {
      this.video.currentTime = this.resumeTime
    }
  }

  startFromBeginning() {
    const notification = document.querySelector(".resume-notification")
    if (notification) notification.remove()
    this.resumeTime = 0
  }

  startTracking(video) {
    this.video = video
    this.videoStarted = true

    // Check if we should show resume notification or auto-resume
    const currentProgress = this.getCurrentProgress()
    if (this.settings.rememberPosition && currentProgress.watchTime > 30) {
      setTimeout(() => {
        if (this.video && this.video.readyState >= 2) {
          this.video.currentTime = currentProgress.watchTime
          console.log(`[v0] Auto-resumed from ${this.formatTime(currentProgress.watchTime)}`)
        }
      }, 1000) // Wait 1 second for video to be ready
    }

    // Start progress tracking
    this.startProgressTracking()
  }

  startProgressTracking() {
    if (!this.video) return

    this.autoSaveInterval = setInterval(() => {
      if (this.video && !this.video.paused && this.video.currentTime > 0) {
        const currentTime = this.video.currentTime
        const duration = this.video.duration

        if (duration > 0) {
          this.saveProgress(currentTime, duration, currentTime / duration >= 0.9)
        }
      }
    }, 500) // Save every 0.5 seconds

    // Add event listeners
    this.video.addEventListener("timeupdate", () => {
      const currentTime = this.video.currentTime
      const duration = this.video.duration

      if (currentTime > 0 && duration > 0) {
        // Only update UI, actual saving is handled by interval
        this.updateUI()
      }
    })

    this.video.addEventListener("ended", () => {
      this.saveProgress(this.video.currentTime, this.video.duration, true)
      this.handleVideoEnd()
    })

    this.video.addEventListener("pause", () => {
      if (this.video.currentTime > 0 && this.video.duration > 0) {
        this.saveProgress(
          this.video.currentTime,
          this.video.duration,
          this.video.currentTime / this.video.duration >= 0.9,
        )
      }
    })

    // Save progress when page is about to unload
    window.addEventListener("beforeunload", () => {
      if (this.video && this.video.currentTime > 0 && this.video.duration > 0) {
        this.saveProgress(
          this.video.currentTime,
          this.video.duration,
          this.video.currentTime / this.video.duration >= 0.9,
        )
      }
    })
  }

  handleVideoEnd() {
    // Auto-next logic is now handled by HLSVideoPlayer
    console.log("Video ended - progress saved")
  }

  stopTracking() {
    this.videoStarted = false
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval)
      this.autoSaveInterval = null
    }
  }
}

window.WatchProgressManager = WatchProgressManager
