// Loading Screen Functionality
class LoadingScreen {
  constructor() {
    this.loadingScreen = null
    this.init()
  }

  init() {
    document.addEventListener("DOMContentLoaded", () => {
      this.loadingScreen = document.getElementById("loading-screen")
      this.setupEventListeners()
    })
  }

  setupEventListeners() {
    if (!this.loadingScreen) return

    window.addEventListener("load", () => {
      setTimeout(() => {
        this.hide()
      }, 100)
    })

    setTimeout(() => {
      this.hide()
    }, 1500)
  }

  show() {
    if (this.loadingScreen) {
      this.loadingScreen.classList.remove("hidden")
    }
  }

  hide() {
    if (this.loadingScreen) {
      this.loadingScreen.classList.add("hidden")
    }
  }

  updateText(text) {
    const textElement = this.loadingScreen?.querySelector(".loading-text")
    if (textElement) {
      textElement.textContent = text
    }
  }
}

// Initialize loading screen
const loadingScreen = new LoadingScreen()
