// Carousel functionality for spotlight section
class SpotlightCarousel {
  constructor(totalSlides) {
    this.currentSlide = 0
    this.totalSlides = totalSlides
    this.autoSlideInterval = null
    this.touchStartX = 0
    this.touchEndX = 0
    this.isAnimating = false
    this.init()
  }

  init() {
    this.startAutoSlide()
    this.setupEventListeners()
    this.connectNavigationButtons()
  }

  showSlide(index, direction = "next") {
    if (this.isAnimating || this.totalSlides === 0) return
    
    this.isAnimating = true
    const slides = document.querySelectorAll(".spotlight-slide")
    const indicators = document.querySelectorAll(".indicator")

    slides.forEach((slide, i) => {
      if (i === index) {
        slide.classList.remove("slide-left", "slide-right")
        slide.classList.add("active", direction === "next" ? "slide-right" : "slide-left")
        setTimeout(() => {
          slide.classList.remove("slide-left", "slide-right")
        }, 600)
      } else {
        slide.classList.remove("active", "slide-left", "slide-right")
      }
    })

    indicators.forEach((indicator, i) => {
      if (i === index) {
        indicator.classList.remove("bg-white/30")
        indicator.classList.add("bg-purple-400")
      } else {
        indicator.classList.remove("bg-purple-400")
        indicator.classList.add("bg-white/30")
      }
    })

    setTimeout(() => {
      this.isAnimating = false
    }, 600)
  }

  nextSlide() {
    this.currentSlide = (this.currentSlide + 1) % this.totalSlides
    this.showSlide(this.currentSlide, "next")
  }

  previousSlide() {
    this.currentSlide = (this.currentSlide - 1 + this.totalSlides) % this.totalSlides
    this.showSlide(this.currentSlide, "prev")
  }

  goToSlide(index) {
    if (index === this.currentSlide) return
    const direction = index > this.currentSlide ? "next" : "prev"
    this.currentSlide = index
    this.showSlide(this.currentSlide, direction)
  }

  startAutoSlide() {
    this.autoSlideInterval = setInterval(() => this.nextSlide(), 5000)
  }

  stopAutoSlide() {
    clearInterval(this.autoSlideInterval)
  }

  connectNavigationButtons() {
    const prevBtn = document.getElementById("spotlight-prev")
    const nextBtn = document.getElementById("spotlight-next")

    if (prevBtn) {
      prevBtn.addEventListener("click", (e) => {
        e.stopPropagation()
        this.stopAutoSlide()
        this.previousSlide()
        this.startAutoSlide()
      })
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", (e) => {
        e.stopPropagation()
        this.stopAutoSlide()
        this.nextSlide()
        this.startAutoSlide()
      })
    }
  }

  setupEventListeners() {
    const carousel = document.getElementById("spotlight-carousel")
    if (carousel) {
      carousel.addEventListener("mouseenter", () => this.stopAutoSlide())
      carousel.addEventListener("mouseleave", () => this.startAutoSlide())
      
      // Touch/Swipe support for mobile
      carousel.addEventListener("touchstart", (e) => {
        this.touchStartX = e.changedTouches[0].screenX
        this.stopAutoSlide()
      }, false)
      
      carousel.addEventListener("touchend", (e) => {
        this.touchEndX = e.changedTouches[0].screenX
        this.handleSwipe()
        this.startAutoSlide()
      }, false)

      // Mouse swipe support
      let mouseStartX = 0
      let isMouseDown = false

      carousel.addEventListener("mousedown", (e) => {
        mouseStartX = e.clientX
        isMouseDown = true
      })

      carousel.addEventListener("mouseup", (e) => {
        if (!isMouseDown) return
        isMouseDown = false
        const mouseEndX = e.clientX
        const swipeThreshold = 50
        const diff = mouseStartX - mouseEndX

        if (Math.abs(diff) > swipeThreshold) {
          if (diff > 0) {
            this.nextSlide()
          } else {
            this.previousSlide()
          }
        }
      })

      carousel.addEventListener("mouseleave", () => {
        isMouseDown = false
      })
    }
  }

  handleSwipe() {
    const swipeThreshold = 50
    const diff = this.touchStartX - this.touchEndX
    
    if (Math.abs(diff) > swipeThreshold) {
      if (diff > 0) {
        // Swiped left, go to next slide
        this.nextSlide()
      } else {
        // Swiped right, go to previous slide
        this.previousSlide()
      }
    }
  }
}

// Global functions for template compatibility
function nextSlide() {
  if (window.spotlightCarousel) {
    window.spotlightCarousel.nextSlide()
  }
}

function previousSlide() {
  if (window.spotlightCarousel) {
    window.spotlightCarousel.previousSlide()
  }
}

function goToSlide(index) {
  if (window.spotlightCarousel) {
    window.spotlightCarousel.goToSlide(index)
  }
}
