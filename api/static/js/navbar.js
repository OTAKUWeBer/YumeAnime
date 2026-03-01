// Navigation functionality
class NavbarManager {
  constructor() {
    this.prevScrollPos = window.pageYOffset
    this.navbar = document.querySelector(".navbar")
    this.init()
  }

  init() {
    this.setupScrollHandler()
    this.setupMobileMenu()
  }

  setupScrollHandler() {
    window.addEventListener("scroll", () => {
      const currentScrollPos = window.pageYOffset

      if (this.navbar) {
        if (this.prevScrollPos > currentScrollPos) {
          this.navbar.style.top = "0"
        } else {
          this.navbar.style.top = "-100px"
        }
      }

      this.prevScrollPos = currentScrollPos
    })
  }

  setupMobileMenu() {
    // Mobile menu toggle functionality will be added here
    window.toggleMobileMenu = () => {
      const mobileMenu = document.getElementById("mobile-menu")
      const menuIcon = document.getElementById("menu-icon")
      const closeIcon = document.getElementById("close-icon")

      if (mobileMenu) mobileMenu.classList.toggle("hidden")
      if (menuIcon) menuIcon.classList.toggle("hidden")
      if (closeIcon) closeIcon.classList.toggle("hidden")
    }
  }
}
