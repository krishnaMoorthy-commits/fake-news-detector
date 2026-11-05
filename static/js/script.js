/* ==========================================================================
   Fake News Detection — UI layer
   ---------------------------------------------------------------------------
   This file contains ONLY interface behaviour: navigation, scroll reveals,
   character counting, sample text and the submit/loading state.
   No prediction ever happens here. Every classification is performed by the
   Flask backend in app.py / model.py.
   ========================================================================== */

(function () {
  "use strict";

  var MAX_CHARS = 10000;

  /* ---------------------------------------------------------------------
     Sample inputs (plain example text used to demo the form, nothing else)
  --------------------------------------------------------------------- */
  var SAMPLES = {
    neutral: {
      headline: "City council approves budget for riverside park",
      article:
        "The city council voted on Tuesday to approve a funding package for a new " +
        "riverside park. The plan includes walking paths, improved lighting and a " +
        "small children's play area. Construction is expected to begin next spring, " +
        "according to the agenda published by the council before the meeting."
    },
    sensational: {
      headline: "You won't BELIEVE what this celebrity just did",
      article:
        "This one weird trick is being hidden from the public by powerful corporations. " +
        "Share this before it gets deleted, because the mainstream media does not want " +
        "you to know the truth. Click now to reveal the secret they are covering up, " +
        "and comment AMEN if you agree."
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    initHeader();
    initNav();
    initReveals();
    initAnalysisForm();
    initPasteButton();
    initUpgrade();
  });

  /* ---------------------------------------------------------------------
     Header: subtle elevation once the page is scrolled
  --------------------------------------------------------------------- */
  function initHeader() {
    var header = document.querySelector(".site-header");
    if (!header) return;

    var update = function () {
      header.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
  }

  /* ---------------------------------------------------------------------
     Mobile navigation
  --------------------------------------------------------------------- */
  function initNav() {
    var toggle = document.getElementById("navToggle");
    var menu = document.getElementById("navMenu");
    if (!toggle || !menu) return;

    var isOpen = function () {
      return menu.getAttribute("data-open") === "true";
    };

    var setOpen = function (open) {
      menu.setAttribute("data-open", open ? "true" : "false");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };

    setOpen(false);

    toggle.addEventListener("click", function () {
      setOpen(!isOpen());
    });

    // Close with Escape and return focus to the trigger.
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && isOpen()) {
        setOpen(false);
        toggle.focus();
      }
    });

    // Close when clicking/tapping outside the menu.
    document.addEventListener("click", function (event) {
      if (!isOpen()) return;
      if (menu.contains(event.target) || toggle.contains(event.target)) return;
      setOpen(false);
    });

    // Close after choosing a destination.
    menu.addEventListener("click", function (event) {
      if (event.target && event.target.closest && event.target.closest("a")) {
        setOpen(false);
      }
    });

    // Reset the panel when moving back to desktop layout.
    window.addEventListener("resize", function () {
      if (window.innerWidth > 900 && isOpen()) setOpen(false);
    });
  }

  /* ---------------------------------------------------------------------
     Scroll reveal (skipped entirely for reduced-motion users)
  --------------------------------------------------------------------- */
  function initReveals() {
    var items = document.querySelectorAll(".reveal");
    if (!items.length) return;

    var reduce =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var showAll = function () {
      for (var i = 0; i < items.length; i++) items[i].classList.add("is-visible");
    };

    if (reduce || typeof IntersectionObserver === "undefined") {
      showAll();
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -6% 0px" }
    );

    for (var i = 0; i < items.length; i++) observer.observe(items[i]);
  }

  /* ---------------------------------------------------------------------
     Analysis form: counter, validation, samples, loading state
  --------------------------------------------------------------------- */
  function initAnalysisForm() {
    var form = document.getElementById("detectForm");
    if (!form) return;

    var headline = document.getElementById("headline");
    var article = document.getElementById("article");
    var counter = document.getElementById("charCounter");
    var warning = document.getElementById("charWarning");
    var checkBtn = document.getElementById("checkBtn");
    var clearBtn = document.getElementById("clearBtn");
    var errorBox = document.getElementById("formErrors");

    /* --- character counter --- */
    function updateCounter() {
      if (!counter) return;
      var total = ((headline && headline.value.length) || 0) +
                  ((article && article.value.length) || 0);
      counter.textContent = total.toLocaleString() + " / " +
                            MAX_CHARS.toLocaleString() + " characters";
      counter.classList.toggle("is-over", total > MAX_CHARS);

      if (warning) {
        warning.textContent =
          total > MAX_CHARS ? "Limit exceeded — shorten the text to continue." : "";
      }
      return total;
    }

    /* --- inline error message (never an alert box) --- */
    function showError(message) {
      if (!errorBox) return;
      errorBox.textContent = "";
      var row = document.createElement("div");
      row.className = "alert alert-error";
      var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("class", "icon");
      icon.setAttribute("aria-hidden", "true");
      var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", "#i-alert");
      icon.appendChild(use);
      var text = document.createElement("div");
      text.textContent = message; // safe: plain text node, never HTML
      row.appendChild(icon);
      row.appendChild(text);
      errorBox.appendChild(row);
      errorBox.hidden = false;
      errorBox.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    function clearError() {
      if (!errorBox) return;
      errorBox.textContent = "";
      errorBox.hidden = true;
    }

    /* --- counters wired to input --- */
    if (headline) headline.addEventListener("input", updateCounter);
    if (article) article.addEventListener("input", updateCounter);
    updateCounter();

    /* --- sample chips --- */
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-sample]"),
      function (chip) {
        chip.addEventListener("click", function () {
          var key = chip.getAttribute("data-sample");
          if (key === "clear" || !SAMPLES[key]) {
            if (headline) headline.value = "";
            if (article) article.value = "";
            clearError();
            updateCounter();
            if (headline) headline.focus();
            return;
          }
          if (headline) headline.value = SAMPLES[key].headline;
          if (article) article.value = SAMPLES[key].article;
          clearError();
          updateCounter();
          if (article) article.focus();
        });
      }
    );

    /* --- clear button --- */
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (headline) headline.value = "";
        if (article) article.value = "";
        clearError();
        updateCounter();
        if (headline) headline.focus();
      });
    }

    /* --- validation + loading state --- */
    form.addEventListener("submit", function (event) {
      var text = ((headline && headline.value) || "").trim();
      var body = ((article && article.value) || "").trim();

      if (!text && !body) {
        event.preventDefault();
        showError("Please enter a news headline or article before checking.");
        if (headline) headline.focus();
        return;
      }

      var total = text.length + body.length;
      if (total > MAX_CHARS) {
        event.preventDefault();
        showError(
          "Input is too long. Please limit your text to " +
            MAX_CHARS.toLocaleString() + " characters."
        );
        return;
      }

      if (checkBtn && !checkBtn.dataset.modelMissing) {
        // Reveal the loading state without delaying the request itself.
        checkBtn.classList.add("is-loading");
        checkBtn.setAttribute("aria-disabled", "true");
      }
    });

    // The page may come back from the back/forward cache with the button
    // still in its loading state — restore it.
    window.addEventListener("pageshow", function () {
      if (!checkBtn) return;
      checkBtn.classList.remove("is-loading");
      checkBtn.removeAttribute("aria-disabled");
    });
  }

  /* ---------------------------------------------------------------------
     Paste article button — reads the system clipboard into the article
     field through the async Clipboard API (available on secure origins,
     which includes http://localhost). Any failure is reported honestly in
     the #pasteNote status line instead of failing silently.
  --------------------------------------------------------------------- */
  function initPasteButton() {
    var pasteBtn = document.getElementById("pasteArticleBtn");
    var article = document.getElementById("article");
    var note = document.getElementById("pasteNote");
    if (!pasteBtn || !article) return;

    var noteTimer = null;
    function showNote(message, isError) {
      if (!note) return;
      note.textContent = message;
      note.hidden = false;
      note.style.color = isError ? "var(--warn)" : "var(--accent)";
      clearTimeout(noteTimer);
      noteTimer = setTimeout(function () {
        note.hidden = true;
      }, 7000);
    }

    pasteBtn.addEventListener("click", function () {
      if (!navigator.clipboard || !navigator.clipboard.readText) {
        showNote(
          "Reading the clipboard is not supported in this browser — click into the article box and press Ctrl+V (Cmd+V on Mac) instead.",
          true
        );
        return;
      }

      pasteBtn.classList.add("is-busy");
      navigator.clipboard
        .readText()
        .then(function (text) {
          pasteBtn.classList.remove("is-busy");
          if (!text || !text.trim()) {
            showNote("The clipboard is empty — copy some text first.", true);
            return;
          }
          article.value = text;
          // Reuse the existing counter/validation wiring.
          article.dispatchEvent(new Event("input", { bubbles: true }));
          article.focus();
          showNote(
            "Pasted " + text.length.toLocaleString() + " characters from the clipboard."
          );
        })
        .catch(function () {
          pasteBtn.classList.remove("is-busy");
          showNote(
            "Clipboard access was denied by the browser — click into the article box and press Ctrl+V (Cmd+V on Mac) instead.",
            true
          );
        });
    });
  }

  /* ====================================================================
     PREMIUM PLATFORM UPGRADE — background particles
     Decorative only. Skipped entirely for reduced-motion users and
     paused when the tab is hidden so it costs nothing in the background.
  ==================================================================== */
  function initParticles() {
    var canvas = document.getElementById("bgParticles");
    if (!canvas || !canvas.getContext) return;

    var reduce =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      canvas.style.display = "none";
      return;
    }

    var ctx = canvas.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var width = 0;
    var height = 0;
    var dots = [];
    var rafId = null;

    function seed() {
      var count = Math.max(18, Math.min(56, Math.round((width * height) / 26000)));
      dots = [];
      for (var i = 0; i < count; i++) {
        dots.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.22,
          vy: (Math.random() - 0.5) * 0.22,
          r: Math.random() * 1.6 + 0.6,
          a: Math.random() * 0.4 + 0.18
        });
      }
    }

    function resize() {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      if (!width || !height) return;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    }

    function frame() {
      ctx.clearRect(0, 0, width, height);

      var i, j, p, q, dx, dy, dist;
      for (i = 0; i < dots.length; i++) {
        p = dots[i];
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < -8) p.x = width + 8;
        if (p.x > width + 8) p.x = -8;
        if (p.y < -8) p.y = height + 8;
        if (p.y > height + 8) p.y = -8;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(56, 189, 248," + p.a + ")";
        ctx.fill();
      }

      // Faint connecting lines between nearby particles.
      for (i = 0; i < dots.length; i++) {
        p = dots[i];
        for (j = i + 1; j < dots.length; j++) {
          q = dots[j];
          dx = p.x - q.x;
          dy = p.y - q.y;
          dist = dx * dx + dy * dy;
          if (dist < 15000) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = "rgba(99, 102, 241," + (0.14 * (1 - dist / 15000)) + ")";
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      rafId = window.requestAnimationFrame(frame);
    }

    function start() {
      if (rafId === null) rafId = window.requestAnimationFrame(frame);
    }
    function stop() {
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    resize();
    start();

    var resizeTimer = null;
    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(resize, 180);
    });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop();
      else start();
    });
  }

  /* ====================================================================
     Animated statistics — counts up to the real, server-rendered value
  ==================================================================== */
  function initCountUp() {
    var items = document.querySelectorAll("[data-count]");
    if (!items.length) return;

    var reduce =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || typeof IntersectionObserver === "undefined") return; // keep final values

    function animate(el) {
      var raw = el.getAttribute("data-count") || "";
      var target = parseFloat(raw);
      if (isNaN(target)) return;
      var suffix = el.getAttribute("data-suffix") || "";
      var decimals = (raw.split(".")[1] || "").length;
      var duration = 1200;
      var start = null;

      function render(value) {
        var text = decimals > 0
          ? value.toFixed(decimals)
          : Math.round(value).toLocaleString();
        el.textContent = text + suffix;
      }

      function step(now) {
        if (start === null) start = now;
        var progress = Math.min(1, (now - start) / duration);
        var eased = 1 - Math.pow(1 - progress, 3);
        render(target * eased);
        if (progress < 1) window.requestAnimationFrame(step);
      }

      render(0);
      window.requestAnimationFrame(step);
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          animate(entry.target);
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.5 }
    );

    Array.prototype.forEach.call(items, function (el) { observer.observe(el); });
  }

  /* ====================================================================
     Glass-card pointer glow (subtle, desktop pointers only)
  ==================================================================== */
  function initGlassGlow() {
    if (!window.matchMedia || !window.matchMedia("(pointer: fine)").matches) return;
    var cards = document.querySelectorAll(".glass-card");
    Array.prototype.forEach.call(cards, function (card) {
      card.addEventListener("pointermove", function (event) {
        var rect = card.getBoundingClientRect();
        card.style.setProperty("--mx", ((event.clientX - rect.left) / rect.width * 100) + "%");
        card.style.setProperty("--my", ((event.clientY - rect.top) / rect.height * 100) + "%");
      });
    });
  }

  /* ====================================================================
     AI workflow visualization — stage selection + optional auto-play
     (visual walkthrough only: it never submits text or fakes a result)
  ==================================================================== */
  function initWorkflow() {
    var root = document.getElementById("workflowViz");
    if (!root) return;

    var nodes = root.querySelectorAll(".wf-node");
    var panels = root.querySelectorAll(".wf-panel");
    var fill = document.getElementById("wfProgressFill");
    var playBtn = document.getElementById("wfPlayBtn");
    var playLabel = playBtn ? playBtn.querySelector(".wf-play-label") : null;
    if (!nodes.length) return;

    var current = 0;
    var timer = null;

    function setStep(index) {
      current = index;
      Array.prototype.forEach.call(nodes, function (node, i) {
        node.classList.toggle("is-active", i === index);
        node.classList.toggle("is-done", i < index);
        node.setAttribute("aria-pressed", i === index ? "true" : "false");
      });
      Array.prototype.forEach.call(panels, function (panel, i) {
        panel.classList.toggle("is-active", i === index);
      });
      if (fill) fill.style.width = ((index + 1) / nodes.length * 100) + "%";
    }

    function stop() {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
      if (playLabel) playLabel.textContent = "Play pipeline";
      if (playBtn) playBtn.setAttribute("aria-pressed", "false");
    }

    function play() {
      if (timer !== null) { stop(); return; }
      setStep(0);
      if (playLabel) playLabel.textContent = "Stop pipeline";
      if (playBtn) playBtn.setAttribute("aria-pressed", "true");
      timer = window.setInterval(function () {
        if (current >= nodes.length - 1) {
          stop();
          return;
        }
        setStep(current + 1);
      }, 1500);
    }

    Array.prototype.forEach.call(nodes, function (node, i) {
      node.addEventListener("click", function () {
        stop();
        setStep(i);
      });
    });

    if (playBtn) playBtn.addEventListener("click", play);

    // Pause the walkthrough when it scrolls out of view.
    if (typeof IntersectionObserver !== "undefined") {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) stop();
        });
      }, { threshold: 0.15 });
      observer.observe(root);
    }

    setStep(0);
  }

  /* ====================================================================
     Document upload — drag & drop, validation, real progress, submit
  ==================================================================== */
  function initUpload() {
    var form = document.getElementById("uploadForm");
    if (!form) return;

    var input = document.getElementById("document");
    var zone = document.getElementById("dropzone");
    var fileRow = document.getElementById("fileRow");
    var fileNameEl = document.getElementById("fileName");
    var fileMetaEl = document.getElementById("fileMeta");
    var removeBtn = document.getElementById("removeFileBtn");
    var clearBtn = document.getElementById("clearUploadBtn");
    var submitBtn = document.getElementById("uploadBtn");
    var progress = document.getElementById("uploadProgress");
    var progressTrack = document.getElementById("uploadProgressBar");
    var progressFill = document.getElementById("uploadProgressFill");
    var progressText = document.getElementById("uploadProgressText");
    var errorBox = document.getElementById("uploadErrors");

    var MAX_BYTES = 2 * 1024 * 1024;
    var ALLOWED = ["txt", "pdf", "docx"];
    var selected = null;

    function showError(message) {
      if (!errorBox) return;
      errorBox.textContent = "";
      var row = document.createElement("div");
      row.className = "alert alert-error";
      var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("class", "icon");
      icon.setAttribute("aria-hidden", "true");
      var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", "#i-alert");
      icon.appendChild(use);
      var text = document.createElement("div");
      text.textContent = message; // plain text node, never HTML
      row.appendChild(icon);
      row.appendChild(text);
      errorBox.appendChild(row);
      errorBox.hidden = false;
    }

    function clearError() {
      if (!errorBox) return;
      errorBox.textContent = "";
      errorBox.hidden = true;
    }

    function formatSize(bytes) {
      if (bytes < 1024) return bytes + " B";
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
      return (bytes / (1024 * 1024)).toFixed(2) + " MB";
    }

    function updateSubmitState() {
      if (!submitBtn) return;
      submitBtn.disabled = !selected;
    }

    function resetSelection() {
      selected = null;
      if (input) input.value = "";
      if (fileRow) fileRow.hidden = true;
      if (zone) zone.classList.remove("is-valid", "is-invalid", "is-dragover");
      updateSubmitState();
    }

    function acceptFile(file) {
      if (!file) return;
      clearError();

      var parts = (file.name || "").split(".");
      var ext = parts.length > 1 ? parts.pop().toLowerCase() : "";

      if (ALLOWED.indexOf(ext) === -1) {
        resetSelection();
        if (zone) zone.classList.add("is-invalid");
        showError("Unsupported file type." +
          " Please choose a TXT, PDF or DOCX file (got '" + (ext || "no extension") + "').");
        return;
      }

      if (file.size > MAX_BYTES) {
        resetSelection();
        if (zone) zone.classList.add("is-invalid");
        showError("File is too large (" + formatSize(file.size) +
          "). The maximum allowed size is 2 MB.");
        return;
      }

      if (file.size === 0) {
        resetSelection();
        if (zone) zone.classList.add("is-invalid");
        showError("The selected file is empty.");
        return;
      }

      selected = file;
      if (fileNameEl) fileNameEl.textContent = file.name;
      if (fileMetaEl) {
        fileMetaEl.textContent = ext.toUpperCase() + " · " + formatSize(file.size);
      }
      if (fileRow) fileRow.hidden = false;
      if (zone) {
        zone.classList.remove("is-invalid", "is-dragover");
        zone.classList.add("is-valid");
      }
      updateSubmitState();
    }

    /* --- file picker --- */
    if (input) {
      input.addEventListener("change", function () {
        if (input.files && input.files[0]) acceptFile(input.files[0]);
      });
    }

    /* --- click anywhere in the zone opens the picker (labels/buttons excluded) --- */
    if (zone) {
      zone.addEventListener("click", function (event) {
        if (event.target.closest("label, button, a, input")) return;
        if (input) input.click();
      });
    }

    /* --- drag and drop --- */
    if (zone) {
      ["dragenter", "dragover"].forEach(function (type) {
        zone.addEventListener(type, function (event) {
          event.preventDefault();
          event.stopPropagation();
          zone.classList.add("is-dragover");
        });
      });
      ["dragleave", "drop"].forEach(function (type) {
        zone.addEventListener(type, function (event) {
          event.preventDefault();
          event.stopPropagation();
          if (type === "dragleave" && zone.contains(event.relatedTarget)) return;
          zone.classList.remove("is-dragover");
        });
      });
      zone.addEventListener("drop", function (event) {
        var files = event.dataTransfer && event.dataTransfer.files;
        if (!files || !files.length) return;
        try {
          // Mirror the dropped file into the real input so the form can submit it.
          input.files = files;
        } catch (err) {
          showError("This browser will not accept a dropped file directly" +
                    " — please use the Choose file button.");
          return;
        }
        acceptFile(files[0]);
      });
    }

    /* --- remove / clear --- */
    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        resetSelection();
        clearError();
        if (input) input.focus();
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        resetSelection();
        clearError();
      });
    }

    /* --- submit with real upload progress (XHR) --- */
    function setProgress(percent) {
      if (!progress || !progressFill || !progressText || !progressTrack) return;
      progress.hidden = false;
      progress.classList.remove("is-indeterminate");
      progressFill.style.width = percent + "%";
      progressTrack.setAttribute("aria-valuenow", String(percent));
      progressText.textContent = "Uploading… " + percent + "%";
    }

    function setIndeterminate() {
      if (!progress || !progressFill || !progressText || !progressTrack) return;
      progress.hidden = false;
      progress.classList.add("is-indeterminate");
      progressText.textContent = "Extracting text and running the model…";
    }

    function hideProgress() {
      if (progress) progress.hidden = true;
    }

    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        clearError();

        var file = selected || (input && input.files && input.files[0]) || null;
        if (!file) {
          if (zone) zone.classList.add("is-invalid");
          showError("Please choose a TXT, PDF or DOCX file before analyzing.");
          return;
        }

        var xhr = new XMLHttpRequest();
        xhr.open("POST", form.action);
        xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        xhr.responseType = "text";

        if (submitBtn) {
          submitBtn.classList.add("is-loading");
          submitBtn.setAttribute("aria-disabled", "true");
        }
        setProgress(0);

        xhr.upload.addEventListener("progress", function (event) {
          if (event.lengthComputable && event.total > 0) {
            setProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
            if (event.loaded === event.total) setIndeterminate();
          } else {
            setIndeterminate();
          }
        });

        xhr.addEventListener("load", function () {
          hideProgress();
          if (submitBtn) {
            submitBtn.classList.remove("is-loading");
            submitBtn.removeAttribute("aria-disabled");
          }
          if (xhr.status >= 200 && xhr.status < 400 && xhr.responseText) {
            try {
              // Render the server's real response (result page or friendly
              // error) exactly as a normal form submission would.
              document.open();
              document.write(xhr.responseText);
              document.close();
              window.history.replaceState(null, "", form.action);
            } catch (err) {
              form.submit(); // graceful fallback
            }
          } else {
            showError("The upload could not be processed (HTTP " + xhr.status +
                      "). Please try again.");
          }
        });

        xhr.addEventListener("error", function () {
          hideProgress();
          if (submitBtn) {
            submitBtn.classList.remove("is-loading");
            submitBtn.removeAttribute("aria-disabled");
          }
          showError("Network error while uploading. Please check your connection and try again.");
        });

        xhr.send(new FormData(form));
      });
    }

    // Restore the button if the page returns from the back/forward cache.
    window.addEventListener("pageshow", function () {
      if (submitBtn) {
        submitBtn.classList.remove("is-loading");
        submitBtn.removeAttribute("aria-disabled");
      }
      hideProgress();
    });

    updateSubmitState();
  }

  /* ====================================================================
     News feed — live filtering of the cards rendered on this page
     (the form and category links still perform the authoritative
     server-side filter, so the page works without JavaScript too)
  ==================================================================== */
  function initFeed() {
    var grid = document.getElementById("feedGrid");
    var input = document.getElementById("feedQuery");
    if (!grid || !input) return;

    var cards = grid.querySelectorAll(".news-card");
    if (!cards.length) return;

    var countEl = document.querySelector(".feed-count");
    var originalCount = countEl ? countEl.textContent : "";
    var emptyEl = null;

    function ensureEmpty(visible) {
      if (visible > 0) {
        if (emptyEl && emptyEl.parentNode) emptyEl.parentNode.removeChild(emptyEl);
        emptyEl = null;
        return;
      }
      if (!emptyEl) {
        emptyEl = document.createElement("div");
        emptyEl.className = "alert alert-info";
        emptyEl.setAttribute("role", "status");
        var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        icon.setAttribute("class", "icon");
        icon.setAttribute("aria-hidden", "true");
        var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", "#i-search");
        icon.appendChild(use);
        var text = document.createElement("div");
        emptyEl.appendChild(icon);
        emptyEl.appendChild(text);
        grid.parentNode.insertBefore(emptyEl, grid.nextSibling);
      }
      emptyEl.lastChild.textContent =
        "No cards on this page match your filter. Press Search to check the full feed.";
    }

    function apply() {
      var query = (input.value || "").trim().toLowerCase();
      var visible = 0;
      Array.prototype.forEach.call(cards, function (card) {
        var haystack = (card.textContent || "").toLowerCase();
        var show = !query || haystack.indexOf(query) !== -1;
        card.hidden = !show;
        if (show) visible++;
      });

      ensureEmpty(visible);

      if (countEl) {
        if (query) {
          countEl.textContent = "Showing " + visible + " card" +
            (visible === 1 ? "" : "s") + " on this page matching “" +
            input.value.trim() + "”";
        } else {
          countEl.textContent = originalCount;
        }
      }
    }

    var timer = null;
    input.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(apply, 140);
    });

    var form = input.form;
    if (form) {
      form.addEventListener("submit", function () {
        window.clearTimeout(timer); // let the server do the authoritative filter
      });
    }
  }

  /* ====================================================================
     AI News Assistant — chat UI (rule-based replies from the server)
  ==================================================================== */
  function initAssistant() {
    var form = document.getElementById("assistantForm");
    if (!form) return;

    var input = document.getElementById("assistantInput");
    var messages = document.getElementById("chatMessages");
    var sendBtn = document.getElementById("chatSendBtn");
    var errorBox = document.getElementById("chatErrors");

    function showError(message) {
      if (!errorBox) return;
      errorBox.textContent = "";
      var row = document.createElement("div");
      row.className = "alert alert-error";
      var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("class", "icon");
      icon.setAttribute("aria-hidden", "true");
      var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", "#i-alert");
      icon.appendChild(use);
      var text = document.createElement("div");
      text.textContent = message;
      row.appendChild(icon);
      row.appendChild(text);
      errorBox.appendChild(row);
      errorBox.hidden = false;
    }

    function clearError() {
      if (!errorBox) return;
      errorBox.textContent = "";
      errorBox.hidden = true;
    }

    function scrollToEnd() {
      if (messages) messages.scrollTop = messages.scrollHeight;
    }

    function addMessage(text, who) {
      if (!messages) return null;
      var wrap = document.createElement("div");
      wrap.className = "chat-msg " + who;

      if (who === "bot") {
        var avatar = document.createElement("span");
        avatar.className = "msg-avatar";
        avatar.setAttribute("aria-hidden", "true");
        var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        icon.setAttribute("class", "icon");
        var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", "#i-spark");
        icon.appendChild(use);
        avatar.appendChild(icon);
        wrap.appendChild(avatar);
      }

      var bubble = document.createElement("div");
      bubble.className = "msg-bubble";
      var para = document.createElement("p");
      para.textContent = text; // plain text, never HTML
      bubble.appendChild(para);
      wrap.appendChild(bubble);
      messages.appendChild(wrap);
      scrollToEnd();
      return wrap;
    }

    var typingEl = null;

    function showTyping() {
      if (!messages) return;
      typingEl = document.createElement("div");
      typingEl.className = "chat-msg bot";
      var avatar = document.createElement("span");
      avatar.className = "msg-avatar";
      avatar.setAttribute("aria-hidden", "true");
      var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      icon.setAttribute("class", "icon");
      var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", "#i-spark");
      icon.appendChild(use);
      avatar.appendChild(icon);
      var bubble = document.createElement("div");
      bubble.className = "msg-bubble";
      var dots = document.createElement("span");
      dots.className = "typing";
      dots.setAttribute("aria-label", "Assistant is typing");
      for (var i = 0; i < 3; i++) dots.appendChild(document.createElement("span"));
      bubble.appendChild(dots);
      typingEl.appendChild(avatar);
      typingEl.appendChild(bubble);
      messages.appendChild(typingEl);
      scrollToEnd();
    }

    function hideTyping() {
      if (typingEl && typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);
      typingEl = null;
    }

    function send(text) {
      text = (text || "").trim();
      if (!text) {
        showError("Please enter a message before sending.");
        if (input) input.focus();
        return;
      }
      if (text.length > 6000) {
        showError("Message is too long. Please limit it to 6,000 characters.");
        return;
      }

      clearError();
      addMessage(text, "user");
      if (input) input.value = "";
      if (sendBtn) {
        sendBtn.classList.add("is-loading");
        sendBtn.setAttribute("aria-disabled", "true");
      }
      showTyping();

      fetch(form.action, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ message: text })
      })
        .then(function (response) {
          return response.json().catch(function () { return null; }).then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          hideTyping();
          if (!result.ok || !result.data || result.data.error) {
            showError(result.data && result.data.error
              ? result.data.error
              : "The assistant could not process that message. Please try again.");
            return;
          }
          addMessage(result.data.reply, "bot");
        })
        .catch(function () {
          hideTyping();
          showError("Network error — could not reach the assistant. Please try again.");
        })
        .then(function () {
          if (sendBtn) {
            sendBtn.classList.remove("is-loading");
            sendBtn.removeAttribute("aria-disabled");
          }
        });
    }

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      send(input ? input.value : "");
    });

    if (input) {
      input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
          event.preventDefault();
          send(input.value);
        }
      });
    }

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-prompt]"),
      function (chip) {
        chip.addEventListener("click", function () {
          send(chip.getAttribute("data-prompt"));
        });
      }
    );

    // A no-JS fallback reply may already be in the log — jump to it. On a
    // fresh load keep the opening message visible from the first line
    // (scrolling to the bottom would clip it on short viewports).
    if (document.querySelector("#chatMessages .chat-msg.user")) scrollToEnd();
    else if (messages) messages.scrollTop = 0;
  }

  /* ====================================================================
     Register the upgrade initializers alongside the core ones
  ==================================================================== */
  function initUpgrade() {
    initParticles();
    initCountUp();
    initGlassGlow();
    initWorkflow();
    initUpload();
    initFeed();
    initAssistant();
  }
})();
