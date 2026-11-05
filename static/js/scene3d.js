/* ==========================================================================
   scene3d.js — premium 3D experience (Three.js, loaded on demand)
   ---------------------------------------------------------------------------
   Renders the decorative WebGL scenes declared in the templates:

       data-scene="neural"   homepage hero — holographic neural network
       data-scene="scanner"  /detect hero  — holographic news scanner rings
       data-scene="panels"   /compare hero — floating article panels
       data-scene="bars"     /analytics   — floating statistic bars

   Design rules honoured here:
     - Three.js is downloaded ONLY when a scene container with real size is
       present, so pages stay fast and other pages never pay for it.
     - Electric blue (#38BDF8) / indigo (#6366F1) lighting only.
     - WebGL failure, an unsupported browser or prefers-reduced-motion keep
       the CSS fallback visible instead (nothing breaks, nothing fakes it).
     - Rendering pauses off-screen and in background tabs; device pixel ratio
       is capped so phones stay smooth.
     - Mouse parallax is subtle and disabled for touch / reduced motion.

   No prediction, statistics or application logic lives in this file.
   ========================================================================== */

(function () {
  "use strict";

  var ACCENT = 0x38bdf8;   /* electric blue */
  var ACCENT_2 = 0x6366f1; /* indigo */
  var DPR_CAP = 1.75;

  var reduceMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var threePromise = null;

  /* ---------------------------------------------------------------------
     WebGL capability probe (never throws)
  --------------------------------------------------------------------- */
  function webglAvailable() {
    try {
      var canvas = document.createElement("canvas");
      return !!(
        window.WebGLRenderingContext &&
        (canvas.getContext("webgl2") || canvas.getContext("webgl"))
      );
    } catch (e) {
      return false;
    }
  }

  /* ---------------------------------------------------------------------
     On-demand Three.js loader. The URL is derived from this script's own
     src so it keeps working under any mount path / port.
  --------------------------------------------------------------------- */
  function threeUrl() {
    var scripts = document.getElementsByTagName("script");
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].src || "";
      if (/scene3d\.js(\?|$)/.test(src)) {
        return src.replace(/js\/scene3d\.js(\?.*)?$/, "js/vendor/three.min.js");
      }
    }
    return "/static/js/vendor/three.min.js";
  }

  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    if (!threePromise) {
      threePromise = new Promise(function (resolve, reject) {
        var script = document.createElement("script");
        script.src = threeUrl();
        script.async = true;
        script.onload = function () {
          if (window.THREE) resolve(window.THREE);
          else reject(new Error("three.js loaded without a global THREE"));
        };
        script.onerror = function () {
          reject(new Error("three.js could not be downloaded"));
        };
        document.head.appendChild(script);
      });
    }
    return threePromise;
  }

  /* =====================================================================
     Scene builders — each returns { group, update(t), resize(w, h) }
     ===================================================================== */

  function buildNeural(THREE, w, h) {
    var group = new THREE.Group();
    var small = w < 640;
    var count = small ? 110 : 200;
    var radius = 1.55;

    /* Fibonacci sphere keeps the point cloud evenly distributed. */
    var points = [];
    var golden = Math.PI * (3 - Math.sqrt(5));
    for (var i = 0; i < count; i++) {
      var y = 1 - (i / (count - 1)) * 2;
      var r = Math.sqrt(Math.max(0, 1 - y * y));
      var theta = golden * i;
      points.push(
        new THREE.Vector3(Math.cos(theta) * r * radius, y * radius, Math.sin(theta) * r * radius)
      );
    }

    var pos = new Float32Array(count * 3);
    points.forEach(function (p, idx) {
      pos[idx * 3] = p.x;
      pos[idx * 3 + 1] = p.y;
      pos[idx * 3 + 2] = p.z;
    });

    var cloudGeo = new THREE.BufferGeometry();
    cloudGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    var cloud = new THREE.Points(
      cloudGeo,
      new THREE.PointsMaterial({
        color: ACCENT,
        size: 0.055,
        transparent: true,
        opacity: 0.9,
        sizeAttenuation: true,
      })
    );
    group.add(cloud);

    /* Connect near neighbours once, capped so the line count stays cheap. */
    var linePts = [];
    var maxLines = small ? 160 : 340;
    var threshold = radius * 0.62;
    var lines = 0;
    for (var a = 0; a < count && lines < maxLines; a++) {
      for (var b = a + 1; b < count && lines < maxLines; b++) {
        if (points[a].distanceTo(points[b]) < threshold) {
          linePts.push(points[a].x, points[a].y, points[a].z);
          linePts.push(points[b].x, points[b].y, points[b].z);
          lines++;
        }
      }
    }
    var lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(linePts), 3));
    var net = new THREE.LineSegments(
      lineGeo,
      new THREE.LineBasicMaterial({
        color: ACCENT_2,
        transparent: true,
        opacity: 0.32,
      })
    );
    group.add(net);

    return {
      group: group,
      update: function (t) {
        group.rotation.y = t * 0.12;
        group.rotation.x = Math.sin(t * 0.25) * 0.14;
      },
    };
  }

  function buildScanner(THREE, w, h) {
    var group = new THREE.Group();

    /* Three scanning rings on different axes. */
    var ringSpecs = [
      { r: 1.25, color: ACCENT, speed: 0.5, tilt: 0.0 },
      { r: 0.98, color: ACCENT_2, speed: -0.7, tilt: Math.PI / 3 },
      { r: 0.74, color: 0xe2f4ff, speed: 0.95, tilt: -Math.PI / 4 },
    ];
    var rings = ringSpecs.map(function (spec) {
      var mesh = new THREE.Mesh(
        new THREE.TorusGeometry(spec.r, 0.014, 10, 120),
        new THREE.MeshBasicMaterial({
          color: spec.color,
          transparent: true,
          opacity: 0.85,
        })
      );
      mesh.rotation.x = Math.PI / 2 + spec.tilt;
      mesh.userData.speed = spec.speed;
      group.add(mesh);
      return mesh;
    });

    /* Holographic "document" core. */
    var doc = new THREE.Mesh(
      new THREE.BoxGeometry(0.92, 1.24, 0.06),
      new THREE.MeshBasicMaterial({
        color: ACCENT,
        transparent: true,
        opacity: 0.1,
        wireframe: false,
      })
    );
    group.add(doc);

    var docWire = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(0.92, 1.24, 0.06)),
      new THREE.LineBasicMaterial({ color: ACCENT, transparent: true, opacity: 0.75 })
    );
    group.add(docWire);

    /* Scanning beam sweeping vertically over the document. */
    var beam = new THREE.Mesh(
      new THREE.BoxGeometry(1.06, 0.08, 0.14),
      new THREE.MeshBasicMaterial({
        color: 0x9ff0ff,
        transparent: true,
        opacity: 0.85,
      })
    );
    group.add(beam);

    return {
      group: group,
      update: function (t) {
        rings.forEach(function (ring, i) {
          ring.rotation.z = t * ring.userData.speed;
          ring.rotation.y = Math.sin(t * 0.4 + i) * 0.35;
        });
        var sweep = Math.sin(t * 0.85);
        beam.position.y = sweep * 0.62;
        doc.material.opacity = 0.08 + Math.abs(sweep) * 0.06;
        group.rotation.y = Math.sin(t * 0.3) * 0.3;
      },
    };
  }

  function buildPanels(THREE, w, h) {
    var group = new THREE.Group();

    function makePanel(color) {
      var panel = new THREE.Group();
      var fill = new THREE.Mesh(
        new THREE.BoxGeometry(1.15, 1.5, 0.05),
        new THREE.MeshBasicMaterial({
          color: color,
          transparent: true,
          opacity: 0.12,
        })
      );
      var edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(1.15, 1.5, 0.05)),
        new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.9 })
      );
      panel.add(fill);
      panel.add(edges);

      /* Content lines floating inside each panel. */
      var lineMat = new THREE.LineBasicMaterial({ color: 0xd7e3f4, transparent: true, opacity: 0.5 });
      for (var i = 0; i < 4; i++) {
        var y = 0.42 - i * 0.26;
        var width = i % 2 === 0 ? 0.8 : 0.62;
        var geo = new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-width / 2, y, 0.03),
          new THREE.Vector3(width / 2, y, 0.03),
        ]);
        panel.add(new THREE.Line(geo, lineMat));
      }
      return panel;
    }

    var panelA = makePanel(ACCENT);
    var panelB = makePanel(ACCENT_2);
    panelA.position.x = -0.85;
    panelB.position.x = 0.85;
    panelA.rotation.y = 0.42;
    panelB.rotation.y = -0.42;
    group.add(panelA);
    group.add(panelB);

    /* Dashed-looking link between the two panels. */
    var linkGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-0.28, 0, 0),
      new THREE.Vector3(0.28, 0, 0),
    ]);
    var link = new THREE.Line(
      linkGeo,
      new THREE.LineDashedMaterial({
        color: 0x9ff0ff,
        dashSize: 0.07,
        gapSize: 0.05,
        transparent: true,
        opacity: 0.85,
      })
    );
    link.computeLineDistances();
    group.add(link);

    return {
      group: group,
      update: function (t) {
        panelA.position.y = Math.sin(t * 0.9) * 0.12;
        panelB.position.y = Math.sin(t * 0.9 + Math.PI) * 0.12;
        panelA.rotation.y = 0.42 + Math.sin(t * 0.5) * 0.1;
        panelB.rotation.y = -0.42 - Math.sin(t * 0.5 + 1.2) * 0.1;
        link.position.y = Math.sin(t * 0.9 + Math.PI / 2) * 0.05;
        group.rotation.y = Math.sin(t * 0.3) * 0.16;
      },
    };
  }

  function buildBars(THREE, w, h) {
    var group = new THREE.Group();
    var heights = [0.9, 1.7, 1.2, 2.1, 1.05];
    var bars = heights.map(function (height, i) {
      var mesh = new THREE.Mesh(
        new THREE.BoxGeometry(0.34, height, 0.34),
        new THREE.MeshBasicMaterial({
          color: i % 2 === 0 ? ACCENT : ACCENT_2,
          transparent: true,
          opacity: 0.75,
        })
      );
      mesh.position.x = (i - 2) * 0.55;
      mesh.position.y = height / 2 - 1.05;
      mesh.userData.baseY = mesh.position.y;
      mesh.userData.phase = i * 0.7;
      group.add(mesh);

      var cap = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(0.34, height, 0.34)),
        new THREE.LineBasicMaterial({ color: 0xe2f4ff, transparent: true, opacity: 0.55 })
      );
      cap.position.copy(mesh.position);
      mesh.userData.cap = cap;
      group.add(cap);
      return mesh;
    });

    group.rotation.x = -0.18;

    return {
      group: group,
      update: function (t) {
        bars.forEach(function (bar) {
          var lift = Math.sin(t * 1.1 + bar.userData.phase) * 0.08;
          bar.position.y = bar.userData.baseY + lift;
          if (bar.userData.cap) bar.userData.cap.position.y = bar.position.y;
        });
        group.rotation.y = Math.sin(t * 0.35) * 0.3;
      },
    };
  }

  var BUILDERS = {
    neural: buildNeural,
    scanner: buildScanner,
    panels: buildPanels,
    bars: buildBars,
  };

  /* =====================================================================
     Renderer lifecycle for one container
     ===================================================================== */
  function initScene(container, type) {
    var builder = BUILDERS[type];
    if (!builder) return;

    /* Zero-sized containers (hidden by CSS on phones) keep the fallback. */
    if (!container.clientWidth || !container.clientHeight) return;

    loadThree()
      .then(function (THREE) {
        if (!webglAvailable() || reduceMotion) return;
        if (!container.isConnected || !container.clientWidth) return;

        var width = container.clientWidth;
        var height = container.clientHeight;

        var renderer;
        try {
          renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: width > 640,
            powerPreference: "low-power",
          });
        } catch (e) {
          return; /* CSS fallback stays visible */
        }

        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, DPR_CAP));
        renderer.setSize(width, height, false);
        renderer.domElement.setAttribute("aria-hidden", "true");
        container.appendChild(renderer.domElement);

        var scene = new THREE.Scene();
        var camera = new THREE.PerspectiveCamera(46, width / height, 0.1, 40);
        camera.position.set(0, 0, 4.4);

        var built = builder(THREE, width, height);
        scene.add(built.group);

        /* Hide the CSS fallback only once real frames are flowing. */
        container.classList.add("scene--webgl");

        /* --- mouse parallax (desktop pointers only) --- */
        var targetX = 0;
        var targetY = 0;
        var pointerFine =
          window.matchMedia && window.matchMedia("(pointer: fine)").matches;
        var onMove = null;
        if (pointerFine) {
          onMove = function (event) {
            var rect = container.getBoundingClientRect();
            if (!rect.width || !rect.height) return;
            var nx = (event.clientX - rect.left) / rect.width - 0.5;
            var ny = (event.clientY - rect.top) / rect.height - 0.5;
            /* Only react when the pointer is reasonably near the scene. */
            if (Math.abs(nx) > 1.4 || Math.abs(ny) > 1.4) return;
            targetY = nx * 0.5;
            targetX = ny * 0.35;
          };
          window.addEventListener("mousemove", onMove, { passive: true });
        }

        /* --- render only while visible & the tab is active --- */
        var inView = true;
        var rafId = null;
        var start = performance.now();

        if (window.IntersectionObserver) {
          var io = new IntersectionObserver(
            function (entries) {
              inView = entries[0].isIntersecting;
              schedule();
            },
            { threshold: 0.02 }
          );
          io.observe(container);
        }

        function frame(now) {
          rafId = null;
          if (!inView || document.hidden) return;
          var t = (now - start) / 1000;

          built.update(t);

          /* Ease the camera toward the parallax target. */
          camera.position.x += (targetY * 0.9 - camera.position.x) * 0.05;
          camera.position.y += (-targetX * 0.7 - camera.position.y) * 0.05;
          camera.lookAt(0, 0, 0);

          renderer.render(scene, camera);
          schedule();
        }

        function schedule() {
          if (rafId === null && inView && !document.hidden) {
            rafId = requestAnimationFrame(frame);
          }
        }

        function onVisibility() {
          if (!document.hidden) schedule();
        }
        document.addEventListener("visibilitychange", onVisibility);

        /* --- responsive sizing --- */
        var resizeTimer = null;
        var onResize = function () {
          clearTimeout(resizeTimer);
          resizeTimer = setTimeout(function () {
            if (!container.clientWidth || !container.clientHeight) return;
            var w = container.clientWidth;
            var h = container.clientHeight;
            camera.aspect = w / h;
            camera.updateProjectionMatrix();
            renderer.setSize(w, h, false);
          }, 160);
        };
        if (window.ResizeObserver) {
          new ResizeObserver(onResize).observe(container);
        } else {
          window.addEventListener("resize", onResize, { passive: true });
        }

        schedule();

        /* Best-effort cleanup if the page ever swaps DOM around. */
        container._scene3dDispose = function () {
          document.removeEventListener("visibilitychange", onVisibility);
          if (onMove) window.removeEventListener("mousemove", onMove);
          if (rafId !== null) cancelAnimationFrame(rafId);
          renderer.dispose();
        };
      })
      .catch(function () {
        /* three.js unavailable — the CSS fallback simply stays visible. */
      });
  }

  /* =====================================================================
     CSS 3D tilt for cards ([data-tilt]) — desktop pointers only
     ===================================================================== */
  function initTilt() {
    if (reduceMotion) return;
    if (!window.matchMedia || !window.matchMedia("(pointer: fine)").matches) return;

    var cards = document.querySelectorAll("[data-tilt]");
    Array.prototype.forEach.call(cards, function (card) {
      card.addEventListener(
        "mousemove",
        function (event) {
          var rect = card.getBoundingClientRect();
          if (!rect.width || !rect.height) return;
          var nx = (event.clientX - rect.left) / rect.width - 0.5;
          var ny = (event.clientY - rect.top) / rect.height - 0.5;
          card.style.transform =
            "perspective(760px) rotateX(" +
            (-ny * 7).toFixed(2) +
            "deg) rotateY(" +
            (nx * 8).toFixed(2) +
            "deg)";
        },
        { passive: true }
      );
      card.addEventListener(
        "mouseleave",
        function () {
          card.style.transform = "";
        },
        { passive: true }
      );
    });
  }

  /* =====================================================================
     3D microphone tilt on the voice dock (CSS vars consumed by style.css)
     ===================================================================== */
  function initMicTilt() {
    if (reduceMotion) return;
    if (!window.matchMedia || !window.matchMedia("(pointer: fine)").matches) return;

    var stage = document.querySelector(".vd-stage");
    var mic = document.getElementById("vdMic");
    if (!stage || !mic) return;

    stage.addEventListener(
      "mousemove",
      function (event) {
        var rect = mic.getBoundingClientRect();
        if (!rect.width) return;
        var nx = (event.clientX - (rect.left + rect.width / 2)) / rect.width;
        var ny = (event.clientY - (rect.top + rect.height / 2)) / rect.height;
        nx = Math.max(-1, Math.min(1, nx));
        ny = Math.max(-1, Math.min(1, ny));
        mic.style.setProperty("--tilt-y", (nx * 14).toFixed(1) + "deg");
        mic.style.setProperty("--tilt-x", (-ny * 14).toFixed(1) + "deg");
      },
      { passive: true }
    );
    stage.addEventListener(
      "mouseleave",
      function () {
        mic.style.setProperty("--tilt-y", "0deg");
        mic.style.setProperty("--tilt-x", "0deg");
      },
      { passive: true }
    );
  }

  /* ---------------------------------------------------------------------
     Boot
  --------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    initTilt();
    initMicTilt();

    var containers = document.querySelectorAll("[data-scene]");
    if (!containers.length) return;

    /* If WebGL or motion preferences rule it out, keep CSS fallbacks only. */
    if (!webglAvailable() || reduceMotion) return;

    Array.prototype.forEach.call(containers, function (container) {
      initScene(container, container.getAttribute("data-scene"));
    });
  });
})();
