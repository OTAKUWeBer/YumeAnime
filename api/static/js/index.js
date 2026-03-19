// Spotlight Carousel using native scroll snap
    const carousel = document.getElementById('spotlight-carousel');
    if (carousel) {
        const slides = carousel.querySelectorAll('.spotlight-slide');
        const prevBtn = document.getElementById('spotlight-prev');
        const nextBtn = document.getElementById('spotlight-next');
        let autoplayInterval;

        function getIndex() {
            let closestIndex = 0;
            let minDiff = Infinity;
            slides.forEach((slide, i) => {
                const diff = Math.abs(carousel.scrollLeft - slide.offsetLeft);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestIndex = i;
                }
            });
            return closestIndex;
        }

        function showSlide(index) {
            if (index < 0) index = slides.length - 1;
            if (index >= slides.length) index = 0;
            const slide = slides[index];
            carousel.scrollTo({
                left: slide.offsetLeft,
                behavior: 'smooth'
            });
        }

        function startAutoplay() {
            stopAutoplay();
            autoplayInterval = setInterval(() => {
                showSlide(getIndex() + 1);
            }, 6000); // 6 seconds per slide
        }

        function stopAutoplay() {
            clearInterval(autoplayInterval);
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', (e) => {
                e.preventDefault();
                showSlide(getIndex() + 1);
                startAutoplay(); // Restart the timer
            });
        }
        
        if (prevBtn) {
            prevBtn.addEventListener('click', (e) => {
                e.preventDefault();
                showSlide(getIndex() - 1);
                startAutoplay(); // Restart the timer
            });
        }

        // Mouse Drag to Scroll
        let isDown = false;
        let startX;
        let scrollLeft;
        let dragged = false;

        // Prevent native HTML drag on images and links so our JS drag works
        carousel.querySelectorAll('a, img').forEach(el => {
            el.addEventListener('dragstart', e => e.preventDefault());
        });

        carousel.addEventListener('mousedown', (e) => {
            isDown = true;
            dragged = false;
            // We do NOT add the 'dragging' class here yet, to allow clicks to register
            startX = e.pageX - carousel.offsetLeft;
            scrollLeft = carousel.scrollLeft;
            stopAutoplay();
        });

        const stopDragging = () => {
            if (!isDown) return;
            isDown = false;
            carousel.classList.remove('dragging');
            if (dragged) showSlide(getIndex());
            startAutoplay();
        };

        // Window level events are safer for mouseup and mouseleave out of bounds
        window.addEventListener('mouseup', stopDragging);
        carousel.addEventListener('mouseleave', stopDragging);

        carousel.addEventListener('mousemove', (e) => {
            if (!isDown) return;
            
            const x = e.pageX - carousel.offsetLeft;
            // Only consider it a drag if moved more than 5 pixels
            if (Math.abs(x - startX) > 5) {
                dragged = true;
                carousel.classList.add('dragging');
            }
            
            if (dragged) {
                e.preventDefault();
                const walk = (x - startX) * 1.5; // Drag speed multiplier
                carousel.scrollLeft = scrollLeft - walk;
            }
        });

        // Touch swipe support (Native scrolling handles the drag, we just need to restart autoplay)
        carousel.addEventListener('touchstart', stopAutoplay, {passive: true});
        carousel.addEventListener('touchend', () => { setTimeout(startAutoplay, 2000); }, {passive: true});
        
        // Pause ONLY momentarily on scroll wheel
        let scrollTimeout;
        carousel.addEventListener('wheel', () => {
             stopAutoplay();
             clearTimeout(scrollTimeout);
             scrollTimeout = setTimeout(startAutoplay, 2000);
        }, {passive: true});

        // Use IntersectionObserver to apply the 'active' class for the Ken Burns effect
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('active');
                } else {
                    entry.target.classList.remove('active');
                }
            });
        }, { root: carousel, threshold: 0.5 });
        
        slides.forEach(slide => observer.observe(slide));

        // Start autoplay initially
        startAutoplay();
    }
