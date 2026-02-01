/**
 * Settings Page JavaScript
 * Handles basic settings functionality for playback preferences
 */

/**
 * Settings Page JavaScript
 * Handles basic settings functionality for playback preferences
 */
class SettingsManager {
  constructor() {
    this.currentUser = null
    this.settings = this.loadSettings()
    this.init()
  }

  init() {
    this.loadUserSession()
    this.loadSettingsFromStorage()
    this.setupEventListeners()
  }

  async loadUserSession() {
    try {
      const response = await fetch("/api/me", {
        method: "GET",
        credentials: "same-origin",
      })
      if (response.ok) {
        const userData = await response.json()
        if (userData && userData.username) {
          this.currentUser = userData
          this.updateAniListStatus()
        }
      }
    } catch (error) {
      console.error("Error loading user session:", error)
    }
  }

  loadSettings() {
    try {
      const saved = localStorage.getItem("yumeAnimeSettings")
      return saved ? JSON.parse(saved) : this.getDefaultSettings()
    } catch (error) {
      console.error("Error loading settings:", error)
      return this.getDefaultSettings()
    }
  }

  getDefaultSettings() {
    return {
      // Playback settings
      autoplayNext: true,
      skipIntro: true,
      preferredLanguage: "sub",
    }
  }

  saveSettings() {
    try {
      localStorage.setItem("yumeAnimeSettings", JSON.stringify(this.settings))
      this.showNotification("Settings saved successfully!", "success")
    } catch (error) {
      console.error("Error saving settings:", error)
      this.showNotification("Failed to save settings", "error")
    }
  }

  loadSettingsFromStorage() {
    // Playback settings
    document.getElementById("autoplay-next").checked = this.settings.autoplayNext
    document.getElementById("skip-intro").checked = this.settings.skipIntro
    document.getElementById("preferred-language").value = this.settings.preferredLanguage
  }

  setupEventListeners() {
    // Auto-save on setting changes
    const settingInputs = document.querySelectorAll('input[type="checkbox"], select')
    settingInputs.forEach((input) => {
      input.addEventListener("change", () => {
        this.updateSettingsFromForm()
        this.saveSettings() // Now only saves when user actually changes something
      })
    })

    // Specific handler for autoplay next setting (this is redundant with the above, but keeping for consistency)
    const autoplayToggle = document.getElementById("autoplay-next")
    if (autoplayToggle) {
      autoplayToggle.addEventListener("change", (e) => {
        this.settings.autoplayNext = e.target.checked
        console.log("Auto-play next episode setting updated:", e.target.checked)
      })
    }
  }

  updateSettingsFromForm() {
    // Playback settings
    this.settings.autoplayNext = document.getElementById("autoplay-next").checked
    this.settings.skipIntro = document.getElementById("skip-intro").checked
    this.settings.preferredLanguage = document.getElementById("preferred-language").value
  }

  updateAniListStatus() {
    const statusContainer = document.getElementById("anilist-status")
    const connectBtn = document.getElementById("connect-anilist-btn")
    const syncBtn = document.getElementById("sync-anilist-btn")
    const disconnectBtn = document.getElementById("disconnect-anilist-btn")

    const isConnected = this.currentUser && this.currentUser.anilist_authenticated

    if (isConnected) {
      // Connected state
      const anilistStats = this.currentUser.anilist_stats || {}
      const statsText = anilistStats.anime_count
        ? `${anilistStats.anime_count} anime • ${Math.round(anilistStats.minutes_watched / 60) || 0} hours watched`
        : "Stats not available"

      statusContainer.innerHTML = `
                <div class="flex items-center justify-between p-4 rounded-lg anilist-connected">
                    <div class="flex items-center">
                        <div class="w-3 h-3 bg-green-400 rounded-full mr-3 animate-pulse"></div>
                        <div>
                            <div class="flex items-center gap-2">
                                <span class="font-medium">Connected</span>
                                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M6.361 2.943 0 21.056h4.06l1.077-3.133h6.875l1.077 3.133H17.15L10.789 2.943zm1.77 5.392 2.18 6.336H5.951zm10.365 9.794V8.113c3.02.501 4.473 2.273 4.473 4.728 0 2.456-1.453 4.227-4.473 4.728z"/>
                                </svg>
                            </div>
${
  this.currentUser.anilist_id
    ? `
                                <p class="text-xs opacity-80">ID: ${this.currentUser.anilist_id}</p>
                                <p class="text-xs opacity-70">${statsText}</p>
`
    : ""
}
                        </div>
                    </div>
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                </div>
`
      connectBtn.classList.add("hidden")
      syncBtn.classList.remove("hidden")
      disconnectBtn.classList.remove("hidden")

      // Show auto-sync info
      const autoSyncInfo = document.getElementById("auto-sync-info")
      if (autoSyncInfo) {
        autoSyncInfo.classList.remove("hidden")
      }
    } else {
      // Disconnected state
      statusContainer.innerHTML = `
                <div class="flex items-center justify-between p-4 rounded-lg anilist-disconnected">
                    <div class="flex items-center">
                        <div class="w-3 h-3 bg-gray-500 rounded-full mr-3"></div>
                        <div>
                            <span class="font-medium">Not Connected</span>
                            <p class="text-xs opacity-70">Connect to sync your watchlist</p>
                        </div>
                    </div>
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </div>
`
      connectBtn.classList.remove("hidden")
      syncBtn.classList.add("hidden")
      disconnectBtn.classList.add("hidden")

      // Hide auto-sync info
      const autoSyncInfo = document.getElementById("auto-sync-info")
      if (autoSyncInfo) {
        autoSyncInfo.classList.add("hidden")
      }
    }
  }

  async connectAniList() {
    if (!this.currentUser) {
      this.showNotification("Please log in first to connect your AniList account.", "error")
      return
    }

    // Check if already connected
    if (this.currentUser.anilist_authenticated) {
      this.showNotification("Your AniList account is already connected.", "info")
      return
    }

    // Redirect to AniList OAuth connect endpoint
    window.location.href = "/auth/anilist/connect"
  }

  async syncAniList() {
    if (!this.currentUser || !this.currentUser.anilist_authenticated) {
      this.showNotification("Please connect your AniList account first.", "error")
      return
    }

    this.setSyncButtonLoading(true)

    try {
      const response = await fetch("/api/anilist/sync-anilist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
      })

      const data = await response.json()

      if (data.success) {
        this.showNotification(
          `Sync completed successfully! Added ${data.synced_count} new entries, skipped ${data.skipped_count} duplicates.${data.failed_count > 0 ? ` ${data.failed_count} entries could not be matched` : ""}`,
          "success",
        )
      } else {
        this.showNotification(data.message || "Sync failed. Please try again.", "error")
      }
    } catch (error) {
      console.error("Sync error:", error)
      this.showNotification("Network error occurred. Please try again.", "error")
    } finally {
      this.setSyncButtonLoading(false)
    }
  }

  async disconnectAniList() {
    if (
      !confirm("Are you sure you want to disconnect your AniList account? This will not remove your local watchlist.")
    ) {
      return
    }

    try {
      const response = await fetch("/auth/anilist/unlink", {
        method: "POST",
        credentials: "same-origin",
      })

      const data = await response.json()

      if (data.success) {
        this.currentUser.anilist_authenticated = false
        this.updateAniListStatus()
        this.showNotification("AniList account disconnected successfully.", "success")
      } else {
        this.showNotification(data.message || "Failed to disconnect AniList account.", "error")
      }
    } catch (error) {
      console.error("Disconnect error:", error)
      this.showNotification("Network error occurred. Please try again.", "error")
    }
  }

  setSyncButtonLoading(loading) {
    const button = document.getElementById("sync-anilist-btn")
    const text = document.getElementById("sync-btn-text")
    const spinner = document.getElementById("sync-spinner")

    if (button && text && spinner) {
      button.disabled = loading
      if (loading) {
        text.classList.add("hidden")
        spinner.classList.remove("hidden")
      } else {
        text.classList.remove("hidden")
        spinner.classList.add("hidden")
      }
    }
  }

  // Password Change Modal Functions
  showPasswordModal() {
    const modal = document.getElementById("password-modal")
    if (modal) {
      modal.classList.remove("hidden")
      document.body.style.overflow = "hidden" // Prevent background scrolling
    }
  }

  hidePasswordModal() {
    const modal = document.getElementById("password-modal")
    if (modal) {
      modal.classList.add("hidden")
      document.body.style.overflow = "" // Restore scrolling
      // Clear form fields
      document.getElementById("current-password").value = ""
      document.getElementById("new-password").value = ""
      document.getElementById("confirm-password").value = ""
      this.hidePasswordMessage()
    }
  }

  setPasswordChangeLoading(loading) {
    const button = document.querySelector('#password-modal button[onclick="submitPasswordChange()"]')
    const text = document.getElementById("password-change-text")
    const spinner = document.getElementById("password-change-spinner")

    if (button && text && spinner) {
      button.disabled = loading
      if (loading) {
        text.classList.add("hidden")
        spinner.classList.remove("hidden")
      } else {
        text.classList.remove("hidden")
        spinner.classList.add("hidden")
      }
    }
  }

  showPasswordMessage(message, type = "error") {
    const messageEl = document.getElementById("password-change-message")
    if (messageEl) {
      messageEl.textContent = message
      messageEl.className = `mt-4 text-center text-sm ${type === "success" ? "text-green-400" : "text-red-400"}`
      messageEl.classList.remove("hidden")
    }
  }

  hidePasswordMessage() {
    const messageEl = document.getElementById("password-change-message")
    if (messageEl) {
      messageEl.classList.add("hidden")
    }
  }

  async submitPasswordChange() {
    const currentPassword = document.getElementById("current-password").value
    const newPassword = document.getElementById("new-password").value
    const confirmPassword = document.getElementById("confirm-password").value

    // Validation
    if (!currentPassword || !newPassword || !confirmPassword) {
      this.showPasswordMessage("Please fill in all fields")
      return
    }

    if (newPassword !== confirmPassword) {
      this.showPasswordMessage("New passwords do not match")
      return
    }

    if (newPassword.length < 6) {
      this.showPasswordMessage("New password must be at least 6 characters long")
      return
    }

    const turnstileToken = document.querySelector('#password-modal [name="cf-turnstile-response"]')?.value
    if (!turnstileToken) {
      this.showPasswordMessage("Please complete the security verification")
      return
    }

    this.setPasswordChangeLoading(true)
    this.hidePasswordMessage()

    try {
      const response = await fetch("/api/change-password", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          cf_turnstile_response: turnstileToken,
        }),
      })

      const data = await response.json()

      if (data.success) {
        this.showPasswordMessage("Password changed successfully!", "success")
        setTimeout(() => {
          this.hidePasswordModal()
          this.showNotification("Password changed successfully!", "success")
        }, 1500)
      } else {
        this.showPasswordMessage(data.message || "Failed to change password")
      }
    } catch (error) {
      console.error("Password change error:", error)
      this.showPasswordMessage("Network error occurred. Please try again.")
    } finally {
      this.setPasswordChangeLoading(false)
    }
  }

  clearCache() {
    try {
      // Clear various caches
      localStorage.removeItem("animeWatchData")
      localStorage.removeItem("searchCache")
      localStorage.removeItem("animeInfoCache")

      // Clear session storage
      sessionStorage.clear()

      this.showNotification("Cache cleared successfully!", "success")
    } catch (error) {
      console.error("Cache clear error:", error)
      this.showNotification("Failed to clear cache.", "error")
    }
  }

  resetSettings() {
    if (!confirm("Are you sure you want to reset all settings to default? This cannot be undone.")) {
      return
    }

    this.settings = this.getDefaultSettings()
    this.loadSettingsFromStorage()
    this.applySettings()
    this.showNotification("Settings reset to defaults!", "success")
  }

  saveAllSettings() {
    this.updateSettingsFromForm()
    this.applySettings()
    this.showNotification("All settings saved successfully!", "success")
  }

  showNotification(message, type = "info") {
      // Remove existing notification
      const existingNotification = document.getElementById("settings-notification")
      if (existingNotification) {
        existingNotification.remove()
      }

      const notification = document.createElement("div")
      notification.id = "settings-notification"
      notification.className = `fixed top-6 right-6 z-50 px-6 py-4 rounded-xl shadow-2xl font-semibold transition-all duration-300 transform translate-x-full border backdrop-blur-sm flex items-center gap-3 ${
        type === "success"
          ? "bg-gradient-to-r from-green-600 to-green-700 text-white border-green-500/30"
          : type === "error"
            ? "bg-gradient-to-r from-red-600 to-red-700 text-white border-red-500/30"
            : type === "warning"
              ? "bg-gradient-to-r from-yellow-600 to-yellow-700 text-white border-yellow-500/30"
              : "bg-gradient-to-r from-blue-600 to-blue-700 text-white border-blue-500/30"
      }`
      
      // Create message span
      const messageSpan = document.createElement("span")
      messageSpan.textContent = message
      notification.appendChild(messageSpan)
      
      // Create close button
      const closeButton = document.createElement("button")
      closeButton.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      `
      closeButton.className = "ml-2 hover:opacity-70 transition-opacity focus:outline-none"
      closeButton.onclick = () => {
        notification.style.transform = "translateX(100%) scale(0.95)"
        setTimeout(() => {
          if (notification.parentNode) {
            notification.remove()
          }
        }, 300)
      }
      notification.appendChild(closeButton)

      document.body.appendChild(notification)

      // Animate in
      setTimeout(() => {
        notification.classList.remove("translate-x-full")
        notification.style.transform = "translateX(0) scale(1)"
      }, 100)

      // Auto remove after 4 seconds
      setTimeout(() => {
        notification.style.transform = "translateX(100%) scale(0.95)"
        setTimeout(() => {
          if (notification.parentNode) {
            notification.remove()
          }
        }, 300)
      }, 4000)
    }
}

// Global functions for template compatibility
function connectAniList() {
  if (window.settingsManager) {
    window.settingsManager.connectAniList()
  }
}

function syncAniList() {
  if (window.settingsManager) {
    window.settingsManager.syncAniList()
  }
}

function disconnectAniList() {
  if (window.settingsManager) {
    window.settingsManager.disconnectAniList()
  }
}

function clearCache() {
  if (window.settingsManager) {
    window.settingsManager.clearCache()
  }
}

function resetSettings() {
  if (window.settingsManager) {
    window.settingsManager.resetSettings()
  }
}

function saveAllSettings() {
  if (window.settingsManager) {
    window.settingsManager.saveAllSettings()
  }
}

// Password Modal Functions
function changePassword() {
  if (window.settingsManager) {
    window.settingsManager.showPasswordModal()
  }
}

function closePasswordModal() {
  if (window.settingsManager) {
    window.settingsManager.hidePasswordModal()
  }
}

function submitPasswordChange() {
  if (window.settingsManager) {
    window.settingsManager.submitPasswordChange()
  }
}

// Initialize settings manager when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  window.settingsManager = new SettingsManager()

  // Close modal when clicking outside of it
  const modal = document.getElementById("password-modal")
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        closePasswordModal()
      }
    })
  }

  // Close modal with Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !document.getElementById("password-modal").classList.contains("hidden")) {
      closePasswordModal()
    }
  })
})
