window.HELP_IMPROVE_VIDEOJS = false;

var INTERP_BASE = "./static/interpolation/stacked";
var NUM_INTERP_FRAMES = 240;

var interp_images = [];
function preloadInterpolationImages() {
  for (var i = 0; i < NUM_INTERP_FRAMES; i++) {
    var path = INTERP_BASE + '/' + String(i).padStart(6, '0') + '.jpg';
    interp_images[i] = new Image();
    interp_images[i].src = path;
  }
}

function setInterpolationImage(i) {
  var image = interp_images[i];
  image.ondragstart = function() { return false; };
  image.oncontextmenu = function() { return false; };
  $('#interpolation-image-wrapper').empty().append(image);
}


$(document).ready(function() {
    // Check for click events on the navbar burger icon
    $(".navbar-burger").click(function() {
      // Toggle the "is-active" class on both the "navbar-burger" and the "navbar-menu"
      $(".navbar-burger").toggleClass("is-active");
      $(".navbar-menu").toggleClass("is-active");

    });

    var options = {
			slidesToScroll: 1,
			slidesToShow: 3,
			loop: true,
			infinite: true,
			autoplay: false,
			autoplaySpeed: 3000,
    }

		// Initialize all div with carousel class
    var carousels = bulmaCarousel.attach('.carousel', options);

    // Loop on each carousel initialized
    for(var i = 0; i < carousels.length; i++) {
    	// Add listener to  event
    	carousels[i].on('before:show', state => {
    		console.log(state);
    	});
    }

    // Access to bulmaCarousel instance of an element
    var element = document.querySelector('#my-element');
    if (element && element.bulmaCarousel) {
    	// bulmaCarousel instance is available as element.bulmaCarousel
    	element.bulmaCarousel.on('before-show', function(state) {
    		console.log(state);
    	});
    }

    /*var player = document.getElementById('interpolation-video');
    player.addEventListener('loadedmetadata', function() {
      $('#interpolation-slider').on('input', function(event) {
        console.log(this.value, player.duration);
        player.currentTime = player.duration / 100 * this.value;
      })
    }, false);*/
    preloadInterpolationImages();

    $('#interpolation-slider').on('input', function(event) {
      setInterpolationImage(this.value);
    });
    setInterpolationImage(0);
    $('#interpolation-slider').prop('max', NUM_INTERP_FRAMES - 1);

    bulmaSlider.attach();

    // ----- Synchronize videos within the same comparison/gallery row -----
    // For each `.comparison-card` or `.gallery-card` we install one master
    // clock that retimes every sibling video to the first video's currentTime.
    // The clock keeps ticking forever, so even when we swap a <source> mid-
    // playback (e.g. via the baseline/scene picker) the new video catches up
    // to the running playhead automatically.
    function videosIn(card) {
      return Array.prototype.slice.call(
        card.querySelectorAll('video.comparison-video, video.gallery-video')
      );
    }

    function syncVideoGroup(card) {
      var videos = videosIn(card);
      if (videos.length < 2) return;

      videos.forEach(function (v) {
        v.muted = true;
        v.playsInline = true;
        v.loop = true;
      });

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
        videos.forEach(function (v) {
          v.play().catch(function () { /* ignore autoplay errors */ });
        });

        function tick() {
          // Refresh the live list every tick so newly-swapped videos in the
          // same card are picked up.
          var live = videosIn(card);
          if (live.length >= 2) {
            var anchor = live[0];
            var t = anchor.currentTime;
            live.forEach(function (v, idx) {
              if (idx === 0) return;
              var drift = Math.abs(v.currentTime - t);
              if (drift > 0.12) v.currentTime = t;
            });
          }
          requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      });
    }

    document.querySelectorAll('.comparison-card, .gallery-card').forEach(function (card) {
      syncVideoGroup(card);
    });

    // ----- Realworld baseline picker -----
    // Each .baseline-picker button[data-baseline] updates the rightmost cell
    // of its parent comparison-card to play that baseline's video. Source paths
    // assume the card has an existing <source src=".../<baseline>.mp4"> we can
    // pattern-match on to extract the row's folder.
    var CACHE_BUSTER = '?v=5';

    function setSrc(video, url) {
      var src = video.querySelector('source');
      if (!src) return;
      var clean = url.split('?')[0];
      src.setAttribute('src', clean + CACHE_BUSTER);
      video.load();
      video.play().catch(function () { /* ignore */ });
    }

    function activeButton(group, value, attr) {
      Array.prototype.slice.call(group.querySelectorAll('button'))
        .forEach(function (b) {
          if (b.getAttribute(attr) === value) b.classList.add('is-active');
          else b.classList.remove('is-active');
        });
    }

    function wireBaselinePicker(card) {
      var picker = card.querySelector('.baseline-picker');
      var swapVideo = card.querySelector('video[data-method="baseline-pick"]');
      var swapLabel = card.querySelector('.baseline-cell-label');
      if (!picker || !swapVideo) return;

      // Derive folder root from the swap video's current src so this helper
      // works for any row (e.g. ./static/videos/comparison/realworld-row/).
      var initialSrc = swapVideo.querySelector('source').getAttribute('src') || '';
      var folderRoot = initialSrc.replace(/\/[^\/]+\.mp4(\?.*)?$/, '/');

      var labelMap = {
        lightx: 'vs LightX',
        dr: 'vs DR',
        unirelight: 'vs UniRelight',
        pbr: 'vs PBR',
        pcrp: 'vs PCRP'
      };

      Array.prototype.slice.call(picker.querySelectorAll('button[data-baseline]'))
        .forEach(function (btn) {
          btn.addEventListener('click', function () {
            var baseline = btn.getAttribute('data-baseline');
            activeButton(picker, baseline, 'data-baseline');
            swapVideo.setAttribute('data-current', baseline);
            if (swapLabel) swapLabel.textContent = labelMap[baseline] || ('vs ' + baseline);
            setSrc(swapVideo, folderRoot + baseline + '.mp4');
          });
        });
    }

    document.querySelectorAll('.comparison-card .baseline-picker').forEach(function (picker) {
      var card = picker.closest('.comparison-card');
      if (card) wireBaselinePicker(card);
    });

    // ----- Before/after slider in the Showcase rows -----
    function wireSlider(cell) {
      var beforeVid = cell.querySelector('video.slider-before');
      var afterVid = cell.querySelector('video.slider-after');
      if (!beforeVid || !afterVid) return;
      [beforeVid, afterVid].forEach(function (v) {
        v.muted = true; v.playsInline = true; v.loop = true;
        v.play().catch(function () { /* ignore */ });
      });

      // Keep the two videos frame-locked to each other.
      function tick() {
        var t = beforeVid.currentTime;
        if (Math.abs(afterVid.currentTime - t) > 0.12) {
          afterVid.currentTime = t;
        }
        requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);

      var dragging = false;

      function setPos(clientX) {
        var rect = cell.getBoundingClientRect();
        var x = clientX - rect.left;
        var pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
        cell.style.setProperty('--pos', pct + '%');
      }

      cell.addEventListener('mousedown', function (e) {
        dragging = true; setPos(e.clientX); e.preventDefault();
      });
      window.addEventListener('mousemove', function (e) {
        if (dragging) setPos(e.clientX);
      });
      window.addEventListener('mouseup', function () { dragging = false; });

      cell.addEventListener('touchstart', function (e) {
        if (e.touches.length) { dragging = true; setPos(e.touches[0].clientX); }
      }, { passive: true });
      cell.addEventListener('touchmove', function (e) {
        if (dragging && e.touches.length) setPos(e.touches[0].clientX);
      }, { passive: true });
      cell.addEventListener('touchend', function () { dragging = false; });
    }

    document.querySelectorAll('.slider-cell').forEach(wireSlider);

    // ----- Synthetic comparison: pick scene + left/right method for the slider -----
    function wireSyntheticComparison() {
      var root = document.getElementById('synthetic-compare');
      if (!root) return;

      var cell = root.querySelector('.synthetic-slider-cell');
      var beforeVid = cell.querySelector('video.slider-before');
      var afterVid = cell.querySelector('video.slider-after');
      var leftLabel = root.querySelector('.syn-left-label');
      var rightLabel = root.querySelector('.syn-right-label');
      var scenePicker = root.querySelector('.syn-scene-picker');
      var leftPicker = root.querySelector('.syn-left-picker');
      var rightPicker = root.querySelector('.syn-right-picker');

      var FILE = {
        input: 'input', target: 'gt', pbr: 'pbr', ours: 'ours',
        dr: 'dr', lightx: 'lightx', unirelight: 'unirelight'
      };
      var LABEL = {
        input: 'Input', target: 'Target', pbr: 'PBR', ours: 'Ours',
        dr: 'DR', lightx: 'LightX', unirelight: 'UniRelight'
      };
      // Methods that actually have a clip in each scene folder (s2 has no UniRelight).
      var AVAIL = {
        s1: ['input', 'target', 'pbr', 'ours', 'dr', 'lightx', 'unirelight'],
        s2: ['input', 'target', 'pbr', 'ours', 'dr', 'lightx'],
        s3: ['input', 'target', 'pbr', 'ours', 'dr', 'lightx', 'unirelight'],
        s4: ['input', 'target', 'pbr', 'ours', 'dr', 'lightx', 'unirelight']
      };

      function srcFor(scene, method) {
        return './static/videos/comparison/' + scene + '/' + FILE[method] + '.mp4';
      }
      function setVideo(video, url) {
        var s = video.querySelector('source');
        if (!s) return;
        if (s.getAttribute('src') === url) return;
        s.setAttribute('src', url);
        video.load();
        video.play().catch(function () { /* ignore */ });
      }
      function setActive(group, attr, value) {
        Array.prototype.slice.call(group.querySelectorAll('button')).forEach(function (b) {
          if (b.getAttribute(attr) === value) b.classList.add('is-active');
          else b.classList.remove('is-active');
        });
      }
      function applyAvailability(scene) {
        var avail = AVAIL[scene] || [];
        [leftPicker, rightPicker].forEach(function (group) {
          Array.prototype.slice.call(group.querySelectorAll('button[data-method]'))
            .forEach(function (b) {
              var ok = avail.indexOf(b.getAttribute('data-method')) !== -1;
              b.disabled = !ok;
              b.classList.toggle('is-disabled', !ok);
            });
        });
      }
      function resolve(scene, method) {
        var avail = AVAIL[scene] || [];
        if (avail.indexOf(method) !== -1) return method;
        return avail[0] || method;
      }

      function render() {
        var scene = root.getAttribute('data-scene');
        var left = resolve(scene, root.getAttribute('data-left'));
        var right = resolve(scene, root.getAttribute('data-right'));
        root.setAttribute('data-left', left);
        root.setAttribute('data-right', right);

        applyAvailability(scene);
        setActive(scenePicker, 'data-scene', scene);
        setActive(leftPicker, 'data-method', left);
        setActive(rightPicker, 'data-method', right);

        setVideo(beforeVid, srcFor(scene, left));
        setVideo(afterVid, srcFor(scene, right));
        if (leftLabel) leftLabel.textContent = LABEL[left];
        if (rightLabel) rightLabel.textContent = LABEL[right];
      }

      scenePicker.addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-scene]');
        if (!btn) return;
        root.setAttribute('data-scene', btn.getAttribute('data-scene'));
        render();
      });
      leftPicker.addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-method]');
        if (!btn || btn.disabled) return;
        root.setAttribute('data-left', btn.getAttribute('data-method'));
        render();
      });
      rightPicker.addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-method]');
        if (!btn || btn.disabled) return;
        root.setAttribute('data-right', btn.getAttribute('data-method'));
        render();
      });

      render();
    }

    wireSyntheticComparison();

    // ----- Showcase scenes: pick illum for the slider + inline lighting probe -----
    function wireShowcaseScene(card) {
      var cell = card.querySelector('.slider-cell');
      if (!cell) return;
      var beforeVid = cell.querySelector('video.slider-before');
      var afterVid = cell.querySelector('video.slider-after');
      var probe = card.querySelector('.showcase-probe');
      var picker = card.querySelector('.illum-picker');
      if (!picker || !beforeVid || !afterVid) return;

      function setVideo(video, url) {
        var s = video.querySelector('source');
        if (!s || !url) return;
        if (s.getAttribute('src') === url) return;
        s.setAttribute('src', url);
        video.load();
        video.play().catch(function () { /* ignore */ });
      }
      function setActive(value) {
        Array.prototype.slice.call(picker.querySelectorAll('button[data-illum]'))
          .forEach(function (b) {
            if (b.getAttribute('data-illum') === value) b.classList.add('is-active');
            else b.classList.remove('is-active');
          });
      }

      function selectIllum(illum) {
        var btn = picker.querySelector('button[data-illum="' + illum + '"]');
        if (!btn) return;
        setActive(illum);
        setVideo(beforeVid, btn.getAttribute('data-pbr'));
        setVideo(afterVid, btn.getAttribute('data-relit'));
        if (probe) {
          var ball = btn.getAttribute('data-ball');
          var name = btn.getAttribute('data-envname') || '';
          if (ball) probe.querySelector('img').setAttribute('src', ball);
          var cap = probe.querySelector('.showcase-probe-name');
          if (cap) cap.textContent = name;
        }
      }

      picker.addEventListener('click', function (e) {
        var btn = e.target.closest('button[data-illum]');
        if (!btn) return;
        selectIllum(btn.getAttribute('data-illum'));
      });

      var active = picker.querySelector('button.is-active[data-illum]') ||
                   picker.querySelector('button[data-illum]');
      if (active) selectIllum(active.getAttribute('data-illum'));
    }

    document.querySelectorAll('.showcase-scene').forEach(wireShowcaseScene);
})
