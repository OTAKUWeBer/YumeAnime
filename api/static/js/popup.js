document.addEventListener('DOMContentLoaded', () => {
    const popupOverlay = document.getElementById('welcome-popup');
    const closeXBtn = document.getElementById('welcome-popup-close-x');
    const closeBtn = document.getElementById('welcome-btn-close');
    const dontShowBtn = document.getElementById('welcome-btn-dont-show');
    
    // Change this version string when you want to show a NEW update to users!
    const currentUpdateVersion = 'v2'; 
    
    // Check user preferences
    const neverShowAgain = localStorage.getItem('yumezone_popup_never_show') === 'true';
    const dismissedCurrentVersion = localStorage.getItem(`yumezone_popup_dismissed_${currentUpdateVersion}`) === 'true';
    
    if (!neverShowAgain && !dismissedCurrentVersion && popupOverlay) {
        // Show after a small delay for smooth intro
        setTimeout(() => {
            popupOverlay.classList.remove('hidden');
            // Force reflow
            void popupOverlay.offsetWidth;
            popupOverlay.classList.add('active');
        }, 500);
    }
    
    const closePopup = () => {
        popupOverlay.classList.remove('active');
        setTimeout(() => {
            popupOverlay.classList.add('hidden');
        }, 300); // Matches CSS transition duration
    };

    const dismissForVersion = () => {
        // Marks THIS SPECIFIC update version as viewed/closed
        localStorage.setItem(`yumezone_popup_dismissed_${currentUpdateVersion}`, 'true');
        closePopup();
    };
    
    // Normal Close actions (X button, "Close" button, or clicking outside) 
    // will dismiss this update, but show future updates.
    if (closeXBtn) closeXBtn.addEventListener('click', dismissForVersion);
    if (closeBtn) closeBtn.addEventListener('click', dismissForVersion);
    if (popupOverlay) {
        popupOverlay.addEventListener('click', (e) => {
            if (e.target === popupOverlay) {
                dismissForVersion();
            }
        });
    }
    
    // "Do not show again" will permanently mute all future update popups
    if (dontShowBtn) {
        dontShowBtn.addEventListener('click', () => {
            localStorage.setItem('yumezone_popup_never_show', 'true');
            closePopup();
        });
    }
});
