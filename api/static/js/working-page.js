// Working page interactive elements
class WorkingPageManager {
  constructor() {
    this.init()
  }

  init() {
    document.addEventListener("DOMContentLoaded", () => {
      this.setupEmailValidation()
    })
  }

  setupEmailValidation() {
    const emailInput = document.querySelector('input[type="email"]')
    const notifyButton = document.querySelector("button")

    if (!emailInput || !notifyButton) return

    emailInput.addEventListener("focus", function () {
      this.parentElement.classList.add("scale-105")
    })

    emailInput.addEventListener("blur", function () {
      this.parentElement.classList.remove("scale-105")
    })

    notifyButton.addEventListener("click", (e) => {
      this.handleNotifyClick(e, emailInput, notifyButton)
    })
  }

  handleNotifyClick(e, emailInput, notifyButton) {
    e.preventDefault()
    const email = emailInput.value.trim()

    if (email && email.includes("@")) {
      // Success feedback
      notifyButton.textContent = "Thanks!"
      notifyButton.classList.remove("animate-bounce-slow")
      notifyButton.classList.add("bg-green-600")

      setTimeout(() => {
        notifyButton.textContent = "Notify Me"
        notifyButton.classList.add("animate-bounce-slow")
        notifyButton.classList.remove("bg-green-600")
        emailInput.value = ""
      }, 2000)
    } else {
      // Error feedback
      emailInput.classList.add("border-red-400", "ring-2", "ring-red-400")
      emailInput.placeholder = "Please enter a valid email"

      setTimeout(() => {
        emailInput.classList.remove("border-red-400", "ring-2", "ring-red-400")
        emailInput.placeholder = "Enter your email..."
      }, 2000)
    }
  }
}
