/* ==========================================================================
   compare.js — News Comparison Lab interface
   ---------------------------------------------------------------------------
   Client-side behaviour ONLY: validation, the loading state, "clear all",
   and building a downloadable report from the results already rendered by
   the server. Every number in the report comes from the DOM the Flask
   backend produced after running the real model — nothing is invented here.
   ========================================================================== */

(function () {
  "use strict";

  var MAX_CHARS = 10000;

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("compareForm");
    if (!form) return;

    var btn = document.getElementById("compareBtn");
    var clearBtn = document.getElementById("compareClear");
    var downloadBtn = document.getElementById("downloadReport");

    var fields = {
      headlineA: document.getElementById("headlineA"),
      articleA: document.getElementById("articleA"),
      headlineB: document.getElementById("headlineB"),
      articleB: document.getElementById("articleB"),
    };

    /* ------------------------------------------------------------------
       Inline error helpers (never alert())
    ------------------------------------------------------------------ */
    function showError(message, target) {
      if (!target) return;
      target.textContent = message;
      target.hidden = false;
    }

    /* ------------------------------------------------------------------
       Validation — mirrors the server rules so users see feedback instantly
    ------------------------------------------------------------------ */
    function validate() {
      var a =
        ((fields.headlineA && fields.headlineA.value) || "").trim() +
        " " +
        ((fields.articleA && fields.articleA.value) || "").trim();
      var b =
        ((fields.headlineB && fields.headlineB.value) || "").trim() +
        " " +
        ((fields.articleB && fields.articleB.value) || "").trim();

      a = a.trim();
      b = b.trim();

      if (!a || !b) {
        return "Both Article A and Article B need a headline or article text before comparing.";
      }
      var fa =
        (fields.headlineA ? fields.headlineA.value.length : 0) +
        (fields.articleA ? fields.articleA.value.length : 0);
      var fb =
        (fields.headlineB ? fields.headlineB.value.length : 0) +
        (fields.articleB ? fields.articleB.value.length : 0);
      if (fa > MAX_CHARS || fb > MAX_CHARS) {
        return (
          "Each article is limited to " +
          MAX_CHARS.toLocaleString() +
          " characters including its headline."
        );
      }
      return null;
    }

    /* Server-rendered per-side errors are already visible; only intercept
       when we can improve the message before a round trip. */
    form.addEventListener("submit", function (event) {
      var problem = validate();
      if (problem) {
        /* Let the server render its own consistent error page for malformed
           input, but still show the loading state only for valid posts. */
        var aEmpty =
          !((fields.headlineA && fields.headlineA.value.trim()) ||
            (fields.articleA && fields.articleA.value.trim()));
        var bEmpty =
          !((fields.headlineB && fields.headlineB.value.trim()) ||
            (fields.articleB && fields.articleB.value.trim()));
        if (aEmpty || bEmpty) {
          event.preventDefault();
          var side = aEmpty ? fields.articleA : fields.articleB;
          if (side) side.focus();
          return;
        }
      }

      if (btn && !btn.dataset.modelMissing) {
        btn.classList.add("is-loading");
        btn.setAttribute("aria-disabled", "true");
      }
    });

    window.addEventListener("pageshow", function () {
      if (!btn) return;
      btn.classList.remove("is-loading");
      btn.removeAttribute("aria-disabled");
    });

    /* ------------------------------------------------------------------
       Clear all — empties both panels and returns to a clean state
    ------------------------------------------------------------------ */
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        Object.keys(fields).forEach(function (key) {
          if (fields[key]) fields[key].value = "";
        });
        /* Clear any client-side notes. */
        Array.prototype.forEach.call(
          form.querySelectorAll(".alert-error"),
          function (node) {
            node.hidden = true;
            node.textContent = "";
          }
        );
        if (fields.headlineA) fields.headlineA.focus();
      });
    }

    /* ------------------------------------------------------------------
       Download comparison report — assembled from the rendered results
    ------------------------------------------------------------------ */
    function buildReport() {
      var results = document.getElementById("compareResults");
      if (!results) return null;

      var lines = [];
      var rule = "=".repeat(60);

      lines.push("NEWS COMPARISON LAB — REPORT");
      lines.push("Generated: " + new Date().toLocaleString());
      lines.push(rule);
      lines.push("");

      function verdictText(prefix, card) {
        if (!card) return;
        var badge = card.querySelector(".badge");
        var label = badge
          ? badge.textContent.replace(/\s+/g, " ").trim()
          : "unknown";
        var summary = card.querySelector(".verdict-summary");
        var meter = card.querySelector(".meter-value");
        lines.push(prefix + " prediction : " + label);
        if (meter) lines.push(prefix + " confidence : " + meter.textContent.trim());
        if (summary) lines.push(prefix + " explanation: " + summary.textContent.trim());
        var warn = card.querySelector(".alert-warning div");
        if (warn) lines.push(prefix + " warning    : " + warn.textContent.replace(/\s+/g, " ").trim());
        lines.push("");
      }

      var cards = results.querySelectorAll(".cmp-verdict");
      verdictText("Article A", cards[0]);
      verdictText("Article B", cards[1]);

      var agreeTitle = results.querySelector(".cmp-agree-title");
      var agreeGap = results.querySelector(".cmp-agree-gap");
      lines.push("Label comparison: " + (agreeTitle ? agreeTitle.textContent.trim() : "n/a"));
      if (agreeGap) lines.push(agreeGap.textContent.replace(/\s+/g, " ").trim());
      lines.push("");

      var simValue = document.getElementById("simValue");
      var simList = results.querySelectorAll(".cmp-sim-list .meta-row");
      if (simValue || simList.length) {
        lines.push("WORD-LEVEL SIMILARITY (computed from the two texts)");
        if (simValue) lines.push("  Jaccard overlap: " + simValue.textContent.trim());
        Array.prototype.forEach.call(simList, function (row) {
          var dt = row.querySelector("dt");
          var dd = row.querySelector("dd");
          if (dt && dd) lines.push("  " + dt.textContent.trim() + ": " + dd.textContent.trim());
        });
        lines.push("");
      }

      var shared = results.querySelector(".cmp-chips-block .cmp-chips");
      if (shared) {
        lines.push("Shared words: " + shared.textContent.replace(/\s+/g, " ").trim());
        lines.push("");
      }

      var note = results.querySelector(".alert-warning[role='note'] div");
      if (note) {
        lines.push(rule);
        lines.push("INTERPRETATION NOTE");
        lines.push(note.textContent.replace(/\s+/g, " ").trim());
        lines.push("");
      }

      lines.push(rule);
      lines.push(
        "This report contains statistical model predictions produced by this application. " +
          "It is not a fact-check and does not verify claims against independent sources."
      );

      return lines.join("\n");
    }

    if (downloadBtn) {
      downloadBtn.addEventListener("click", function () {
        var report = buildReport();
        if (!report) {
          downloadBtn.disabled = true;
          return;
        }
        try {
          var blob = new Blob([report], { type: "text/plain;charset=utf-8" });
          var url = URL.createObjectURL(blob);
          var link = document.createElement("a");
          var stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
          link.href = url;
          link.download = "comparison-report-" + stamp + ".txt";
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          setTimeout(function () {
            URL.revokeObjectURL(url);
          }, 4000);
        } catch (e) {
          /* Downloading can be blocked (private mode, embedded webviews).
             Fall back to selecting the text so it can be copied by hand. */
          var pre = document.createElement("textarea");
          pre.value = report;
          document.body.appendChild(pre);
          pre.select();
          try {
            document.execCommand("copy");
            downloadBtn.textContent = "Report copied to clipboard instead";
          } catch (ignored) {
            /* Nothing else we can honestly do. */
          }
          document.body.removeChild(pre);
        }
      });
    }
  });
})();
