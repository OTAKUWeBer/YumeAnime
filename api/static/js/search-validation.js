// Search form validation and error handling
class SearchValidator {
  constructor() {
    this.searchForm = document.getElementById("search-form")
    this.searchInput = document.getElementById("search-input")
    this.searchError = document.getElementById("search-error")
    this.init()
  }

  init() {
    if (this.searchForm && this.searchInput) {
      this.setupEventListeners()
    }
  }

  setupEventListeners() {
    this.searchForm.addEventListener("submit", (e) => this.handleSubmit(e))
    this.searchInput.addEventListener("input", () => this.handleInput())
  }

  handleSubmit(e) {
    const value = this.searchInput.value.trim()
    if (!value) {
      e.preventDefault()
      this.showSearchError("Please enter a search query.")
      return false
    }
  }

  handleInput() {
    if (this.searchInput.value.trim()) {
      this.clearSearchError()
    }
  }

  showSearchError(msg) {
    if (this.searchError) {
      this.searchError.textContent = msg
      this.searchError.classList.remove("hidden")
    }

    this.searchInput.classList.add("ring-2", "ring-red-400", "border-red-400")

    // Shake animation
    this.searchInput.animate(
      [
        { transform: "translateX(0)" },
        { transform: "translateX(-6px)" },
        { transform: "translateX(6px)" },
        { transform: "translateX(0)" },
      ],
      { duration: 300, iterations: 1 },
    )

    this.searchInput.focus()
  }

  clearSearchError() {
    if (this.searchError) {
      this.searchError.classList.add("hidden")
    }
    this.searchInput.classList.remove("ring-2", "ring-red-400", "border-red-400")
  }
}
