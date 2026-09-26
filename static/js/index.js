// LightCrafter project page. Carousel / BibTeX / scroll helpers follow the Vista4D project page.

// Minimum time (ms) before a carousel auto-advances. The actual delay is
// ceil(minTime / videoDuration) × videoDuration, so each video always
// finishes at least one full loop and the total wait is >= this value.
var CAROUSEL_AUTOPLAY_MIN = 5000;

// Start playback and retry once the browser has enough data, so a video whose
// src was set a moment ago does not stay frozen on its first frame.
function safePlay(videoEl) {
    var p = videoEl.play();
    if (p && p.catch) p.catch(function() {});
    if (videoEl.readyState < 3) {
        var onReady = function() {
            videoEl.removeEventListener('canplay', onReady);
            if (videoEl.paused && videoEl.getAttribute('preload') === 'auto') {
                var q = videoEl.play();
                if (q && q.catch) q.catch(function() {});
            }
        };
        videoEl.addEventListener('canplay', onReady);
    }
}

// Load a video's src from its data-src attribute (lazy loading).
function loadVideo(videoEl) {
    if (videoEl.dataset.loaded) return;
    videoEl.dataset.loaded = '1';
    var source = videoEl.querySelector('source[data-src]');
    if (source) {
        source.src = source.dataset.src;
        videoEl.load();
    }
}

// Copy BibTeX to clipboard
function copyBibTeX() {
    const bibtexElement = document.getElementById('bibtex-code');
    const button = document.querySelector('.copy-bibtex-btn');
    const copyText = button.querySelector('.copy-text');
    
    if (bibtexElement) {
        navigator.clipboard.writeText(bibtexElement.textContent).then(function() {
            // Success feedback
            button.classList.add('copied');
            copyText.textContent = 'Cop';
            
            setTimeout(function() {
                button.classList.remove('copied');
                copyText.textContent = 'Copy';
            }, 2000);
        }).catch(function(err) {
            console.error('Failed to copy: ', err);
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = bibtexElement.textContent;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            button.classList.add('copied');
            copyText.textContent = 'Cop';
            setTimeout(function() {
                button.classList.remove('copied');
                copyText.textContent = 'Copy';
            }, 2000);
        });
    }
}

// Scroll to top functionality
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Show/hide scroll to top button
window.addEventListener('scroll', function() {
    const scrollButton = document.querySelector('.scroll-to-top');
    if (!scrollButton) return;
    if (window.pageYOffset > 300) {
        scrollButton.classList.add('visible');
    } else {
        scrollButton.classList.remove('visible');
    }
});

// Carousel initialization
function initCarousels() {
    document.querySelectorAll('.carousel').forEach(function(carousel) {
        var track = carousel.querySelector('.carousel-track');
        var items = Array.from(track.children);
        var prevBtn = carousel.querySelector('.carousel-prev');
        var nextBtn = carousel.querySelector('.carousel-next');
        var dotsContainer = carousel.querySelector('.carousel-dots');
        var currentIndex = 0;
        var autoplayTimer = null;
        var pendingMetaCb = null;
        var isTransitioning = false;
        var isTwoUp = carousel.classList.contains('carousel-two-up');

        function getSlidesPerView() {
            if (!isTwoUp) return 1;
            return window.innerWidth > 768 ? 2 : 1;
        }

        var maxSlidesPerView = isTwoUp ? 2 : 1;

        // Clone items for seamless infinite scrolling:
        // - Prepend clone of last item (for wrapping left)
        // - Append clones of first N items (for wrapping right + filling two-up view)
        var cloneBefore = items[items.length - 1].cloneNode(true);
        cloneBefore.setAttribute('aria-hidden', 'true');
        track.insertBefore(cloneBefore, track.firstChild);

        for (var c = 0; c < maxSlidesPerView; c++) {
            var cloneAfter = items[c].cloneNode(true);
            cloneAfter.setAttribute('aria-hidden', 'true');
            track.appendChild(cloneAfter);
        }

        // All track children including clones (for video management)
        var allTrackChildren = Array.from(track.children);

        // Stop all carousel videos from auto-playing on page load.
        // src is not set yet (lazy-loaded via data-src), so use preload="none".
        allTrackChildren.forEach(function(item) {
            var v = item.querySelector('video');
            if (v) {
                v.removeAttribute('autoplay');
                v.setAttribute('preload', 'none');
                v.pause();
            }
        });

        // Play only the currently visible videos from the start, pause the rest.
        // Skip if the carousel is hidden (e.g., inside a collapsed section).
        function activateVideos() {
            if (!carousel.offsetParent) return;

            var slidesPerView = getSlidesPerView();
            var startPos = currentIndex + 1; // +1 for prepended clone

            allTrackChildren.forEach(function(item, domIdx) {
                var v = item.querySelector('video');
                if (!v) return;
                if (domIdx >= startPos && domIdx < startPos + slidesPerView) {
                    loadVideo(v);
                    v.setAttribute('preload', 'auto');
                    v.currentTime = 0;
                    safePlay(v);
                } else {
                    v.pause();
                    v.setAttribute('preload', 'none');
                }
            });

            // Preload the next and previous real slides so navigation feels instant.
            [currentIndex + 1, currentIndex - 1].forEach(function(i) {
                var realIdx = ((i % items.length) + items.length) % items.length;
                var item = allTrackChildren[realIdx + 1]; // +1 for prepended clone
                if (item) {
                    var v = item.querySelector('video');
                    if (v) loadVideo(v);
                }
            });
        }

        // Offset by 1 to skip the prepended clone
        function setTransform(index) {
            var stepPercent = 100 / getSlidesPerView();
            var pos = (index + 1) * stepPercent;
            track.style.transform = 'translateX(-' + pos + '%)';
        }

        // Set initial position without animation (activation deferred to IntersectionObserver)
        track.style.transition = 'none';
        setTransform(0);
        track.offsetHeight; // force reflow
        track.style.transition = '';

        // Create dots (one per real item)
        items.forEach(function(_, i) {
            var dot = document.createElement('button');
            dot.className = 'carousel-dot' + (i === 0 ? ' active' : '');
            dot.addEventListener('click', function() { goTo(i); });
            dotsContainer.appendChild(dot);
        });
        var dots = Array.from(dotsContainer.children);

        function updateDots() {
            dots.forEach(function(d, i) {
                d.classList.toggle('active', i === currentIndex);
            });
        }

        function goTo(index) {
            if (isTransitioning) return;

            if (index < 0) {
                // Wrapping left: animate to the prepended clone, then snap
                isTransitioning = true;
                setTransform(-1);
                currentIndex = items.length - 1;
                updateDots();
                resetAutoplay();
                return;
            }

            if (index >= items.length) {
                // Wrapping right: animate to the appended clone, then snap
                isTransitioning = true;
                setTransform(items.length);
                currentIndex = 0;
                updateDots();
                resetAutoplay();
                return;
            }

            currentIndex = index;
            setTransform(currentIndex);
            updateDots();
            activateVideos();
            resetAutoplay();
        }

        // After animating to a clone, instantly snap to the real position
        track.addEventListener('transitionend', function(e) {
            if (e.propertyName === 'transform' && isTransitioning) {
                isTransitioning = false;
                track.style.transition = 'none';
                setTransform(currentIndex);
                track.offsetHeight; // force reflow before restoring transition
                track.style.transition = '';
                activateVideos();
            }
        });

        prevBtn.addEventListener('click', function() { goTo(currentIndex - 1); });
        nextBtn.addEventListener('click', function() { goTo(currentIndex + 1); });

        // Keyboard navigation
        carousel.setAttribute('tabindex', '0');
        carousel.addEventListener('keydown', function(e) {
            if (e.key === 'ArrowLeft') goTo(currentIndex - 1);
            if (e.key === 'ArrowRight') goTo(currentIndex + 1);
        });

        // Pause autoplay on hover
        carousel.addEventListener('mouseenter', function() {
            cleanupAutoplay();
        });
        carousel.addEventListener('mouseleave', function() {
            resetAutoplay();
        });

        // Compute autoplay delay: N full loops of the current video where
        // N = max(1, ceil(CAROUSEL_AUTOPLAY_MIN / duration)).
        // Returns null if video duration is not yet available.
        function getAutoplayDelay() {
            var video = items[currentIndex] && items[currentIndex].querySelector('video');
            if (video && isFinite(video.duration) && video.duration > 0) {
                var durationMs = video.duration * 1000;
                var n = Math.max(1, Math.ceil(CAROUSEL_AUTOPLAY_MIN / durationMs));
                return n * durationMs;
            }
            return null;
        }

        function cleanupAutoplay() {
            if (autoplayTimer) clearTimeout(autoplayTimer);
            autoplayTimer = null;
            if (pendingMetaCb) {
                pendingMetaCb.video.removeEventListener('loadedmetadata', pendingMetaCb.fn);
                pendingMetaCb = null;
            }
        }

        function resetAutoplay() {
            cleanupAutoplay();

            // Don't auto-advance if carousel is hidden (collapsed section)
            if (!carousel.offsetParent) return;

            var delay = getAutoplayDelay();
            if (delay !== null) {
                autoplayTimer = setTimeout(function() {
                    goTo(currentIndex + 1);
                }, delay);
            } else {
                // Duration not available yet (video still loading);
                // wait for metadata then set the proper timer
                var video = items[currentIndex] && items[currentIndex].querySelector('video');
                if (video) {
                    var fn = function() {
                        video.removeEventListener('loadedmetadata', fn);
                        pendingMetaCb = null;
                        resetAutoplay();
                    };
                    pendingMetaCb = { video: video, fn: fn };
                    video.addEventListener('loadedmetadata', fn);
                }
                // Fallback in case metadata never loads
                autoplayTimer = setTimeout(function() {
                    if (pendingMetaCb) {
                        pendingMetaCb.video.removeEventListener('loadedmetadata', pendingMetaCb.fn);
                        pendingMetaCb = null;
                    }
                    goTo(currentIndex + 1);
                }, CAROUSEL_AUTOPLAY_MIN);
            }
        }

        // Update transform on resize when slidesPerView changes
        if (isTwoUp) {
            var lastSlidesPerView = getSlidesPerView();
            window.addEventListener('resize', function() {
                var newSlidesPerView = getSlidesPerView();
                if (newSlidesPerView !== lastSlidesPerView) {
                    lastSlidesPerView = newSlidesPerView;
                    track.style.transition = 'none';
                    setTransform(currentIndex);
                    track.offsetHeight;
                    track.style.transition = '';
                    activateVideos();
                }
            });
        }

        // Custom events for collapsible sections
        carousel.addEventListener('carousel-activate', function() {
            activateVideos();
            resetAutoplay();
        });
        carousel.addEventListener('carousel-deactivate', function() {
            cleanupAutoplay();
            allTrackChildren.forEach(function(item) {
                var v = item.querySelector('video');
                if (v) v.pause();
            });
        });

        // Activate the carousel only when it scrolls into view; pause when it leaves.
        if ('IntersectionObserver' in window) {
            var carouselObserver = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        activateVideos();
                        resetAutoplay();
                    } else {
                        cleanupAutoplay();
                        allTrackChildren.forEach(function(item) {
                            var v = item.querySelector('video');
                            if (v) v.pause();
                        });
                    }
                });
            }, { rootMargin: '100px 0px' });
            carouselObserver.observe(carousel);
        } else {
            // Fallback for browsers without IntersectionObserver
            activateVideos();
            resetAutoplay();
        }
    });
}

// Toggle a collapsible section and activate/deactivate its carousels
function toggleCollapsible(header) {
    var content = header.nextElementSibling;
    var icon = header.querySelector('.collapsible-icon');
    var hint = header.querySelector('.collapsible-hint');
    var isShowing = content.classList.toggle('show');
    icon.classList.toggle('open', isShowing);
    if (hint) hint.textContent = isShowing ? 'Click to collapse' : 'Click to expand';

    content.querySelectorAll('.carousel').forEach(function(c) {
        c.dispatchEvent(new Event(isShowing ? 'carousel-activate' : 'carousel-deactivate'));
    });
}


// ---------------------------------------------------------------------------
// Original hero teaser: synced rows, PBR <-> Refined slider, G-buffer quad drag,
// Appearance / Geometry toggle.
// ---------------------------------------------------------------------------
function initTeaser() {
    function videosIn(card) {
        return Array.prototype.slice.call(card.querySelectorAll('video.teaser-video'));
    }
    function syncVideoGroup(card) {
        var videos = videosIn(card);
        if (videos.length < 2) return;
        videos.forEach(function (v) { v.muted = true; v.playsInline = true; v.loop = true; });
        function ready(v) { return v.readyState >= 1; }
        function whenAllReady(cb) {
            if (videos.every(ready)) { cb(); return; }
            videos.forEach(function (v) {
                if (!ready(v)) {
                    v.addEventListener('loadedmetadata', function once() {
                        v.removeEventListener('loadedmetadata', once);
                        if (videos.every(ready)) cb();
                    });
                }
            });
        }
        whenAllReady(function () {
            videos.forEach(function (v) { v.currentTime = 0; });
            videos.forEach(function (v) { v.play().catch(function () {}); });
            function tick() {
                var live = videosIn(card);
                if (live.length >= 2) {
                    var t = live[0].currentTime;
                    live.forEach(function (v, idx) {
                        if (idx === 0) return;
                        if (Math.abs(v.currentTime - t) > 0.12) v.currentTime = t;
                    });
                }
                requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        });
    }
    document.querySelectorAll('.teaser-row').forEach(syncVideoGroup);

    // Only decode the teaser's 24 clips while the teaser is on screen.
    var teaserGrid = document.querySelector('.teaser-grid');
    if (teaserGrid && 'IntersectionObserver' in window) {
        var teaserObserver = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                teaserGrid.querySelectorAll('video').forEach(function(v) {
                    if (entry.isIntersecting) { v.play().catch(function() {}); } else { v.pause(); }
                });
            });
        }, { rootMargin: '100px 0px' });
        teaserObserver.observe(teaserGrid);
    }

    function wireSlider(cell) {
        var beforeVid = cell.querySelector('video.slider-before');
        var afterVid = cell.querySelector('video.slider-after');
        if (!beforeVid || !afterVid) return;
        [beforeVid, afterVid].forEach(function (v) {
            v.muted = true; v.playsInline = true; v.loop = true;
            v.play().catch(function () {});
        });
        function tick() {
            var t = beforeVid.currentTime;
            if (Math.abs(afterVid.currentTime - t) > 0.12) afterVid.currentTime = t;
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        var dragging = false;
        function setPos(clientX) {
            var rect = cell.getBoundingClientRect();
            var pct = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
            cell.style.setProperty('--pos', pct + '%');
        }
        cell.addEventListener('mousedown', function (e) { dragging = true; setPos(e.clientX); e.preventDefault(); });
        window.addEventListener('mousemove', function (e) { if (dragging) setPos(e.clientX); });
        window.addEventListener('mouseup', function () { dragging = false; });
        cell.addEventListener('touchstart', function (e) { if (e.touches.length) { dragging = true; setPos(e.touches[0].clientX); } }, { passive: true });
        cell.addEventListener('touchmove', function (e) { if (dragging && e.touches.length) setPos(e.touches[0].clientX); }, { passive: true });
        cell.addEventListener('touchend', function () { dragging = false; });
    }
    document.querySelectorAll('.slider-cell').forEach(wireSlider);

    function wireQuadDrag(quad) {
        var dragging = false;
        function setShift(clientX) {
            var rect = quad.getBoundingClientRect();
            var pct = ((clientX - rect.left) / rect.width) * 100;
            pct = Math.max(25, Math.min(75, pct));
            quad.style.setProperty('--shift', (pct - 50) + '%');
        }
        quad.addEventListener('mousedown', function (e) { dragging = true; setShift(e.clientX); e.preventDefault(); });
        window.addEventListener('mousemove', function (e) { if (dragging) setShift(e.clientX); });
        window.addEventListener('mouseup', function () { dragging = false; });
        quad.addEventListener('touchstart', function (e) { if (e.touches.length) { dragging = true; setShift(e.touches[0].clientX); } }, { passive: true });
        quad.addEventListener('touchmove', function (e) { if (dragging && e.touches.length) setShift(e.touches[0].clientX); }, { passive: true });
        quad.addEventListener('touchend', function () { dragging = false; });
    }
    document.querySelectorAll('.teaser-quad').forEach(wireQuadDrag);

    var grid = document.querySelector('.teaser-grid');
    var toggle = document.querySelector('.ir-toggle');
    if (!grid || !toggle) return;
    var geoVids = Array.prototype.slice.call(grid.querySelectorAll('.ir-geometry video'));
    geoVids.forEach(function (v) { v.muted = true; v.loop = true; v.playsInline = true; });
    function playGeo() { geoVids.forEach(function (v) { v.play().catch(function () {}); }); }
    toggle.addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-ir]');
        if (!btn) return;
        grid.setAttribute('data-ir-mode', btn.getAttribute('data-ir'));
        Array.prototype.slice.call(toggle.querySelectorAll('button')).forEach(function (b) {
            b.classList.toggle('is-active', b === btn);
        });
        if (btn.getAttribute('data-ir') === 'geometry') playGeo();
    });
    playGeo();
}

document.addEventListener('DOMContentLoaded', function() {
    initCarousels();
    initTeaser();
});
