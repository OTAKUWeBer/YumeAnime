// Improved HLS Video Player with Loading Screen and Fixed Control Hiding
class HLSVideoPlayer {
  constructor() {
    this.hls = null
    this.video = null
    this.intro = null
    this.outro = null
    this.skipButtonsContainer = null
    this.skipIntroBtn = null
    this.skipOutroBtn = null
    this.isFullscreen = false
    this.touchStartX = 0
    this.touchStartTime = 0
    this.isSeeking = false
    this.keyboardEnabled = true
    this.loadingOverlay = null
    this.bufferIndicator = null
    this.isBuffering = false
    this.controlIndicatorTimeouts = new Map() // Track timeouts for proper cleanup
    this.settings = this.loadSettings()
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
            videoQuality: "auto",
          }
    } catch (error) {
      console.error("Error loading settings:", error)
      return {
        autoplayNext: true,
        skipIntro: true,
        rememberPosition: true,
        defaultVolume: 80,
        preferredLanguage: "sub",
        videoQuality: "auto",
      }
    }
  }

  initialize() {
    console.log("=== HLS Player Initialization ===")

    this.video = document.getElementById("videoPlayer")
    this.skipButtonsContainer = document.getElementById("skipButtons")
    this.skipIntroBtn = document.getElementById("skipIntroBtn")
    this.skipOutroBtn = document.getElementById("skipOutroBtn")

    if (!this.video) {
      console.error("ERROR: Video element not found!")
      return false
    }

    // Apply volume setting
    this.video.volume = this.settings.defaultVolume / 100

    // Create loading overlay
    this.createLoadingOverlay()

    // Get data from video element with debugging
    const videoUrl = this.video.dataset.videoUrl
    console.log("Video URL:", videoUrl)
    console.log("Video URL type:", typeof videoUrl)
    console.log("Video URL length:", videoUrl ? videoUrl.length : 0)

    if (!videoUrl || videoUrl === "null" || videoUrl === "") {
      console.error("ERROR: No valid video URL provided!")
      this.showError("Video not available. Please try refreshing the page.")
      this.hideLoadingOverlay()
      return false
    }

    // Parse other data
    try {
      const subtitles = JSON.parse(this.video.dataset.subtitles || "[]")
      const introData = JSON.parse(this.video.dataset.intro || "{}")
      const outroData = JSON.parse(this.video.dataset.outro || "{}")

      this.intro = introData.start ? introData : null
      this.outro = outroData.start ? outroData : null

      console.log("Subtitles:", subtitles.length, "tracks")
      console.log("Intro:", this.intro)
      console.log("Outro:", this.outro)

      // Setup everything
      this.setupHLS(videoUrl)
      this.setupSubtitles(subtitles)
      this.setupSkipButtons()
      this.setupVideoEvents()
      this.setupKeyboardShortcuts()
      this.setupMobileFeatures()
      this.setupFullscreenHandling()
      this.setupBufferingIndicators()

      return true
    } catch (error) {
      console.error("Error parsing video data:", error)
      this.showError("Error loading video data")
      this.hideLoadingOverlay()
      return false
    }
  }

  createLoadingOverlay() {
    this.loadingOverlay = document.createElement("div")
    this.loadingOverlay.className = "loading-overlay"
    this.loadingOverlay.innerHTML = `
      <div class="loading-spinner"></div>
      <div class="loading-text">Loading video...</div>
      <div class="loading-subtext">Please wait while we prepare your content</div>
    `
    this.video.parentElement.appendChild(this.loadingOverlay)
  }

  hideLoadingOverlay() {
    if (this.loadingOverlay) {
      this.loadingOverlay.classList.add("fade-out")
      setTimeout(() => {
        if (this.loadingOverlay && this.loadingOverlay.parentElement) {
          this.loadingOverlay.remove()
          this.loadingOverlay = null
        }
      }, 300)
    }
  }

  createBufferIndicator() {
    if (!this.bufferIndicator) {
      this.bufferIndicator = document.createElement("div")
      this.bufferIndicator.className = "buffer-indicator"
      this.bufferIndicator.innerHTML = `
        <div class="buffer-spinner"></div>
      `
      this.video.parentElement.appendChild(this.bufferIndicator)
    }
  }

  showBufferIndicator() {
    if (!this.isBuffering) {
      this.isBuffering = true
      this.createBufferIndicator()
      setTimeout(() => {
        if (this.bufferIndicator) {
          this.bufferIndicator.classList.add("show")
        }
      }, 500) // Show buffer indicator after 500ms delay
    }
  }

  hideBufferIndicator() {
    this.isBuffering = false
    if (this.bufferIndicator) {
      this.bufferIndicator.classList.remove("show")
      setTimeout(() => {
        if (this.bufferIndicator && this.bufferIndicator.parentElement) {
          this.bufferIndicator.remove()
          this.bufferIndicator = null
        }
      }, 300)
    }
  }

  setupBufferingIndicators() {
    // Show buffer indicator when waiting for data
    this.video.addEventListener("waiting", () => {
      console.log("Video is waiting/buffering")
      this.showBufferIndicator()
    })

    // Hide buffer indicator when ready to play
    this.video.addEventListener("canplay", () => {
      console.log("Video can play - hiding buffer indicator")
      this.hideBufferIndicator()
    })

    // Hide buffer indicator when playing
    this.video.addEventListener("playing", () => {
      console.log("Video is playing")
      this.hideBufferIndicator()
    })

    // Show buffer indicator on stall
    this.video.addEventListener("stalled", () => {
      console.log("Video stalled")
      this.showBufferIndicator()
    })

    // Monitor buffer health
    this.video.addEventListener("progress", () => {
      if (this.video.buffered.length > 0) {
        const bufferedEnd = this.video.buffered.end(this.video.buffered.length - 1)
        const currentTime = this.video.currentTime
        const bufferAhead = bufferedEnd - currentTime

        // If buffer is low and video is playing, show buffer indicator
        if (bufferAhead < 2 && !this.video.paused && this.video.readyState < 3) {
          this.showBufferIndicator()
        }
      }
    })
  }

  setupKeyboardShortcuts() {
    console.log("=== Setting up Keyboard Shortcuts ===")

    // Make video container focusable
    const videoContainer = this.video.parentElement
    videoContainer.setAttribute("tabindex", "0")

    // Add keyboard event listener to document
    document.addEventListener("keydown", (e) => {
      if (!this.keyboardEnabled) return

      // Don't trigger shortcuts if user is typing in an input
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return

      switch (e.code) {
        case "Space":
          e.preventDefault()
          this.togglePlayPause()
          break
        case "KeyF":
          e.preventDefault()
          this.toggleFullscreen()
          break
        case "ArrowRight":
          e.preventDefault()
          this.skipForward(10)
          break
        case "ArrowLeft":
          e.preventDefault()
          this.skipBackward(10)
          break
        case "ArrowUp":
          e.preventDefault()
          this.adjustVolume(0.1)
          break
        case "ArrowDown":
          e.preventDefault()
          this.adjustVolume(-0.1)
          break
        case "KeyM":
          e.preventDefault()
          this.toggleMute()
          break
        case "KeyK":
          e.preventDefault()
          this.togglePlayPause()
          break
        case "KeyJ":
          e.preventDefault()
          this.skipBackward(10)
          break
        case "KeyL":
          e.preventDefault()
          this.skipForward(10)
          break
        case "Comma":
          if (this.video.paused) {
            e.preventDefault()
            this.skipBackward(1 / 30) // Frame by frame backward
          }
          break
        case "Period":
          if (this.video.paused) {
            e.preventDefault()
            this.skipForward(1 / 30) // Frame by frame forward
          }
          break
      }
    })

    console.log("Keyboard shortcuts enabled: Space, F, Arrow keys, M, K, J, L, comma, period")
  }

  setupMobileFeatures() {
    console.log("=== Setting up Mobile Features ===")

    const videoContainer = this.video.parentElement
    const lastTapTime = 0
    const tapCount = 0
    const tapTimeout = null

    videoContainer.addEventListener(
      "touchstart",
      (e) => {
        if (e.touches.length === 1) {
          this.touchStartX = e.touches[0].clientX
          this.touchStartTime = Date.now()
        }
      },
      { passive: true },
    )

    videoContainer.addEventListener(
      "touchmove",
      (e) => {
        if (e.touches.length === 1 && !this.isSeeking) {
          const touchX = e.touches[0].clientX
          const deltaX = touchX - this.touchStartX
          const containerWidth = videoContainer.offsetWidth

          // Only start seeking if moved more than 30px
          if (Math.abs(deltaX) > 30) {
            this.isSeeking = true
            const seekAmount = (deltaX / containerWidth) * this.video.duration
            const newTime = Math.max(0, Math.min(this.video.duration, this.video.currentTime + seekAmount))
            this.video.currentTime = newTime
            this.showSeekIndicator(seekAmount > 0 ? "forward" : "backward", Math.abs(seekAmount))
          }
        }
      },
      { passive: true },
    )

    videoContainer.addEventListener(
      "touchend",
      (e) => {
        const touchDuration = Date.now() - this.touchStartTime
        const currentTime = Date.now()
        const touchX = e.changedTouches[0].clientX
        const containerWidth = videoContainer.offsetWidth

        this.isSeeking = false
        this.hideSeekIndicator()
      },
      { passive: true },
    )

    if (!this.isMobileDevice()) {
      this.video.addEventListener("click", (e) => {
        // Don't trigger if clicking on controls or buttons
        if (
          e.target.closest(".subtitle-selector") ||
          e.target.closest("button") ||
          e.target.closest(".control-indicator")
        ) {
          return
        }
        this.togglePlayPause()
      })
    }
  }

  isMobileDevice() {
    return (
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
      (navigator.maxTouchPoints && navigator.maxTouchPoints > 2)
    )
  }

  setupFullscreenHandling() {
    console.log("=== Setting up Fullscreen Handling ===")

    // Listen for fullscreen changes
    document.addEventListener("fullscreenchange", () => {
      this.isFullscreen = !!document.fullscreenElement
      this.handleFullscreenChange()
    })

    document.addEventListener("webkitfullscreenchange", () => {
      this.isFullscreen = !!document.webkitFullscreenElement
      this.handleFullscreenChange()
    })

    document.addEventListener("mozfullscreenchange", () => {
      this.isFullscreen = !!document.mozFullScreenElement
      this.handleFullscreenChange()
    })
  }

  handleFullscreenChange() {
    const videoContainer = this.video.parentElement

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
    if (this.video.paused) {
      this.video.play()
      this.showControlIndicator("play")
    } else {
      this.video.pause()
      this.showControlIndicator("pause")
    }
  }

  toggleFullscreen() {
    const videoContainer = this.video.parentElement

    if (!this.isFullscreen) {
      if (videoContainer.requestFullscreen) {
        videoContainer.requestFullscreen()
      } else if (videoContainer.webkitRequestFullscreen) {
        videoContainer.webkitRequestFullscreen()
      } else if (videoContainer.mozRequestFullScreen) {
        videoContainer.mozRequestFullScreen()
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen()
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen()
      } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen()
      }
    }
  }

  skipForward(seconds) {
    this.video.currentTime = Math.min(this.video.duration, this.video.currentTime + seconds)
    this.showControlIndicator("forward", seconds)
  }

  skipBackward(seconds) {
    this.video.currentTime = Math.max(0, this.video.currentTime - seconds)
    this.showControlIndicator("backward", seconds)
  }

  adjustVolume(delta) {
    const newVolume = Math.max(0, Math.min(1, this.video.volume + delta))
    this.video.volume = newVolume
    this.showControlIndicator("volume", Math.round(newVolume * 100))
  }

  toggleMute() {
    this.video.muted = !this.video.muted
    this.showControlIndicator(this.video.muted ? "muted" : "unmuted")
  }

  // FIXED: Improved control indicator with proper timeout management
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
          <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
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
          <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
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

    this.video.parentElement.appendChild(indicator)

    if (action === "forward" || action === "backward") {
      this.createSeekRipple(action === "forward" ? "right" : "left")
    }

    // FIXED: Properly manage timeouts to ensure indicators are removed
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
    ) // Show auto-skip notifications longer

    this.controlIndicatorTimeouts.set(indicatorId, timeoutId)
  }

  createSeekRipple(direction) {
    const ripple = document.createElement("div")
    ripple.className = `seek-ripple ${direction}`

    const videoRect = this.video.getBoundingClientRect()
    const centerX = direction === "right" ? videoRect.width * 0.75 : videoRect.width * 0.25
    const centerY = videoRect.height * 0.5

    ripple.style.left = `${centerX}px`
    ripple.style.top = `${centerY}px`

    this.video.parentElement.appendChild(ripple)

    setTimeout(() => {
      if (ripple.parentElement) {
        ripple.parentElement.removeChild(ripple)
      }
    }, 600)
  }

  // FIXED: Improved seek indicator with proper timeout management
  showSeekIndicator(direction, seconds) {
    let indicator = document.querySelector(".seek-indicator")
    if (!indicator) {
      indicator = document.createElement("div")
      indicator.className = "seek-indicator youtube-seek"
      this.video.parentElement.appendChild(indicator)
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

  handleHLSError(data) {
    switch (data.details) {
      case window.Hls.ErrorDetails.MANIFEST_LOAD_ERROR:
        this.showError("Failed to load video manifest. Please try again.")
        break
      case window.Hls.ErrorDetails.NETWORK_ERROR:
        this.showError("Network error. Please check your connection.")
        break
      case window.Hls.ErrorDetails.MEDIA_ERROR:
        console.log("Attempting to recover from media error...")
        this.hls.recoverMediaError()
        break
      default:
        this.showError("Video playback error. Please try refreshing the page.")
        break
    }
  }

  setupHLS(videoUrl) {
    console.log("=== Setting up HLS ===")
    console.log("Video URL:", videoUrl)

    if (window.Hls && window.Hls.isSupported()) {
      console.log("HLS.js is supported, initializing...")
      this.hls = new window.Hls({
        debug: false,
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 90,
      })

      this.hls.loadSource(videoUrl)
      this.hls.attachMedia(this.video)

      this.hls.on(window.Hls.Events.MANIFEST_PARSED, () => {
        console.log("HLS manifest parsed successfully")
        this.hideLoadingOverlay()
        this.video.play().catch((e) => {
          console.log("Autoplay prevented:", e)
        })
      })

      this.hls.on(window.Hls.Events.ERROR, (event, data) => {
        console.error("HLS error:", data)
        this.hideLoadingOverlay()
        if (data.fatal) {
          this.handleHLSError(data)
        }
      })
    } else if (this.video.canPlayType("application/vnd.apple.mpegurl")) {
      console.log("Native HLS support detected")
      this.video.src = videoUrl
      this.hideLoadingOverlay()
    } else {
      console.error("HLS not supported")
      this.showError("Your browser doesn't support HLS video playback")
      this.hideLoadingOverlay()
    }
  }

  setupSubtitles(subtitles) {
    console.log("=== Setting up Subtitles ===")
    console.log("Subtitles data:", subtitles)

    if (!subtitles || subtitles.length === 0) {
      console.log("No subtitles available")
      return
    }

    const existingTracks = this.video.querySelectorAll("track")
    existingTracks.forEach((track) => track.remove())

    let englishTrackIndex = -1
    let defaultTrackIndex = -1

    // Look for English track or explicitly marked default
    subtitles.forEach((subtitle, index) => {
      if (subtitle.lang === "en" || subtitle.label?.toLowerCase().includes("english")) {
        englishTrackIndex = index
      }
      if (subtitle.default === true) {
        defaultTrackIndex = index
      }
    })

    // Prioritize English, then explicit default, then first track
    const preferredDefaultIndex =
      englishTrackIndex !== -1 ? englishTrackIndex : defaultTrackIndex !== -1 ? defaultTrackIndex : 0

    subtitles.forEach((subtitle, index) => {
      console.log(`Adding subtitle track ${index + 1}:`, subtitle)

      const track = document.createElement("track")
      track.kind = subtitle.kind || "subtitles"
      track.label = subtitle.label || `Subtitle ${index + 1}`
      track.srclang = subtitle.lang || "en"
      track.src = subtitle.file

      track.crossOrigin = "anonymous"

      if (index === preferredDefaultIndex) {
        track.default = true
        track.setAttribute("default", "")
        console.log(`Setting track ${index + 1} (${subtitle.label}) as default`)
      }

      this.video.appendChild(track)

      track.addEventListener("load", () => {
        console.log(`Subtitle track ${index + 1} loaded successfully`)
        if (index === preferredDefaultIndex) {
          this.enableSubtitles()
        }
      })

      track.addEventListener("error", (e) => {
        console.error(`Subtitle track ${index + 1} failed to load:`, e)
        console.log("Attempting to reload track without CORS restrictions...")
        track.crossOrigin = ""
      })
    })

    setTimeout(() => {
      this.enableSubtitles()
    }, 200)
  }

  setupSkipButtons() {
    if (!this.intro && !this.outro) return

    let introSkipTimeout = null
    let outroSkipTimeout = null

    this.video.addEventListener("timeupdate", () => {
      const currentTime = this.video.currentTime

      // Show/hide intro skip button
      if (this.intro && currentTime >= this.intro.start && currentTime <= this.intro.end) {
        this.skipIntroBtn.style.display = "block"
        this.skipIntroBtn.classList.add("show")

        if (this.settings.skipIntro && !introSkipTimeout) {
          introSkipTimeout = setTimeout(() => {
            if (this.video.currentTime >= this.intro.start && this.video.currentTime <= this.intro.end) {
              this.video.currentTime = this.intro.end
              this.showControlIndicator("auto-skip", "Intro skipped")
              console.log("[v0] Auto-skipped intro")
            }
          }, 100) // Immediate skip when setting is enabled
        }
      } else {
        this.skipIntroBtn.style.display = "none"
        this.skipIntroBtn.classList.remove("show")
        if (introSkipTimeout) {
          clearTimeout(introSkipTimeout)
          introSkipTimeout = null
        }
      }

      // Show/hide outro skip button
      if (this.outro && currentTime >= this.outro.start && currentTime <= this.outro.end) {
        this.skipOutroBtn.style.display = "block"
        this.skipOutroBtn.classList.add("show")

        if (this.settings.skipIntro && !outroSkipTimeout) {
          outroSkipTimeout = setTimeout(() => {
            if (this.video.currentTime >= this.outro.start && this.video.currentTime <= this.outro.end) {
              this.video.currentTime = this.outro.end
              this.showControlIndicator("auto-skip", "Outro skipped")
              console.log("[v0] Auto-skipped outro")
            }
          }, 100) // Immediate skip when setting is enabled
        }
      } else {
        this.skipOutroBtn.style.display = "none"
        this.skipOutroBtn.classList.remove("show")
        if (outroSkipTimeout) {
          clearTimeout(outroSkipTimeout)
          outroSkipTimeout = null
        }
      }
    })

    // Skip button event listeners
    this.skipIntroBtn.addEventListener("click", () => {
      if (this.intro) {
        this.video.currentTime = this.intro.end
        if (introSkipTimeout) {
          clearTimeout(introSkipTimeout)
          introSkipTimeout = null
        }
        this.showControlIndicator("skip", "Intro skipped")
      }
    })

    this.skipOutroBtn.addEventListener("click", () => {
      if (this.outro) {
        this.video.currentTime = this.outro.end
        if (outroSkipTimeout) {
          clearTimeout(outroSkipTimeout)
          outroSkipTimeout = null
        }
        this.showControlIndicator("skip", "Outro skipped")
      }
    })
  }

  setupVideoEvents() {
    this.video.addEventListener("loadstart", () => {
      console.log("Video load started")
      setTimeout(() => this.enableSubtitles(), 100)
    })

    this.video.addEventListener("loadedmetadata", () => {
      console.log("Video metadata loaded")
      this.hideLoadingOverlay()
      this.enableSubtitles()

      if (window.progressManager) {
        window.progressManager.startTracking(this.video)
      }
    })

    this.video.addEventListener("canplay", () => {
      console.log("Video can play - ensuring subtitles are enabled")
      this.hideLoadingOverlay()
      this.enableSubtitles()
    })

    this.video.addEventListener("loadeddata", () => {
      console.log("Video data loaded - enabling subtitles")
      this.hideLoadingOverlay()
      this.enableSubtitles()
    })

    this.video.addEventListener("play", () => {
      console.log("Video started playing - final subtitle check")
      setTimeout(() => {
        this.enableSubtitles()
      }, 100)
    })

    this.video.addEventListener("ended", () => {
      console.log("Video ended")
      this.handleVideoEnd()
    })
    this.video.addEventListener("addtrack", () => {
      console.log("Track added to video")
      setTimeout(() => this.enableSubtitles(), 50)
    })

    this.video.addEventListener("error", (e) => {
      console.error("Video element error:", e)
      this.hideLoadingOverlay()
      this.showError("Video playback failed. Please try refreshing the page.")
    })
  }

  handleVideoEnd() {
    console.log("Video ended - checking auto next settings")
    
    // Check if auto next is enabled in settings
    if (!this.settings.autoplayNext) {
      console.log("Auto next disabled in settings")
      return
    }
    
    const nextBtn = document.getElementById("nextEpisodeBtn")
    if (nextBtn && nextBtn.href && !nextBtn.disabled) {
      console.log("Auto next enabled - showing notification")
      this.showAutoNextNotification(nextBtn.href)
      setTimeout(() => {
        // Double check settings before navigating
        const currentSettings = this.loadSettings()
        if (currentSettings.autoplayNext) {
          console.log("Navigating to next episode:", nextBtn.href)
          window.location.href = nextBtn.href
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
    notification.className = "fixed top-4 right-4 z-50 bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-4 rounded-xl shadow-2xl border border-purple-500/30 backdrop-blur-sm"
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
      notification.style.transform = 'translateX(0)'
      notification.style.opacity = '1'
    }, 100)
    
    // Countdown timer
    const countdownInterval = setInterval(() => {
      countdown--
      const countdownElement = document.getElementById('countdown-number')
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
  enableSubtitles() {
    console.log("=== Enabling Subtitles ===")

    if (this.video.textTracks && this.video.textTracks.length > 0) {
      console.log("Text tracks available:", this.video.textTracks.length)

      for (let i = 0; i < this.video.textTracks.length; i++) {
        this.video.textTracks[i].mode = "disabled"
      }

      let englishTrack = null
      let defaultTrack = null
      const firstTrack = this.video.textTracks[0]

      for (let i = 0; i < this.video.textTracks.length; i++) {
        const track = this.video.textTracks[i]
        if (track.language === "en" || track.label?.toLowerCase().includes("english")) {
          englishTrack = track
          break
        }
        if (track.default || track.mode === "showing") {
          defaultTrack = track
        }
      }

      // Prioritize English, then default, then first track
      const trackToEnable = englishTrack || defaultTrack || firstTrack

      if (trackToEnable) {
        trackToEnable.mode = "showing"
        console.log(`Enabled subtitle track: ${trackToEnable.label} (${trackToEnable.language})`)

        setTimeout(() => {
          if (trackToEnable.mode !== "showing") {
            trackToEnable.mode = "showing"
            console.log("Force-enabled subtitles again")
          }

          console.log("Final subtitle track state:", {
            mode: trackToEnable.mode,
            readyState: trackToEnable.readyState,
            cues: trackToEnable.cues ? trackToEnable.cues.length : "not loaded",
            language: trackToEnable.language,
            label: trackToEnable.label,
          })
        }, 500)
      }
    } else {
      console.log("No text tracks available yet")
    }
  }

  showError(message) {
    // Remove existing error message
    const existingError = document.querySelector(".error-message")
    if (existingError) {
      existingError.remove()
    }

    const errorDiv = document.createElement("div")
    errorDiv.className = "error-message"
    errorDiv.textContent = message

    this.video.parentElement.appendChild(errorDiv)

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (errorDiv.parentElement) {
        errorDiv.remove()
      }
    }, 5000)
  }

  destroy() {
    if (this.hls) {
      this.hls.destroy()
    }
    if (this.loadingOverlay && this.loadingOverlay.parentElement) {
      this.loadingOverlay.remove()
    }
    if (this.bufferIndicator && this.bufferIndicator.parentElement) {
      this.bufferIndicator.remove()
    }
    document.removeEventListener("keydown", this.handleKeydown)
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

  // Initialize HLS player
  const hlsPlayer = new HLSVideoPlayer()
  hlsPlayer.initialize()

  // Store player reference globally for cleanup
  window.hlsPlayer = hlsPlayer
})

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
  if (window.hlsPlayer) {
    window.hlsPlayer.destroy()
  }
  if (window.progressManager) {
    window.progressManager.stopTracking()
  }
})

window.jumpToEpisode = jumpToEpisode
