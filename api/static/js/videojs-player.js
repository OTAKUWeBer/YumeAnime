// Video.js Player with all existing functionality preserved
class VideoJSPlayer {
  constructor() {
    this.player = null
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
    this.controlIndicatorTimeouts = new Map()
    this.settings = this.loadSettings()
    this.currentLanguage = "sub" // Track current language for subtitle visibility
    this.stalledCheckInterval = null // For stalled playback monitoring
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
            subtitleLanguage: "English", // Added default subtitle language
            subtitleBackground: "transparent", // Added default transparent background
            forceSubtitlesOff: false, // Added default force subtitles off setting
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
        subtitleLanguage: "English", // Added default subtitle language
        subtitleBackground: "transparent", // Added default transparent background
        forceSubtitlesOff: false, // Added default force subtitles off setting
      }
    }
  }

  initialize() {
    console.log("=== Video.js Player Initialization ===")

    const videoElement = document.getElementById("videoPlayer")
    this.skipButtonsContainer = document.getElementById("skipButtons")
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

      // Initialize Video.js player
      this.setupVideoJS(videoElement, videoUrl, subtitles)

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

  setupVideoJS(videoElement, videoUrl, subtitles) {
    console.log("=== Setting up Video.js ===")

    // Video.js configuration
    const playerOptions = {
      fluid: true,
      responsive: true,
      aspectRatio: "16:9",
      playbackRates: [0.5, 0.75, 1, 1.25, 1.5, 2],
      volume: this.settings.defaultVolume / 100,
      html5: {
        vhs: {
          overrideNative: true,
          enableLowInitialPlaylist: true,
          smoothQualityChange: true,
          useBandwidthFromLocalStorage: true,
          segmentDuration: 10,
          maxPlaylistRetries: 3,
          // Retry failed segments with exponential backoff
          segmentRetryOptions: {
            maxRetries: 3,
            retryDelay: 200, // Initial retry delay in ms
            backoffFactor: 2, // Exponential backoff multiplier
          },
          // Timeout settings for segment requests
          segmentRequestTimeout: 30000, // 30 seconds for segment requests
          // Handle stalled/stuck playback
          stalledMonitoringInterval: 1000,
          // Lower the threshold for detecting stalled playback
          highWaterMark: 20 * 1000 * 1000, // 20MB buffer
          bandwidth: 4194304, // 4Mbps initial bandwidth estimate
          // Adaptive bitrate settings
          minPlaylistRetryDelay: 100,
          maxPlaylistRetryDelay: 30000,
          playlistRetryDelayBase: 2,
          playlistRetryDelayMax: 30,
          discontinuitySequence: true,
          // Better segment loading strategy
          bufferBasedABR: true,
          baseTolerance: 100,
          baseTargetDuration: 10,
        },
        nativeVideoTracks: false,
        nativeAudioTracks: false,
        nativeTextTracks: false,
      },
      sources: [
        {
          src: videoUrl,
          type: "application/x-mpegURL",
        },
      ],
      tracks: this.formatSubtitlesForVideoJS(subtitles),
    }

    // Initialize Video.js player
    const videojs = window.videojs // Declare the videojs variable
    this.player = videojs(videoElement, playerOptions)

    // Setup event listeners and features
    this.player.ready(() => {
      console.log("Video.js player is ready")
      this.setupPlayerEvents()
      this.setupKeyboardShortcuts()
      this.setupMobileFeatures()
      this.setupSkipButtons()
      this.setupSubtitleHandling(subtitles)
      this.hideVideoJSLoadingSpinner()
      this.applySubtitleStyling()
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

  formatSubtitlesForVideoJS(subtitles) {
    if (!subtitles || subtitles.length === 0) {
      console.log("[Subtitles] No subtitles provided")
      return []
    }

    console.log("[Subtitles] Raw subtitle data:", JSON.stringify(subtitles, null, 2))

    // Language name to code mapping
    const langToCode = {
      english: "en",
      "chinese - traditional": "zh-Hant",
      "chinese - simplified": "zh-Hans",
      indonesian: "id",
      korean: "ko",
      malay: "ms",
      thai: "th",
      spanish: "es",
      french: "fr",
      german: "de",
      japanese: "ja",
      arabic: "ar",
      portuguese: "pt",
      russian: "ru",
      italian: "it",
      vietnamese: "vi",
    }

    const normalizeLabel = (s) => {
      if (!s || s === "null" || s === "undefined") return ""
      s = String(s).trim()

      // Title case each word while preserving separators
      return s
        .split(/(\s+|-)/)
        .map((part) => {
          if (!part || /^\s*$/.test(part) || part === "-") return part
          return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase()
        })
        .join("")
    }

    // Try to extract language from filename
    const extractLanguageFromFilename = (filename) => {
      if (!filename) return null

      // Remove query params and extension
      const cleanName = filename.split("?")[0].replace(/\.(vtt|srt|ass|ssa)$/i, "")

      // Common patterns: en.vtt, english.vtt, en-US.vtt, subtitle-en.vtt
      const patterns = [
        /[._-](en|english)[._-]?/i,
        /[._-](zh[-_]?hant|chinese[-_]?traditional)[._-]?/i,
        /[._-](zh[-_]?hans|chinese[-_]?simplified)[._-]?/i,
        /[._-](id|indonesian)[._-]?/i,
        /[._-](ko|korean)[._-]?/i,
        /[._-](ms|malay)[._-]?/i,
        /[._-](th|thai)[._-]?/i,
        /[._-](es|spanish)[._-]?/i,
        /[._-](fr|french)[._-]?/i,
        /[._-](de|german)[._-]?/i,
        /[._-](ja|japanese)[._-]?/i,
        /[._-](ar|arabic)[._-]?/i,
        /[._-](pt|portuguese)[._-]?/i,
        /[._-](ru|russian)[._-]?/i,
        /[._-](it|italian)[._-]?/i,
        /[._-](vi|vietnamese)[._-]?/i,
      ]

      for (const pattern of patterns) {
        const match = cleanName.match(pattern)
        if (match) {
          return match[1].toLowerCase()
        }
      }

      return null
    }

    // ENHANCED: Filter valid subtitle tracks with stricter validation
    const candidates = subtitles.filter((subtitle) => {
      const subFile = subtitle.file || subtitle.url
      if (!subFile || subFile === "null" || subFile === "") return false

      const labelOrLang = (subtitle.lang || subtitle.label || "").toString().toLowerCase()
      const kind = (subtitle.kind || "").toString().toLowerCase()

      // CRITICAL: Skip any track that's explicitly NOT subtitles/captions
      if (kind && kind !== "subtitles" && kind !== "captions" && kind !== "") {
        console.warn("[Subtitles] Skipping non-subtitle track (wrong kind):", subtitle)
        return false
      }

      // Skip thumbnails, posters, images, sprites, metadata
      if (
        labelOrLang.includes("thumb") ||
        labelOrLang.includes("thumbnail") ||
        labelOrLang.includes("poster") ||
        labelOrLang.includes("image") ||
        labelOrLang.includes("sprite") ||
        labelOrLang.includes("preview") ||
        labelOrLang.includes("metadata") ||
        labelOrLang.includes("chapter")
      ) {
        console.warn("[Subtitles] Skipping non-subtitle track:", subtitle)
        return false
      }

      // Skip image files and common sprite formats
      if (/\.(jpe?g|png|gif|webp|bmp|svg|vtt\.jpg|vtt\.png)(\?.*)?$/i.test(subFile)) {
        console.warn("[Subtitles] Skipping image file:", subFile)
        return false
      }
      return true
    })

    console.log(`[Subtitles] Filtered ${candidates.length} valid subtitle tracks from ${subtitles.length} total`)

    // Map to Video.js format
    const tracks = candidates.map((subtitle, index) => {
      const subFile = subtitle.file || subtitle.url

      // Get the raw label/lang value
      let rawLabel = subtitle.label || subtitle.lang || ""

      // If no label/lang, try to extract from filename
      if (!rawLabel || rawLabel === "null" || rawLabel === "undefined") {
        const extractedLang = extractLanguageFromFilename(subFile)
        if (extractedLang) {
          rawLabel = extractedLang
          console.log(`[Subtitles] Extracted language from filename: ${extractedLang}`)
        }
      }

      // Create readable label
      const label =
        rawLabel && rawLabel !== "null" && rawLabel !== "undefined" ? normalizeLabel(rawLabel) : `Subtitle ${index + 1}`

      // Get language code
      const langKey = (rawLabel || "").toString().toLowerCase()
      let srclang = subtitle.srclang || langToCode[langKey]

      if (!srclang) {
        // Try normalized version
        const normalizedKey = normalizeLabel(langKey).toLowerCase()
        srclang = langToCode[normalizedKey]
      }

      if (!srclang) {
        // Try partial match (e.g., "english" in "english-us")
        for (const [key, code] of Object.entries(langToCode)) {
          if (langKey.includes(key)) {
            srclang = code
            break
          }
        }
      }

      if (!srclang) {
        // Fallback: extract first two letters
        const inferred = langKey.replace(/[^a-z]/gi, "").slice(0, 2) || "en"
        srclang = inferred
      }

      // Check if this should be the default track
      const isEnglish = label.toLowerCase().includes("english") || srclang.startsWith("en")
      const shouldBeDefault =
        isEnglish && this.settings.subtitleLanguage === "English" && this.currentLanguage === "sub"

      console.log(
        `[Subtitles] Track ${index}: label="${label}", srclang="${srclang}", file="${subFile}", default=${shouldBeDefault}`,
      )

      return {
        kind: "subtitles",
        src: subFile,
        srclang,
        label,
        default: shouldBeDefault,
        mode: shouldBeDefault ? "showing" : "disabled",
      }
    })

    console.log(`[Subtitles] Formatted ${tracks.length} subtitle tracks`)
    return tracks
  }

  applySubtitleStyling() {
    const existingStyle = document.getElementById("videojs-subtitle-custom-style")
    if (existingStyle) {
      existingStyle.remove()
    }

    const style = document.createElement("style")
    style.id = "videojs-subtitle-custom-style"

    style.textContent = `
      .video-js .vjs-text-track-cue {
        background: transparent !important;
        color: white !important;
        font-size: 18px !important;
        line-height: 1.4 !important;
        padding: 0 !important;
        border-radius: 0 !important;
        font-family: "Inter", sans-serif !important;
        font-weight: 500 !important;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.9) !important;
        border: none !important;
      }
      
      /* Mobile adjustments */
      @media (max-width: 768px) {
        .video-js .vjs-text-track-cue {
          font-size: 16px !important;
          padding: 0 !important;
        }
        
        .video-container.fullscreen-active .video-js .vjs-text-track-cue {
          font-size: 22px !important;
          padding: 0 !important;
        }
      }
      
      @media (max-width: 480px) {
        .video-js .vjs-text-track-cue {
          font-size: 18px !important;
          padding: 0 !important;
        }
        
        .video-container.fullscreen-active .video-js .vjs-text-track-cue {
          font-size: 26px !important;
          padding: 0 !important;
        }
      }
    `

    document.head.appendChild(style)
    console.log(`[v0] Applied clean subtitle styling with no background or borders`)
  }

  setupPlayerEvents() {
    // Track progress for resume functionality
    this.player.on("loadedmetadata", () => {
      console.log("[Player] Video metadata loaded")
      if (window.progressManager) {
        window.progressManager.startTracking(this.player.el().querySelector("video"))
      }

      this.detectCurrentLanguage()
      this.updateSubtitleVisibility()
      this.setDefaultSubtitleTrack()
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

    // Handle errors
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
    if (!this.player || !this.player.textTracks) {
      console.warn("[Subtitles] Player not ready for subtitle setup")
      return
    }

    const textTracks = this.player.textTracks()
    console.log(`[Subtitles] Total tracks available: ${textTracks.length}`)

    let englishTrack = null
    let firstTrack = null

    for (let i = 0; i < textTracks.length; i++) {
      const track = textTracks[i]
      console.log(`[Subtitles] Track ${i}: kind=${track.kind}, label=${track.label}, mode=${track.mode}`)

      if (track.kind === "subtitles" || track.kind === "captions") {
        if (!firstTrack) firstTrack = track
        if (track.label && track.label.toLowerCase().includes("english")) {
          englishTrack = track
        }
      }
    }

    if (this.currentLanguage === "sub") {
      const defaultTrack = englishTrack || firstTrack
      if (defaultTrack) {
        for (let i = 0; i < textTracks.length; i++) {
          textTracks[i].mode = "disabled"
        }
        defaultTrack.mode = "showing"
        console.log(`[Subtitles] Enabled subtitle track: ${defaultTrack.label}`)
      } else {
        console.warn("[Subtitles] No subtitle tracks found to enable")
      }
    } else {
      console.log("[Subtitles] Dub mode - subtitles disabled")
      for (let i = 0; i < textTracks.length; i++) {
        textTracks[i].mode = "disabled"
      }
    }
  }

  setupSubtitleHandling(subtitles) {
    console.log("[Subtitles] Setting up subtitle handling with", subtitles ? subtitles.length : 0, "tracks")

    this.player.ready(() => {
      this.detectCurrentLanguage()

      setTimeout(() => {
        this.updateSubtitleVisibility()
        this.setDefaultSubtitleTrack()
      }, 200)

      this.player.textTracks().on("change", () => {
        console.log("[Subtitles] Text tracks changed")
        this.handleTextTrackChange()
      })

      this.player.on("texttrackchange", () => {
        console.log("[Subtitles] Text track change event fired")
      })
    })

    const languageToggle = document.querySelector(".language-toggle")
    if (languageToggle) {
      const observer = new MutationObserver(() => {
        this.detectCurrentLanguage()
        this.updateSubtitleVisibility()
      })
      observer.observe(languageToggle, { childList: true, subtree: true })
    }
  }

  detectCurrentLanguage() {
    const urlParams = new URLSearchParams(window.location.search)
    const epParam = urlParams.get("ep")

    if (epParam && epParam.includes("-dub")) {
      this.currentLanguage = "dub"
      console.log(`[Language] Detected from URL: dub`)
      return
    }

    const languageToggle = document.querySelector(".language-toggle")
    if (languageToggle) {
      const activeButton = languageToggle.querySelector(".active")
      if (activeButton) {
        this.currentLanguage = activeButton.textContent.toLowerCase().includes("dub") ? "dub" : "sub"
        console.log(`[Language] Detected from UI: ${this.currentLanguage}`)
        return
      }
    }

    this.currentLanguage = "sub"
    console.log(`[Language] Default: sub`)
  }

  handleTextTrackChange() {
    const textTracks = this.player.textTracks()

    for (let i = 0; i < textTracks.length; i++) {
      const track = textTracks[i]

      // Log track status for debugging
      console.log(`[v0] Track ${i}: mode=${track.mode}, kind=${track.kind}, language=${track.language}`)

      // Ensure metadata tracks don't show as subtitles
      if (track.kind === "metadata" || track.kind === "chapters") {
        track.mode = "hidden"
        continue
      }

      // Handle subtitle tracks based on current language
      if (track.kind === "subtitles" || track.kind === "captions") {
        if (this.currentLanguage === "dub") {
          track.mode = "disabled"
        } else if (this.currentLanguage === "sub") {
          const isPreferredLanguage =
            track.label && track.label.toLowerCase().includes(this.settings.subtitleLanguage.toLowerCase())
          const isFirstTrack = i === 0

          if (
            isPreferredLanguage ||
            (isFirstTrack && !this.hasPreferredLanguageTrack(this.settings.subtitleLanguage))
          ) {
            track.mode = "showing"
          } else {
            track.mode = "disabled"
          }
        }
      }
    }
  }

  hasPreferredLanguageTrack(preferredLang) {
    if (!this.player || !this.player.textTracks) return false

    const textTracks = this.player.textTracks()
    for (let i = 0; i < textTracks.length; i++) {
      const track = textTracks[i]
      if (track.kind === "subtitles" || track.kind === "captions") {
        if (track.label && track.label.toLowerCase().includes(preferredLang.toLowerCase())) {
          return true
        }
      }
    }
    return false
  }

  updateSubtitleVisibility() {
    if (!this.player || !this.player.textTracks) return

    const textTracks = this.player.textTracks()
    console.log(`[v0] Updating subtitle visibility for language: ${this.currentLanguage}`)

    if (this.settings.forceSubtitlesOff || this.settings.subtitleLanguage === "off") {
      for (let i = 0; i < textTracks.length; i++) {
        const track = textTracks[i]
        if (track.kind === "subtitles" || track.kind === "captions") {
          track.mode = "disabled"
        }
      }
      console.log(`[v0] All subtitles disabled due to user preference`)
      return
    }

    for (let i = 0; i < textTracks.length; i++) {
      const track = textTracks[i]

      // Skip non-subtitle tracks
      if (track.kind !== "subtitles" && track.kind !== "captions") {
        continue
      }

      if (this.currentLanguage === "dub") {
        track.mode = "disabled"
        console.log(`[v0] Disabled subtitle track ${i} for dub audio`)
      } else if (this.currentLanguage === "sub") {
        const preferredLang = this.settings.subtitleLanguage || "English"
        const isPreferredLanguage = track.label && track.label.toLowerCase().includes(preferredLang.toLowerCase())
        const isFirstTrack = i === 0

        if (isPreferredLanguage || (isFirstTrack && !this.hasPreferredLanguageTrack(preferredLang))) {
          track.mode = "showing"
          console.log(`[v0] Enabled subtitle track ${i} (${track.label}) for sub audio`)
        } else {
          track.mode = "disabled"
        }
      }
    }
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
    console.log("=== Setting up Keyboard Shortcuts ===")

    // Make video container focusable
    const videoContainer = this.player.el().parentElement
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
          if (this.player.paused()) {
            e.preventDefault()
            this.skipBackward(1 / 30) // Frame by frame backward
          }
          break
        case "Period":
          if (this.player.paused()) {
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

    const videoContainer = this.player.el().parentElement

    if (this.isMobileDevice()) {
      // On mobile, ensure video doesn't autoplay without user interaction
      this.player.ready(() => {
        // Disable autoplay on mobile to prevent issues
        this.player.autoplay(false)

        // Add user interaction detection for mobile resume
        const handleFirstInteraction = () => {
          console.log("[v0] User interaction detected on mobile")
          // Check if we need to resume from saved position
          if (window.progressManager) {
            const currentProgress = window.progressManager.getCurrentProgress()
            if (currentProgress.watchTime > 30) {
              // Small delay to ensure video is ready
              setTimeout(() => {
                if (this.player.currentTime() < 5) {
                  this.player.currentTime(currentProgress.watchTime)
                  console.log(
                    `[v0] Mobile resume applied: ${window.progressManager.formatTime(currentProgress.watchTime)}`,
                  )
                }
              }, 200)
            }
          }

          // Remove listeners after first interaction
          videoContainer.removeEventListener("touchstart", handleFirstInteraction)
          videoContainer.removeEventListener("click", handleFirstInteraction)
        }

        videoContainer.addEventListener("touchstart", handleFirstInteraction, { once: true })
        videoContainer.addEventListener("click", handleFirstInteraction, { once: true })
      })
    }

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
            const seekAmount = (deltaX / containerWidth) * this.player.duration()
            const newTime = Math.max(0, Math.min(this.player.duration(), this.player.currentTime() + seekAmount))
            this.player.currentTime(newTime)
            this.showSeekIndicator(seekAmount > 0 ? "forward" : "backward", Math.abs(seekAmount))
          }
        }
      },
      { passive: true },
    )

    videoContainer.addEventListener(
      "touchend",
      (e) => {
        this.isSeeking = false
        this.hideSeekIndicator()
      },
      { passive: true },
    )
  }

  setupSkipButtons() {
    if (!this.intro && !this.outro) return

    let introSkipTimeout = null
    let outroSkipTimeout = null

    this.player.on("timeupdate", () => {
      const currentTime = this.player.currentTime()

      // Show/hide intro skip button
      if (this.intro && currentTime >= this.intro.start && currentTime <= this.intro.end) {
        this.skipIntroBtn.style.display = "block"
        this.skipIntroBtn.classList.add("show")

        if (this.settings.skipIntro && !introSkipTimeout) {
          introSkipTimeout = setTimeout(() => {
            if (this.player.currentTime() >= this.intro.start && this.player.currentTime() <= this.intro.end) {
              this.player.currentTime(this.intro.end)
              this.showControlIndicator("auto-skip", "Intro skipped")
              console.log("[v0] Auto-skipped intro")
            }
          }, 100)
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
            if (this.player.currentTime() >= this.outro.start && this.player.currentTime() <= this.outro.end) {
              this.player.currentTime(this.outro.end)
              this.showControlIndicator("auto-skip", "Outro skipped")
              console.log("[v0] Auto-skipped outro")
            }
          }, 100)
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
        this.player.currentTime(this.intro.end)
        if (introSkipTimeout) {
          clearTimeout(introSkipTimeout)
          introSkipTimeout = null
        }
        this.showControlIndicator("skip", "Intro skipped")
      }
    })

    this.skipOutroBtn.addEventListener("click", () => {
      if (this.outro) {
        this.player.currentTime(this.outro.end)
        if (outroSkipTimeout) {
          clearTimeout(outroSkipTimeout)
          outroSkipTimeout = null
        }
        this.showControlIndicator("skip", "Outro skipped")
      }
    })
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
    if (this.player.paused()) {
      this.player.play()
      this.showControlIndicator("play")
    } else {
      this.player.pause()
      this.showControlIndicator("pause")
    }
  }

  toggleFullscreen() {
    if (this.player.isFullscreen()) {
      this.player.exitFullscreen()
    } else {
      this.player.requestFullscreen()
    }
  }

  skipForward(seconds) {
    const newTime = Math.min(this.player.duration(), this.player.currentTime() + seconds)
    this.player.currentTime(newTime)
    this.showControlIndicator("forward", seconds)
  }

  skipBackward(seconds) {
    const newTime = Math.max(0, this.player.currentTime() - seconds)
    this.player.currentTime(newTime)
    this.showControlIndicator("backward", seconds)
  }

  adjustVolume(delta) {
    const newVolume = Math.max(0, Math.min(1, this.player.volume() + delta))
    this.player.volume(newVolume)
    this.showControlIndicator("volume", Math.round(newVolume * 100))
  }

  toggleMute() {
    this.player.muted(!this.player.muted())
    this.showControlIndicator(this.player.muted() ? "muted" : "unmuted")
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
    return (
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
      (navigator.maxTouchPoints && navigator.maxTouchPoints > 2 && /MacIntel/.test(navigator.platform))
    )
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

    this.player.el().parentElement.appendChild(errorDiv)

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (errorDiv.parentElement) {
        errorDiv.remove()
      }
    }, 5000)
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
    const oldSettings = { ...this.settings }
    this.settings = { ...this.settings, ...newSettings }
    this.saveSettings()

    // Reapply subtitle styling with new settings
    this.applySubtitleStyling()

    // Update subtitle visibility if language preference changed
    if (
      newSettings.preferredLanguage ||
      newSettings.subtitleLanguage !== oldSettings.subtitleLanguage ||
      newSettings.forceSubtitlesOff !== oldSettings.forceSubtitlesOff
    ) {
      this.currentLanguage = newSettings.preferredLanguage || this.currentLanguage
      this.updateSubtitleVisibility()
    }

    console.log(`[v0] Updated settings:`, this.settings)
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
