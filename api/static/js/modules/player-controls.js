export class PlayerControls {
  constructor(player, player2) {
    this.player = player
    this.player2 = player2 // Reference to VideoJSPlayer instance for methods
    this.keyboardEnabled = true
  }

  setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      if (!this.keyboardEnabled) return
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
      }
    })
  }

  setupMobileFeatures() {
    if (!this.player2.isMobileDevice()) return

    const videoContainer = this.player.el().parentElement
    videoContainer.addEventListener("dblclick", () => {
      this.togglePlayPause()
    })

    videoContainer.addEventListener("click", (e) => {
      if (e.detail === 3) {
        this.toggleFullscreen()
      }
    })
  }

  setupTouchGestures() {
    const videoContainer = this.player.el().parentElement
    let touchStartX = 0
    let touchStartTime = 0

    videoContainer.addEventListener(
      "touchstart",
      (e) => {
        touchStartX = e.touches[0].clientX
        touchStartTime = Date.now()
      },
      { passive: true },
    )

    videoContainer.addEventListener(
      "touchmove",
      (e) => {
        if (!touchStartX) return
        const deltaX = e.touches[0].clientX - touchStartX
        const containerWidth = videoContainer.offsetWidth
        if (Math.abs(deltaX) > 30) {
          const seekAmount = (deltaX / containerWidth) * this.player.duration()
          const newTime = Math.max(0, Math.min(this.player.duration(), this.player.currentTime() + seekAmount))
          this.player.currentTime(newTime)
          this.player2.showSeekIndicator(seekAmount > 0 ? "forward" : "backward", Math.abs(seekAmount))
        }
      },
      { passive: true },
    )

    videoContainer.addEventListener(
      "touchend",
      () => {
        touchStartX = 0
        this.player2.hideSeekIndicator()
      },
      { passive: true },
    )
  }

  togglePlayPause() {
    if (this.player.paused()) {
      this.player.play()
      this.player2.showControlIndicator("play")
    } else {
      this.player.pause()
      this.player2.showControlIndicator("pause")
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
    this.player2.showControlIndicator("forward", seconds)
  }

  skipBackward(seconds) {
    const newTime = Math.max(0, this.player.currentTime() - seconds)
    this.player.currentTime(newTime)
    this.player2.showControlIndicator("backward", seconds)
  }

  adjustVolume(delta) {
    const newVolume = Math.max(0, Math.min(1, this.player.volume() + delta))
    this.player.volume(newVolume)
    this.player2.showControlIndicator("volume", Math.round(newVolume * 100))
  }

  toggleMute() {
    this.player.muted(!this.player.muted())
    this.player2.showControlIndicator(this.player.muted() ? "muted" : "unmuted")
  }
}
