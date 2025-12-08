// Video.js Player with all existing functionality preserved
import { PlayerConfig } from "./modules/player-config.js"
import { SubtitleHandler } from "./modules/subtitle-handler.js"
import { PlayerControls } from "./modules/player-controls.js"
import { SkipManager } from "./modules/skip-manager.js"

class VideoJSPlayer {
  constructor() {
    this.player = null
    this.skipManager = null
    this.controls = null
    this.subtitleHandler = null
    this.isFullscreen = false
    this.touchStartX = 0
    this.touchStartTime = 0
    this.isSeeking = false
    this.keyboardEnabled = true
    this.controlIndicatorTimeouts = new Map()
    this.settings = this.loadSettings()
    this.currentLanguage = "sub" // Track current language for subtitle visibility
    this.stalledCheckInterval = null // For stalled playback monitoring
  }

  loadSettings() {
    try {
      const saved = localStorage.getItem("yumeAnimeSettings")
      return saved ? JSON.parse(saved) : PlayerConfig.getDefaultSettings()
    } catch (error) {
      console.error("Error loading settings:", error)
      return PlayerConfig.getDefaultSettings()
    }
  }

  initialize() {
    console.log("=== Video.js Player Initialization ===")

    const videoElement = document.getElementById("videoPlayer")
    this.skipButtonsContainer = document.getElementById("skipButtons") // Kept for potential future use, but handled by SkipManager
    this.skipIntroBtn = document.getElementById("skipIntroBtn")
    this.skipOutroBtn = document.getElementById("skipOutroBtn")

    if (!videoElement) {
      console.error("ERROR: Video element not found!")
      return false
    }

    // Get data from video element
    const videoUrl = videoElement.dataset.videoUrl
    console.log("Video URL:", videoUrl)

    if (!videoUrl || videoUrl === "null" || videoUrl === "") {
      console.error("ERROR: No valid video URL provided!")
      this.showError("Video not available. Please try refreshing the page.")
      return false
    }

    // Parse other data
    try {
      const subtitles = JSON.parse(videoElement.dataset.subtitles || "[]")
      const introData = JSON.parse(videoElement.dataset.intro || "{}")
      const outroData = JSON.parse(videoElement.dataset.outro || "{}")

      this.intro = introData.start ? introData : null
      this.outro = outroData.start ? outroData : null

      console.log("Subtitles:", subtitles.length, "tracks")
      console.log("Intro:", this.intro)
      console.log("Outro:", this.outro)

      this.subtitleHandler = new SubtitleHandler(this.settings)
      const intro = introData.start ? introData : null
      const outro = outroData.start ? outroData : null

      // Initialize Video.js player
      this.setupVideoJS(videoElement, videoUrl, subtitles, intro, outro, this.skipIntroBtn, this.skipOutroBtn)

      window.addEventListener("settingsChanged", (event) => {
        if (event.detail && event.detail.settings) {
          this.updateSettings(event.detail.settings)
        }
      })

      return true
    } catch (error) {
      console.error("Error parsing video data:", error)
      this.showError("Error loading video data")
      return false
    }
  }

  setupVideoJS(videoElement, videoUrl, subtitles, intro, outro, skipIntroBtn, skipOutroBtn) {
    console.log("=== Setting up Video.js ===")

    const playerOptions = PlayerConfig.getDefaultConfig()
    playerOptions.volume = this.settings.defaultVolume / 100
    playerOptions.sources = [{ src: videoUrl, type: "application/x-mpegURL" }]
    playerOptions.tracks = this.subtitleHandler.formatSubtitlesForVideoJS(subtitles)

    // Initialize Video.js player
    const videojs = window.videojs // Declare the videojs variable
    this.player = videojs(videoElement, playerOptions)

    // Setup event listeners and features
    this.player.ready(() => {
      console.log("Video.js player is ready")
      this.setupPlayerEvents()

      this.controls = new PlayerControls(this.player, this)
      this.controls.setupKeyboardShortcuts()
      this.controls.setupMobileFeatures()
      this.controls.setupTouchGestures()

      this.skipManager = new SkipManager(this.player, this)
      this.skipManager.initialize(intro, outro, skipIntroBtn, skipOutroBtn)

      this.subtitleHandler.updateSubtitleVisibility(this.player, this.detectCurrentLanguage())
      this.setupSubtitleHandling(subtitles)
      this.hideVideoJSLoadingSpinner()
      this.applySubtitleStyling() // Keep explicit call for initial styling
    })

    // Handle errors
    this.player.on("error", (error) => {
      console.error("Video.js error:", error)

      const playerError = this.player.error()
      if (playerError) {
        console.error(`[v0] Error code: ${playerError.code}, message: ${playerError.message}`)

        // Don't show error for subtitle issues (code 4)
        if (playerError.code === 4) {
          console.warn("Subtitle loading error detected, continuing without subtitles")
          return
        }

        if (playerError.code === 2 || playerError.code === 3) {
          console.warn("[v0] Network error detected, attempting recovery...")
          setTimeout(() => {
            this.attemptPlaybackRecovery()
          }, 1000)
          return
        }
      }

      this.showError("Video playback failed. Please try refreshing the page.")
    })
  }

  // Replaced by SubtitleHandler methods, but kept for reference if needed elsewhere
  formatSubtitlesForVideoJS(subtitles) {
    return this.subtitleHandler.formatSubtitlesForVideoJS(subtitles)
  }

  applySubtitleStyling() {
    this.subtitleHandler.applySubtitleStyling()
  }

  setupPlayerEvents() {
    // Track progress for resume functionality
    this.player.on("loadedmetadata", () => {
      console.log("[Player] Video metadata loaded")
      if (window.progressManager) {
        window.progressManager.startTracking(this.player.el().querySelector("video"))
      }

      this.detectCurrentLanguage() // Update language detection
      this.updateSubtitleVisibility() // Ensure subtitles are correctly set on metadata load
      this.setDefaultSubtitleTrack() // Ensure default track is set
    })

    this.player.on("waiting", () => {
      console.log("[Player] Video waiting for data")
      if (window.progressManager) {
        window.progressManager.showBufferIndicator()
      }
      this.monitorStalledPlayback()
    })

    this.player.on("canplay", () => {
      console.log("[Player] Video can play")
      if (window.progressManager) {
        window.progressManager.hideBufferIndicator()
      }
      // Clear any stalled playback monitoring
      if (this.stalledCheckInterval) {
        clearInterval(this.stalledCheckInterval)
        this.stalledCheckInterval = null
      }
    })

    this.player.on("playing", () => {
      if (window.progressManager) {
        window.progressManager.hideBufferIndicator()
      }
    })

    // Handle errors (duplicate, but kept for now as per original structure)
    this.player.on("error", (error) => {
      console.error("Video.js error:", error)

      // Check if it's a subtitle loading error
      const playerError = this.player.error()
      if (playerError && playerError.code === 4) {
        console.warn("Subtitle loading error detected, continuing without subtitles")
        // Don't show error for subtitle issues, just log it
        return
      }

      this.showError("Video playback failed. Please try refreshing the page.")
    })

    // Handle video end for auto-next
    this.player.on("ended", () => {
      console.log("Video ended")
      this.handleVideoEnd()
    })

    // Handle fullscreen changes
    this.player.on("fullscreenchange", () => {
      this.isFullscreen = this.player.isFullscreen()
      this.handleFullscreenChange()
    })

    // Handle play/pause for subtitle visibility
    this.player.on("play", () => {
      this.updateSubtitleVisibility()
    })

    this.player.on("pause", () => {
      this.updateSubtitleVisibility()
    })
  }

  monitorStalledPlayback() {
    if (this.stalledCheckInterval) {
      clearInterval(this.stalledCheckInterval)
    }

    let stalledCount = 0
    const maxStalledAttempts = 3

    this.stalledCheckInterval = setInterval(() => {
      if (!this.player || this.player.paused()) {
        clearInterval(this.stalledCheckInterval)
        this.stalledCheckInterval = null
        return
      }

      const time = this.player.currentTime()
      const buffered = this.player.buffered()

      // Check if playhead is stuck and buffered data is available
      if (time >= 0 && buffered.length > 0 && buffered.end(buffered.length - 1) > time + 2) {
        // Playhead is stuck but buffer has data ahead
        stalledCount++
        console.log(`[v0] Stalled playback detected (attempt ${stalledCount}/${maxStalledAttempts})`)

        if (stalledCount >= maxStalledAttempts) {
          clearInterval(this.stalledCheckInterval)
          this.stalledCheckInterval = null
          this.attemptPlaybackRecovery()
        }
      } else {
        stalledCount = 0
      }
    }, 1000)
  }

  attemptPlaybackRecovery() {
    if (!this.player) return

    console.log("[v0] Attempting playback recovery...")

    const currentTime = this.player.currentTime()
    const wasPlaying = !this.player.paused()

    try {
      // Stop and seek to current position to flush buffers
      this.player.pause()

      // Clear the buffer by seeking to a slightly different position
      const seekTime = Math.max(0, currentTime - 1)
      this.player.currentTime(seekTime)

      // Brief delay then attempt to resume
      setTimeout(() => {
        if (wasPlaying) {
          console.log("[v0] Resuming playback after recovery...")
          this.player.play().catch((err) => {
            console.error("[v0] Failed to resume playback:", err)
          })
        }
      }, 500)
    } catch (error) {
      console.error("[v0] Recovery attempt failed:", error)
    }
  }

  setDefaultSubtitleTrack() {
    this.subtitleHandler.setDefaultSubtitleTrack(this.player)
  }

  setupSubtitleHandling(subtitles) {
    console.log("[Subtitles] Setting up subtitle handling")
    this.player.ready(() => {
      setTimeout(() => {
        this.subtitleHandler.updateSubtitleVisibility(this.player, this.detectCurrentLanguage())
      }, 200)

      // Removed the direct listener here as SubtitleHandler manages textTracks events internally
    })

    // Removed the MutationObserver for language toggle as it's handled by SubtitleHandler
  }

  detectCurrentLanguage() {
    return this.subtitleHandler.detectCurrentLanguage()
  }

  handleTextTrackChange() {
    this.subtitleHandler.handleTextTrackChange(this.player, this.currentLanguage)
  }

  hasPreferredLanguageTrack(preferredLang) {
    return this.subtitleHandler.hasPreferredLanguageTrack(this.player, preferredLang)
  }

  updateSubtitleVisibility() {
    this.subtitleHandler.updateSubtitleVisibility(this.player, this.currentLanguage)
  }

  hideVideoJSLoadingSpinner() {
    // Hide Video.js default loading spinner and use our custom styling
    setTimeout(() => {
      const loadingSpinner = this.player.el().querySelector(".vjs-loading-spinner")
      if (loadingSpinner) {
        loadingSpinner.style.display = "none"
      }
    }, 1000)
  }

  setupKeyboardShortcuts() {
    this.controls.setupKeyboardShortcuts()
  }

  setupMobileFeatures() {
    this.controls.setupMobileFeatures()
  }

  setupTouchGestures() {
    this.controls.setupTouchGestures()
  }

  setupSkipButtons() {
    this.skipManager.initialize(this.intro, this.outro, this.skipIntroBtn, this.skipOutroBtn)
  }

  handleFullscreenChange() {
    const videoContainer = this.player.el().parentElement

    if (this.isFullscreen) {
      videoContainer.classList.add("fullscreen-active")

      // Auto-rotate to landscape on mobile devices
      if (screen.orientation && screen.orientation.lock) {
        screen.orientation.lock("landscape").catch((err) => {
          console.log("Screen orientation lock not supported:", err)
        })
      }
    } else {
      videoContainer.classList.remove("fullscreen-active")

      // Unlock orientation when exiting fullscreen
      if (screen.orientation && screen.orientation.unlock) {
        screen.orientation.unlock()
      }
    }
  }

  togglePlayPause() {
    this.controls.togglePlayPause()
  }

  toggleFullscreen() {
    this.controls.toggleFullscreen()
  }

  skipForward(seconds) {
    this.controls.skipForward(seconds)
  }

  skipBackward(seconds) {
    this.controls.skipBackward(seconds)
  }

  adjustVolume(delta) {
    this.controls.adjustVolume(delta)
  }

  toggleMute() {
    this.controls.toggleMute()
  }

  // Keep existing control indicator functionality
  showControlIndicator(action, value = null) {
    const indicator = document.createElement("div")
    indicator.className = "control-indicator youtube-style"

    let content = ""
    let icon = ""
    switch (action) {
      case "play":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z"/>
        </svg>`
        content = ""
        break
      case "pause":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M6 19h4V5H6v14zm8-14v12l8.5-6L13 6z"/>
        </svg>`
        content = ""
        break
      case "forward":
        icon = `<svg class="control-icon seek-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z"/>
        </svg>`
        content = `${value}s`
        indicator.classList.add("seek-forward")
        break
      case "backward":
        icon = `<svg class="control-icon seek-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M11 18V6l-8.5 6 8.5 6zm.5-6l8.5 6V6l-8.5 6z"/>
        </svg>`
        content = `${value}s`
        indicator.classList.add("seek-backward")
        break
      case "volume":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
        </svg>`
        content = `${value}%`
        break
      case "muted":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
        </svg>`
        content = "Muted"
        break
      case "unmuted":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
        </svg>`
        content = "Unmuted"
        break
      case "auto-skip":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z"/>
        </svg>`
        content = value || "Auto-skipped"
        indicator.classList.add("auto-skip")
        break
      case "skip":
        icon = `<svg class="control-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z"/>
        </svg>`
        content = value || "Skipped"
        indicator.classList.add("skip")
        break
    }

    const showText =
      !this.isMobileDevice() &&
      (action === "forward" ||
        action === "backward" ||
        action === "volume" ||
        action === "muted" ||
        action === "unmuted" ||
        action === "auto-skip" ||
        action === "skip")

    indicator.innerHTML = `
      <div class="control-content">
        ${icon}
        ${showText ? `<span class="control-text">${content}</span>` : ""}
      </div>
    `

    this.player.el().parentElement.appendChild(indicator)

    if (action === "forward" || action === "backward") {
      this.createSeekRipple(action === "forward" ? "right" : "left")
    }

    // Properly manage timeouts to ensure indicators are removed
    const indicatorId = `indicator-${Date.now()}-${Math.random()}`
    indicator.dataset.indicatorId = indicatorId

    // Store timeout reference for cleanup
    const timeoutId = setTimeout(
      () => {
        if (indicator && indicator.parentElement) {
          indicator.classList.add("fade-out")
          setTimeout(() => {
            if (indicator && indicator.parentElement) {
              indicator.remove()
            }
            // Clean up timeout reference
            this.controlIndicatorTimeouts.delete(indicatorId)
          }, 300)
        }
      },
      action === "auto-skip" || action === "skip" ? 2500 : 1500,
    )

    this.controlIndicatorTimeouts.set(indicatorId, timeoutId)
  }

  createSeekRipple(direction) {
    const ripple = document.createElement("div")
    ripple.className = `seek-ripple ${direction}`

    const videoRect = this.player.el().getBoundingClientRect()
    const centerX = direction === "right" ? videoRect.width * 0.75 : videoRect.width * 0.25
    const centerY = videoRect.height * 0.5

    ripple.style.left = `${centerX}px`
    ripple.style.top = `${centerY}px`

    this.player.el().parentElement.appendChild(ripple)

    setTimeout(() => {
      if (ripple.parentElement) {
        ripple.parentElement.removeChild(ripple)
      }
    }, 600)
  }

  showSeekIndicator(direction, seconds) {
    let indicator = document.querySelector(".seek-indicator")
    if (!indicator) {
      indicator = document.createElement("div")
      indicator.className = "seek-indicator youtube-seek"
      this.player.el().parentElement.appendChild(indicator)
    }

    const isForward = direction === "forward"
    const icon = isForward
      ? `<svg class="seek-arrow" viewBox="0 0 24 24" fill="currentColor">
          <path d="M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z"/>
        </svg>`
      : `<svg class="seek-arrow" viewBox="0 0 24 24" fill="currentColor">
          <path d="M11 18V6l-8.5 6 8.5 6zm.5-6l8.5 6V6l-8.5 6z"/>
        </svg>`

    const sign = isForward ? "+" : "-"
    const showTime = !this.isMobileDevice()

    indicator.innerHTML = `
      <div class="seek-content ${direction}">
        ${icon}
        ${showTime ? `<span class="seek-time">${sign}${Math.round(seconds)}s</span>` : ""}
      </div>
    `

    indicator.classList.remove("hide")
    indicator.classList.add("show", direction)

    // Clear existing timeout if any
    if (indicator.dataset.timeoutId) {
      clearTimeout(Number(indicator.dataset.timeoutId))
    }

    // Set new timeout
    const timeoutId = setTimeout(() => {
      this.hideSeekIndicator()
    }, 1000)

    indicator.dataset.timeoutId = timeoutId.toString()
  }

  hideSeekIndicator() {
    const indicator = document.querySelector(".seek-indicator")
    if (indicator) {
      // Clear timeout
      if (indicator.dataset.timeoutId) {
        clearTimeout(Number(indicator.dataset.timeoutId))
        delete indicator.dataset.timeoutId
      }

      indicator.classList.add("hide")
      setTimeout(() => {
        if (indicator && indicator.parentElement) {
          indicator.remove()
        }
      }, 300)
    }
  }

  handleVideoEnd() {
    if (window.progressManager) {
      window.progressManager.syncWatchedEpisodesToWatchlist()
    }
    // Kept the rest of the auto-next logic from original, though it might be redundant if handled by UI
    console.log("Video ended - checking auto next settings")

    // Check if auto next is enabled in settings
    if (!this.settings.autoplayNext) {
      console.log("Auto next disabled in settings")
      return
    }

    const nextBtn = document.getElementById("nextEpisodeBtn")
    if (nextBtn && nextBtn.href && !nextBtn.disabled) {
      console.log("Auto next enabled - showing notification")
      const nextUrl = nextBtn.href
      this.showAutoNextNotification(nextUrl)
      setTimeout(() => {
        // Double check settings before navigating
        const currentSettings = this.loadSettings()
        if (currentSettings.autoplayNext) {
          console.log("Navigating to next episode:", nextUrl)
          window.location.href = nextUrl
        } else {
          console.log("Auto next was disabled during countdown")
        }
      }, 5000)
    } else {
      console.log("No next episode available or button disabled")
    }
  }

  showAutoNextNotification(nextUrl) {
    const notification = document.createElement("div")
    notification.className =
      "fixed top-4 right-4 z-50 bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-4 rounded-xl shadow-2xl border border-purple-500/30 backdrop-blur-sm"
    notification.id = "auto-next-notification"

    let countdown = 3

    notification.innerHTML = `
      <div class="flex items-center gap-4">
        <div class="flex-shrink-0">
          <svg class="w-6 h-6 animate-spin text-purple-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
        </div>
        <div class="flex-1">
          <p class="font-semibold">Auto-playing next episode</p>
          <p class="text-sm text-purple-200" id="countdown-text">in <span id="countdown-number">${countdown}</span> seconds...</p>
        </div>
        <div class="flex gap-2">
          <button onclick="window.location.href='${nextUrl}'" class="px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium transition-colors">
            Play Now
          </button>
          <button onclick="this.closest('#auto-next-notification').remove()" class="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition-colors">
            Cancel
          </button>
        </div>
      </div>
    `

    document.body.appendChild(notification)

    // Animate in
    setTimeout(() => {
      notification.style.transform = "translateX(0)"
      notification.style.opacity = "1"
    }, 100)

    // Countdown timer
    const countdownInterval = setInterval(() => {
      countdown--
      const countdownElement = document.getElementById("countdown-number")
      if (countdownElement) {
        countdownElement.textContent = countdown
      }

      if (countdown <= 0) {
        clearInterval(countdownInterval)
      }
    }, 1000)

    // Auto remove after countdown
    setTimeout(() => {
      clearInterval(countdownInterval)
      if (notification.parentElement) {
        notification.remove()
      }
    }, 5500)
  }

  isMobileDevice() {
    return this.controls.isMobileDevice()
  }

  showError(message) {
    this.controls.showError(message)
  }

  destroy() {
    if (this.player) {
      this.player.dispose()
    }
    // Clear all timeouts
    this.controlIndicatorTimeouts.forEach((timeoutId) => clearTimeout(timeoutId))
    this.controlIndicatorTimeouts.clear()
    // Clear stalled playback interval
    if (this.stalledCheckInterval) {
      clearInterval(this.stalledCheckInterval)
      this.stalledCheckInterval = null
    }
  }

  saveSettings() {
    try {
      localStorage.setItem("yumeAnimeSettings", JSON.stringify(this.settings))
      console.log("[v0] Settings saved to localStorage")
    } catch (error) {
      console.error("Error saving settings:", error)
    }
  }

  updateSetting(key, value) {
    this.settings[key] = value
    this.saveSettings()
    console.log(`[v0] Updated setting ${key} to ${value}`)

    // Apply subtitle styling changes immediately
    if (key === "subtitleBackground") {
      this.applySubtitleStyling()
    }

    // Update subtitle language if changed
    if (key === "subtitleLanguage") {
      this.setDefaultSubtitleTrack()
    }
  }

  updateSettings(newSettings) {
    this.settings = { ...this.settings, ...newSettings }
    this.saveSettings()
    console.log("[Player] Settings updated:", this.settings)
    this.applySubtitleStyling() // Reapply subtitle styling with new settings
    this.updateSubtitleVisibility() // Update subtitle visibility if language preference changed
  }
}

// Utility functions
function jumpToEpisode() {
  const input = document.getElementById("jumpToEpisode")
  const episodeNumber = Number.parseInt(input.value)

  if (episodeNumber) {
    const episodeCard = document.querySelector(`[data-episode="${episodeNumber}"]`)
    if (episodeCard) {
      window.location.href = episodeCard.href
    } else {
      alert("Episode not found")
    }
  }
}

// Initialize everything when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  // Initialize progress manager - WatchProgressManager is available from watch-progress.js
  const WatchProgressManager = window.WatchProgressManager
  if (typeof WatchProgressManager !== "undefined") {
    window.progressManager = new WatchProgressManager()
  }

  // Initialize Video.js player
  const videojsPlayer = new VideoJSPlayer()
  videojsPlayer.initialize()

  // Store player reference globally for cleanup
  window.videojsPlayer = videojsPlayer
})

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
  if (window.videojsPlayer) {
    window.videojsPlayer.destroy()
  }
  if (window.progressManager) {
    window.progressManager.stopTracking()
  }
})

window.jumpToEpisode = jumpToEpisode
