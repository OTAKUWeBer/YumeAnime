// Carousel functionality for spotlight section
class SpotlightCarousel {
  constructor(totalSlides) {
    this.currentSlide = 0
    this.totalSlides = totalSlides
    this.autoSlideInterval = null
    this.init()
  }

  init() {
    this.startAutoSlide()
    this.setupEventListeners()
  }

  showSlide(index) {
    const slides = document.querySelectorAll(".spotlight-slide")
    const indicators = document.querySelectorAll(".indicator")

    slides.forEach((slide, i) => {
      slide.classList.toggle("active", i === index)
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
  }

  nextSlide() {
    this.currentSlide = (this.currentSlide + 1) % this.totalSlides
    this.showSlide(this.currentSlide)
  }

  previousSlide() {
    this.currentSlide = (this.currentSlide - 1 + this.totalSlides) % this.totalSlides
    this.showSlide(this.currentSlide)
  }

  goToSlide(index) {
    this.currentSlide = index
    this.showSlide(this.currentSlide)
  }

  startAutoSlide() {
    this.autoSlideInterval = setInterval(() => this.nextSlide(), 5000)
  }

  stopAutoSlide() {
    clearInterval(this.autoSlideInterval)
  }

  setupEventListeners() {
    const carousel = document.getElementById("spotlight-carousel")
    if (carousel) {
      carousel.addEventListener("mouseenter", () => this.stopAutoSlide())
      carousel.addEventListener("mouseleave", () => this.startAutoSlide())
      
      // Touch/Swipe support for mobile
      let touchStartX = 0
      let touchEndX = 0
      
      carousel.addEventListener("touchstart", (e) => {
        touchStartX = e.changedTouches[0].screenX
        this.stopAutoSlide()
      }, false)
      
      carousel.addEventListener("touchend", (e) => {
        touchEndX = e.changedTouches[0].screenX
        this.handleSwipe()
        this.startAutoSlide()
      }, false)
    }
  }

  handleSwipe() {
    const swipeThreshold = 50
    const diff = touchStartX - touchEndX
    
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
