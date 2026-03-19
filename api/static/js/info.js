document.addEventListener('DOMContentLoaded', () => {
                                const container = document.getElementById('next-ep-countdown');
                                if (!container) return;
                                const timestamp = parseInt(container.getAttribute('data-timestamp'), 10);
                                if (!timestamp) return;
                                const daysEl = container.querySelector('.days');
                                const hoursEl = container.querySelector('.hours');
                                const minutesEl = container.querySelector('.minutes');
                                const secondsEl = container.querySelector('.seconds');
                                function updateTimer() {
                                    const now = Date.now();
                                    const jsTimestamp = timestamp > 9999999999 ? timestamp : timestamp * 1000;
                                    const diff = jsTimestamp - now;
                                    if (diff <= 0) { daysEl.textContent = "00"; hoursEl.textContent = "00"; minutesEl.textContent = "00"; secondsEl.textContent = "00"; return; }
                                    const d = Math.floor(diff / (1000 * 60 * 60 * 24));
                                    const h = Math.floor((diff / (1000 * 60 * 60)) % 24);
                                    const m = Math.floor((diff / 1000 / 60) % 60);
                                    const s = Math.floor((diff / 1000) % 60);
                                    daysEl.textContent = d.toString().padStart(2, '0');
                                    hoursEl.textContent = h.toString().padStart(2, '0');
                                    minutesEl.textContent = m.toString().padStart(2, '0');
                                    secondsEl.textContent = s.toString().padStart(2, '0');
                                }
                                updateTimer();
                                setInterval(updateTimer, 1000);
                            });
