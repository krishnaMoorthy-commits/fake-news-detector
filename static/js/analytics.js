/* ==========================================================================
   analytics.js — Intelligence Analytics dashboard
   ---------------------------------------------------------------------------
   Animated counters and two charts (prediction distribution + weekly
   activity). The data comes from the JSON block the server rendered from
   THIS browser session's real predictions (see analytics.html) — no sample
   or fabricated values exist anywhere in this file. Chart.js is vendored
   locally and only loaded on this page; if it fails to load, a readable
   text summary replaces the charts instead of leaving blank canvases.
   ========================================================================== */

(function () {
  "use strict";

  var reduceMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function readData() {
    var block = document.getElementById("analyticsData");
    if (!block) return null;
    try {
      return JSON.parse(block.textContent);
    } catch (e) {
      return null;
    }
  }

  /* ---------------------------------------------------------------------
     Animated counters ([data-count]) — reduced motion jumps to the value
  --------------------------------------------------------------------- */
  function animateCounters() {
    var nodes = document.querySelectorAll("[data-count]");
    Array.prototype.forEach.call(nodes, function (node) {
      var target = parseInt(node.getAttribute("data-count"), 10);
      if (isNaN(target)) target = 0;

      if (reduceMotion || target === 0) {
        node.textContent = String(target);
        return;
      }

      var duration = 1100;
      var start = null;

      function step(now) {
        if (start === null) start = now;
        var progress = Math.min((now - start) / duration, 1);
        /* easeOutCubic — fast start, gentle settle */
        var eased = 1 - Math.pow(1 - progress, 3);
        node.textContent = String(Math.round(target * eased));
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  }

  /* ---------------------------------------------------------------------
     Charts (Chart.js — vendored at static/js/vendor/chart.umd.min.js)
  --------------------------------------------------------------------- */
  var GRID = "rgba(148, 163, 184, 0.14)";
  var TEXT = "#A7B4C8";
  var REAL = "#4ADE80";
  var FAKE = "#F87171";
  var CYAN = "#38BDF8";
  var INDIGO = "#818CF8";

  function chartFont() {
    return (
      getComputedStyle(document.documentElement).getPropertyValue("--font") ||
      "system-ui, sans-serif"
    );
  }

  function replaceWithMessage(canvas, message) {
    var note = document.createElement("p");
    note.className = "field-hint";
    note.setAttribute("role", "status");
    note.textContent = message;
    if (canvas && canvas.parentNode) {
      canvas.parentNode.replaceChild(note, canvas);
    }
  }

  function renderDistribution(data) {
    var canvas = document.getElementById("distChart");
    if (!canvas || !window.Chart) return;

    var dist = data.distribution || { REAL: 0, FAKE: 0 };
    var total = (dist.REAL || 0) + (dist.FAKE || 0);
    if (!total) return;

    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["REAL", "FAKE"],
        datasets: [
          {
            data: [dist.REAL || 0, dist.FAKE || 0],
            backgroundColor: [REAL, FAKE],
            borderColor: "rgba(8, 13, 26, 0.9)",
            borderWidth: 3,
            hoverOffset: 10,
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "64%",
        animation: reduceMotion ? false : { duration: 900, easing: "easeOutQuart" },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(13, 21, 40, 0.96)",
            borderColor: GRID,
            borderWidth: 1,
            titleColor: "#F8FAFC",
            bodyColor: TEXT,
            padding: 10,
            displayColors: true,
            callbacks: {
              label: function (ctx) {
                var pct = total ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                return " " + ctx.label + ": " + ctx.parsed + " (" + pct + "%)";
              },
            },
          },
        },
      },
    });
  }

  function renderWeekly(data) {
    var canvas = document.getElementById("weekChart");
    if (!canvas || !window.Chart) return;

    var weekly = data.weekly || [];
    if (!weekly.length) return;

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: weekly.map(function (d) {
          return d.day;
        }),
        datasets: [
          {
            label: "Analyses",
            data: weekly.map(function (d) {
              return d.count;
            }),
            backgroundColor: function (ctx) {
              var chart = ctx.chart;
              var area = chart.chartArea;
              if (!area) return CYAN;
              var gradient = chart.ctx.createLinearGradient(0, area.bottom, 0, area.top);
              gradient.addColorStop(0, "rgba(99, 102, 241, 0.55)");
              gradient.addColorStop(1, "rgba(56, 189, 248, 0.95)");
              return gradient;
            },
            borderRadius: 8,
            borderSkipped: false,
            maxBarThickness: 42,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: reduceMotion ? false : { duration: 900, easing: "easeOutQuart" },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "rgba(13, 21, 40, 0.96)",
            borderColor: GRID,
            borderWidth: 1,
            titleColor: "#F8FAFC",
            bodyColor: TEXT,
            padding: 10,
            callbacks: {
              label: function (ctx) {
                var n = ctx.parsed.y;
                return " " + n + (n === 1 ? " analysis" : " analyses");
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: GRID, drawBorder: false },
            ticks: { color: TEXT, font: { family: chartFont(), size: 12 } },
          },
          y: {
            beginAtZero: true,
            suggestedMax: 4,
            ticks: {
              color: TEXT,
              precision: 0,
              stepSize: 1,
              font: { family: chartFont(), size: 12 },
            },
            grid: { color: GRID, drawBorder: false },
          },
        },
      },
    });
  }

  /* ---------------------------------------------------------------------
     Boot
  --------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    var data = readData();
    animateCounters();

    if (!data || !data.hasHistory) return;

    if (typeof window.Chart === "undefined") {
      var distCanvas = document.getElementById("distChart");
      var weekCanvas = document.getElementById("weekChart");
      if (distCanvas) {
        replaceWithMessage(
          distCanvas,
          "The chart library could not be loaded, so a text summary is shown instead: " +
            data.stats.real +
            " REAL and " +
            data.stats.fake +
            " FAKE labels in this session."
        );
      }
      if (weekCanvas) {
        replaceWithMessage(
          weekCanvas,
          "The chart library could not be loaded, so the weekly activity chart is unavailable. " +
            "The exact figures remain in your recent activity list below."
        );
      }
      return;
    }

    renderDistribution(data);
    renderWeekly(data);
  });
})();
