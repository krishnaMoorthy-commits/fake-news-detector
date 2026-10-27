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
})();
