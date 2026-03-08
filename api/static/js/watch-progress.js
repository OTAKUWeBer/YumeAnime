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
    this.bufferIndicator = null
    this.bufferTimeout = null

    console.log("[WatchProgress] Init:", {
      anime: this.currentAnimeId,
      epId: this.currentEpisodeId,
      epNum: this.currentEpisodeNumber
    });

    this.initializeProgress()
  }

  loadSettings() {
    try {
      const saved = localStorage.getItem("yumeAnimeSettings")
      return saved
        ? JSON.parse(saved)
        : {
          autoplayNext: true,
          skipIntro: true,
          rememberPosition: true,
          defaultVolume: 80,
          preferredLanguage: "sub",
        }
    } catch (error) {
      return {
        autoplayNext: true,
        skipIntro: true,
        rememberPosition: true,
        defaultVolume: 80,
        preferredLanguage: "sub",
      }
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
    // Priority: DOM attribute -> URL regex
    const watchLayout = document.querySelector('.watch-layout, .episode-sidebar');
    if (watchLayout && watchLayout.dataset.animeId) {
      return watchLayout.dataset.animeId;
    }
    const path = window.location.pathname
    // New format: /watch/<anime_id>/ep-<N>
    const newMatch = path.match(/\/watch\/([^\/]+)\/ep-/)
    if (newMatch) return newMatch[1]
    // Old format: /watch/<anime_slug>
    const match = path.match(/\/watch\/([^?\/]+)/)
    return match ? match[1] : null
  }

  extractEpisodeId() {
    // New format: /watch/<anime_id>/ep-<N> -> use episode number as ID
    const path = window.location.pathname
    const newMatch = path.match(/\/watch\/[^\/]+\/ep-(\d+)/)
    if (newMatch) return newMatch[1]

    // Fallback: old ?ep= format
    const urlParams = new URLSearchParams(window.location.search)
    const ep = urlParams.get("ep")
    if (!ep) return null
    return ep.replace(/-(sub|dub)$/, "")
  }

  extractEpisodeNumber() {
    // New format: /watch/<anime_id>/ep-<N>
    const path = window.location.pathname
    const newMatch = path.match(/\/watch\/[^\/]+\/ep-(\d+)/)
    if (newMatch) return parseInt(newMatch[1], 10)

    // Fallback: check URL param
    const urlParams = new URLSearchParams(window.location.search)
    const ep = urlParams.get("ep")
    if (ep) {
      const parts = ep.split('-');
      if (parts.length > 0 && !isNaN(parts[0])) {
        return parseFloat(parts[0]);
      }
    }

    // Check for active sidebar item
    const activeItem = document.querySelector('.episode-sidebar-item.current');
    if (activeItem && activeItem.dataset.number) {
      return parseFloat(activeItem.dataset.number);
    }

    return null
  }

  getEpisodeKey(animeId, episodeId) {
    // Use episode number as key — language is not in URL anymore
    const langType = (window._watchState && window._watchState.language) || 'sub'
    return `${animeId}_${episodeId}_${langType}`
  }

  getCurrentProgress() {
    const key = this.getEpisodeKey(this.currentAnimeId, this.currentEpisodeId)
    return this.watchData[key] || { watchTime: 0, totalTime: 0, completed: false }
  }

  saveProgress(watchTime, totalTime = null, completed = false) {
    if (!this.currentAnimeId || !this.currentEpisodeId) {
      console.warn("[WatchProgress] Cannot save - missing IDs");
      return;
    }

    const key = this.getEpisodeKey(this.currentAnimeId, this.currentEpisodeId)
    const current = this.watchData[key] || {}

    // Track total watch time (to handle local storage usage)
    const tTime = totalTime || current.totalTime || 0;

    this.watchData[key] = {
      ...current,
      watchTime: Math.floor(watchTime),
      totalTime: tTime,
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

    // Use server-provided progress if available and preferred over local
    let currentProgress = this.getCurrentProgress()

    if (window._watchState && window._watchState.serverProgress) {
      const epProgress = window._watchState.serverProgress[`ep_${this.currentEpisodeNumber}`];
      if (epProgress) {
        console.log("[WatchProgress] Found server-side progress", epProgress);
        // Use server progress if local is significantly older or doesn't exist
        if (!currentProgress.lastWatched || (Date.now() - currentProgress.lastWatched > 1000 * 60 * 60 * 24)) {
          currentProgress = {
            watchTime: epProgress.watch_time || 0,
            totalTime: epProgress.total_time || 0,
            completed: epProgress.is_completed || false,
          };

          // Inject back into local state to keep UI consistent
          const key = this.getEpisodeKey(this.currentAnimeId, this.currentEpisodeId)
          this.watchData[key] = { ...this.watchData[key] || {}, ...currentProgress, lastWatched: Date.now() };
          this.saveWatchData();
        }
      }
    }

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
        let progress = this.watchData[key]

        // Enhance UI locally based on server tracking if available
        if (window._watchState && window._watchState.serverProgress) {
          const serverP = window._watchState.serverProgress[`ep_${episodeNumber}`];
          if (serverP && serverP.is_completed) {
            progress = { ...progress || {}, watchTime: serverP.total_time || 1, totalTime: serverP.total_time || 1, completed: true };
          }
        }

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
      const totalTimeFormatted = progress.totalTime ? `/${this.formatTime(Math.floor(progress.totalTime))}` : ""
      currentProgressElement.textContent = `${watchTimeFormatted}${totalTimeFormatted}`
    }
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
    if (!container) return

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
      const resumeTime = this.resumeTime

      // Wait for video to be fully ready before seeking
      const attemptResume = () => {
        if (this.video.readyState >= 2) {
          this.video.currentTime = resumeTime
          console.log(`[WatchProgress] Resumed from ${this.formatTime(resumeTime)}`)
        } else {
          setTimeout(attemptResume, 100)
        }
      }

      attemptResume()

      if (this.video.paused) {
        const handlePlay = () => {
          setTimeout(() => {
            if (Math.abs(this.video.currentTime - resumeTime) > 2) {
              this.video.currentTime = resumeTime
            }
          }, 200)
          this.video.removeEventListener("play", handlePlay)
        }
        this.video.addEventListener("play", handlePlay)
      }
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
    console.log("[WatchProgress] Resume Check:", currentProgress);

    if (this.settings.rememberPosition && currentProgress.watchTime > 10) {
      console.log(`[WatchProgress] Attempting resume from ${currentProgress.watchTime}s`);

      if (this.isMobileDevice()) {
        this.showResumeNotification(currentProgress.watchTime)
      } else {
        const attemptAutoResume = () => {
          if (this.video && this.video.readyState >= 1) {
            this.video.currentTime = currentProgress.watchTime
            console.log(`[WatchProgress] Auto-resumed from ${this.formatTime(currentProgress.watchTime)}`)
          } else if (this.video) {
            setTimeout(attemptAutoResume, 200)
          }
        }
        attemptAutoResume()
      }
    }

    this.startProgressTracking()
  }

  isMobileDevice() {
    return (
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
      (navigator.maxTouchPoints && navigator.maxTouchPoints > 2 && /MacIntel/.test(navigator.platform))
    )
  }

  startProgressTracking() {
    if (!this.video) return

    this.autoSaveInterval = setInterval(() => {
      if (this.video && !this.video.paused && this.video.currentTime > 0) {
        const currentTime = this.video.currentTime
        const duration = this.video.duration

        if (duration > 0 && !isNaN(currentTime) && !isNaN(duration)) {
          this.saveProgress(currentTime, duration, currentTime / duration >= 0.9)
        }
      }
    }, 1000)

    this.video.addEventListener("waiting", () => {
      this.showBufferIndicator()
    })

    this.video.addEventListener("canplay", () => {
      this.hideBufferIndicator()
    })

    this.video.addEventListener("canplaythrough", () => {
      this.hideBufferIndicator()
    })

    this.video.addEventListener("playing", () => {
      this.hideBufferIndicator()
    })

    this.video.addEventListener("ended", () => {
      const isComplete = true;

      // Force an immediate API sync by clearing block
      this._apiSyncThrottled = false;
      this.saveProgress(this.video.currentTime, this.video.duration, isComplete);
      this.handleVideoEnd();
    })

    this.video.addEventListener("pause", () => {
      if (this.video.currentTime > 0 && this.video.duration > 0) {
        const isComplete = this.video.currentTime / this.video.duration >= 0.9;

        // Force an immediate API sync when deliberately pausing
        this._apiSyncThrottled = false;
        this.saveProgress(this.video.currentTime, this.video.duration, isComplete);

        if (isComplete) {
          this.syncWatchedEpisodesToWatchlist()
        }
      }
    })

    this.video.addEventListener("error", (event) => {
      const error = event.target.error
      if (error) {
        console.error(`[WatchProgress] Video error: ${error.code} - ${error.message}`)
      }
    })

    window.addEventListener("beforeunload", () => {
      if (this.video && this.video.currentTime > 0 && this.video.duration > 0) {
        const isCompleted = window._forceEpisodeComplete || (this.video.currentTime / this.video.duration >= 0.9);

        // Use sendBeacon for guaranteed delivery on page unload
        if (window._watchState && window._watchState.isLoggedIn) {
          if (isCompleted) {
            const updatePayload = JSON.stringify({
              anime_id: this.currentAnimeId,
              action: "episodes",
              watched_episodes: this.currentEpisodeNumber
            });
            navigator.sendBeacon("/api/watchlist/update", new Blob([updatePayload], { type: 'application/json' }));
          }
        }

        this.saveProgress(
          this.video.currentTime,
          this.video.duration,
          isCompleted,
        )
      }
    })
  }

  showBufferIndicator() {
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout)
    }

    if (!this.bufferIndicator) {
      this.bufferIndicator = document.createElement("div")
      this.bufferIndicator.className = "buffer-indicator"
      this.bufferIndicator.innerHTML = `<div class="buffer-spinner"></div>`
      const videoContainer = document.getElementById("videoContainer")
      if (videoContainer) {
        videoContainer.appendChild(this.bufferIndicator)
      }
    }

    this.bufferTimeout = setTimeout(() => {
      if (this.bufferIndicator) {
        this.bufferIndicator.classList.add("show")
      }
    }, 300)
  }

  hideBufferIndicator() {
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout)
      this.bufferTimeout = null
    }

    if (this.bufferIndicator) {
      this.bufferIndicator.classList.remove("show")
    }
  }

  handleVideoEnd() {
    this.syncWatchedEpisodesToWatchlist()
    console.log("Video ended - progress saved and watchlist updated")
  }

  syncWatchedEpisodesToWatchlist() {
    if (!this.currentAnimeId || !this.currentEpisodeNumber || !window._watchState?.isLoggedIn) {
      console.log("[WatchProgress] Cannot sync - missing anime, episode info, or safely ignored (not logged in)")
      return
    }

    // Since the API sync explicitly updates the watched episodes count on the server securely
    // via `/api/watchlist/progress` directly when it receives "is_completed=true",
    // counting from local storage arbitrarily is no longer actually required.
    // However, to keep backward compatibility and purely for updating 'status':
    console.log(`[WatchProgress] Auto-completing episode ${this.currentEpisodeNumber} directly.`);

    try {
      fetch("/api/watchlist/update", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          anime_id: this.currentAnimeId,
          action: "episodes",
          watched_episodes: this.currentEpisodeNumber, // Now just directly passing the episode number for max update
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          console.log(`[WatchProgress] Legacy Watchlist updated to episode: ${this.currentEpisodeNumber}`)
        })
        .catch((error) => {
          console.error("[WatchProgress] Error syncing to watchlist:", error)
        })
    } catch (error) {
      console.error("[WatchProgress] Error in syncWatchedEpisodesToWatchlist:", error)
    }
  }

  stopTracking() {
    this.videoStarted = false
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval)
      this.autoSaveInterval = null
    }
    this.hideBufferIndicator()
    if (this.bufferTimeout) {
      clearTimeout(this.bufferTimeout)
    }
  }
}

window.WatchProgressManager = WatchProgressManager
