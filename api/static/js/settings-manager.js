class SettingsManager {
  constructor(player) {
    this.player = player
    this.settingsPanel = null
    this.settingsToggle = null
    this.init()
  }

  init() {
    this.settingsPanel = document.getElementById("settingsPanel")
    this.settingsToggle = document.getElementById("settingsToggle")

    if (!this.settingsPanel || !this.settingsToggle) {
      console.warn("[v0] Settings panel elements not found")
      return
    }

    this.setupEventListeners()
    this.loadSettingsToUI()
  }

  setupEventListeners() {
    // Toggle settings panel
    this.settingsToggle.addEventListener("click", () => {
      this.toggleSettingsPanel()
    })

    // Close panel when clicking outside
    document.addEventListener("click", (e) => {
      if (!this.settingsPanel.contains(e.target) && !this.settingsToggle.contains(e.target)) {
        this.hideSettingsPanel()
      }
    })

    // Settings controls
    const skipIntroToggle = document.getElementById("skipIntroToggle")
    const autoSkipIntroToggle = document.getElementById("autoSkipIntroToggle")
    const autoSkipOutroToggle = document.getElementById("autoSkipOutroToggle")
    const autoplayNextToggle = document.getElementById("autoplayNextToggle")
    const volumeSlider = document.getElementById("volumeSlider")

    if (skipIntroToggle) {
      skipIntroToggle.addEventListener("change", (e) => {
        this.player.updateSetting("skipIntro", e.target.checked)
      })
    }

    if (autoSkipIntroToggle) {
      autoSkipIntroToggle.addEventListener("change", (e) => {
        this.player.updateSetting("autoSkipIntro", e.target.checked)
      })
    }

    if (autoSkipOutroToggle) {
      autoSkipOutroToggle.addEventListener("change", (e) => {
        this.player.updateSetting("autoSkipOutro", e.target.checked)
      })
    }

    if (autoplayNextToggle) {
      autoplayNextToggle.addEventListener("change", (e) => {
        this.player.updateSetting("autoplayNext", e.target.checked)
      })
    }

    if (volumeSlider) {
      volumeSlider.addEventListener("input", (e) => {
        const volume = Number.parseInt(e.target.value)
        this.player.updateSetting("defaultVolume", volume)
        this.player.video.volume = volume / 100
      })
    }
  }

  loadSettingsToUI() {
    const settings = this.player.settings

    const skipIntroToggle = document.getElementById("skipIntroToggle")
    const autoSkipIntroToggle = document.getElementById("autoSkipIntroToggle")
    const autoSkipOutroToggle = document.getElementById("autoSkipOutroToggle")
    const autoplayNextToggle = document.getElementById("autoplayNextToggle")
    const volumeSlider = document.getElementById("volumeSlider")

    if (skipIntroToggle) skipIntroToggle.checked = settings.skipIntro
    if (autoSkipIntroToggle) autoSkipIntroToggle.checked = settings.autoSkipIntro
    if (autoSkipOutroToggle) autoSkipOutroToggle.checked = settings.autoSkipOutro
    if (autoplayNextToggle) autoplayNextToggle.checked = settings.autoplayNext
    if (volumeSlider) volumeSlider.value = settings.defaultVolume
  }

  toggleSettingsPanel() {
    if (this.settingsPanel.classList.contains("hidden")) {
      this.showSettingsPanel()
    } else {
      this.hideSettingsPanel()
    }
  }

  showSettingsPanel() {
    this.settingsPanel.classList.remove("hidden")
    this.settingsPanel.style.opacity = "0"
    this.settingsPanel.style.transform = "translateY(-10px)"

    requestAnimationFrame(() => {
      this.settingsPanel.style.transition = "opacity 0.2s ease, transform 0.2s ease"
      this.settingsPanel.style.opacity = "1"
      this.settingsPanel.style.transform = "translateY(0)"
    })
  }

  hideSettingsPanel() {
    this.settingsPanel.style.transition = "opacity 0.2s ease, transform 0.2s ease"
    this.settingsPanel.style.opacity = "0"
    this.settingsPanel.style.transform = "translateY(-10px)"

    setTimeout(() => {
      this.settingsPanel.classList.add("hidden")
    }, 200)
  }
}

// Initialize settings manager when player is ready
window.initializeSettingsManager = (player) => new SettingsManager(player)
