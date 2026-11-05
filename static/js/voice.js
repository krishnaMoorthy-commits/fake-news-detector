/* ==========================================================================
   voice.js — Premium AI Voice Intelligence System
   ---------------------------------------------------------------------------
   Real Web Speech API integration for the Fake News Detection platform:

     1. Voice-to-text dock on /detect   (SpeechRecognition -> the real form)
     2. Floating AI voice assistant     (chat + mic input + spoken replies)
     3. Multilingual support            (en-IN / ta-IN / hi-IN, shared state)
     4. Text-to-speech result player    (SpeechSynthesis with full controls)

   Design rules honoured here:
     - No external APIs and no API keys: everything runs in the browser and
       only talks to this Flask server for assistant replies.
     - Nothing is faked: unsupported features are detected at runtime and
       reported honestly with friendly messages.
     - All dynamic text is inserted with textContent (never innerHTML), so
       transcripts and replies are never interpreted as markup.
     - Animations respect prefers-reduced-motion.
   ========================================================================== */

(function () {
  "use strict";

  /* ---------------------------------------------------------------------
     Configuration & shared state
  --------------------------------------------------------------------- */
  var LANG_KEY = "fnd_voice_lang";
  var SPEAK_KEY = "fnd_speak_replies";
  var MAX_MESSAGE = 6000;             // matches the server-side limit
  var CHUNK_CHARS = 180;              // max characters per utterance
                                         // (Chrome drops very long ones)

  var LANGS = [
    { code: "en-IN", short: "English", prefix: "en" },
    { code: "ta-IN", short: "Tamil", prefix: "ta" },
    { code: "hi-IN", short: "Hindi", prefix: "hi" }
  ];

  var RecognitionCtor =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var synthAvailable =
    typeof window.speechSynthesis !== "undefined" &&
    typeof window.SpeechSynthesisUtterance !== "undefined";

  function $(id) {
    return document.getElementById(id);
  }

  function on(el, type, fn) {
    if (el) el.addEventListener(type, fn);
  }

  function reduceMotion() {
    return !!(window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function storeGet(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }

  function storeSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }

  function svgIcon(href) {
    var icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    icon.setAttribute("class", "icon");
    icon.setAttribute("aria-hidden", "true");
    var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", href);
    icon.appendChild(use);
    return icon;
  }

  /* Inline error reporter — plain text nodes only, never HTML. */
  function makeErrorReporter(box) {
    return function showError(message) {
      if (!box) return;
      box.textContent = "";
      var row = document.createElement("div");
      row.className = "alert alert-error";
      row.appendChild(svgIcon("#i-alert"));
      var text = document.createElement("div");
      text.textContent = message;
      row.appendChild(text);
      box.appendChild(row);
      box.hidden = false;
    };
  }

  function makeErrorClearer(box) {
    return function clearError() {
      if (!box) return;
      box.textContent = "";
      box.hidden = true;
    };
  }

  /* ---------------------------------------------------------------------
     Language state (shared by every dropdown on the page)
  --------------------------------------------------------------------- */
  var langListeners = [];
  var currentLang = (function () {
    var saved = storeGet(LANG_KEY);
    for (var i = 0; i < LANGS.length; i++) {
      if (LANGS[i].code === saved) return saved;
    }
    return "en-IN";
  })();

  function langInfo(code) {
    for (var i = 0; i < LANGS.length; i++) {
      if (LANGS[i].code === (code || currentLang)) return LANGS[i];
    }
    return LANGS[0];
  }

  function syncLangSelects() {
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-voice-lang]"),
      function (select) { select.value = currentLang; }
    );
  }

  function setLang(code) {
    var known = LANGS.some(function (l) { return l.code === code; });
    if (!known || code === currentLang) return;
    currentLang = code;
    storeSet(LANG_KEY, code);
    syncLangSelects();
    langListeners.forEach(function (fn) {
      try { fn(code); } catch (e) { /* one listener must not break the rest */ }
    });
  }

  function onLangChange(fn) {
    langListeners.push(fn);
  }

  function initLanguage() {
    syncLangSelects();
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-voice-lang]"),
      function (select) {
        on(select, "change", function () { setLang(select.value); });
      }
    );
    window.addEventListener("storage", function (event) {
      if (event && event.key === LANG_KEY) setLang(storeGet(LANG_KEY));
    });
  }

  /* ---------------------------------------------------------------------
     Honest capability messages
  --------------------------------------------------------------------- */
  function unsupportedRecognition() {
    return "Speech recognition is not available in this browser. " +
      "Use Chrome or Edge (desktop or Android), or type your text instead.";
  }

  function recognitionMessage(error, langShort) {
    switch (error) {
      case "not-allowed":
      case "service-not-allowed":
        return "Microphone access was blocked. Allow microphone permission " +
          "for this site in your browser's address bar, then start recording again.";
      case "audio-capture":
        return "No microphone was found. Connect a microphone (or enable " +
          "your device's microphone) and try again.";
      case "no-speech":
        return "No speech was detected. Please speak clearly and try again.";
      case "network":
        return "The speech recognition service is unreachable. Speech " +
          "recognition needs an internet connection in this browser — " +
          "check your connection, or type your text instead.";
      case "language-not-supported":
        return "This browser cannot recognize " + langShort + " speech. " +
          "Try Chrome or Edge, choose another language, or type your text instead.";
      default:
        return "Speech recognition failed" + (error ? " (" + error + ")" : "") +
          ". Please try again, or type your text instead.";
    }
  }

  /* ---------------------------------------------------------------------
     Animated waveform — CSS animation by default; when the microphone
     permission is granted it is driven by the real signal amplitude
     (Web Audio). Reduced-motion users get static bars, and environments
     without getUserMedia simply keep the CSS animation.
  --------------------------------------------------------------------- */
  function createWave(el, barCount, useMic) {
    if (!el) return null;
    var bars = [];
    el.textContent = "";
    for (var i = 0; i < barCount; i++) {
      var bar = document.createElement("span");
      bar.style.animationDelay = (i * 0.07).toFixed(2) + "s";
      el.appendChild(bar);
      bars.push(bar);
    }

    var stream = null, audioCtx = null, analyser = null, data = null, raf = null;
    var levels = [];
    for (var j = 0; j < barCount; j++) levels.push(4);

    function frame() {
      if (!analyser) return;
      analyser.getByteFrequencyData(data);
      for (var k = 0; k < bars.length; k++) {
        var bucket = data[k] || 0;
        var target = 4 + (bucket / 255) * 22;
        levels[k] = levels[k] + (target - levels[k]) * 0.35;
        bars[k].style.height = levels[k].toFixed(1) + "px";
      }
      raf = window.requestAnimationFrame(frame);
    }

    function teardownAudio() {
      if (raf !== null) { window.cancelAnimationFrame(raf); raf = null; }
      if (stream) {
        Array.prototype.forEach.call(stream.getTracks(), function (t) {
          try { t.stop(); } catch (e) { /* already stopped */ }
        });
        stream = null;
      }
      if (audioCtx) { try { audioCtx.close(); } catch (e) { /* noop */ } audioCtx = null; }
      analyser = null;
      el.classList.remove("is-live");
      Array.prototype.forEach.call(bars, function (b) { b.style.height = ""; });
    }

    return {
      start: function () {
        el.classList.add("is-active");
        if (!useMic || reduceMotion()) return;   // CSS bars (or static, if reduced motion)
        var getUserMedia = navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
        if (!getUserMedia) return;               // CSS animation fallback
        getUserMedia.call(navigator.mediaDevices, { audio: true })
          .then(function (s) {
            if (!el.classList.contains("is-active")) {
              Array.prototype.forEach.call(s.getTracks(), function (t) { t.stop(); });
              return;
            }
            stream = s;
            var Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return;
            audioCtx = new Ctx();
            var src = audioCtx.createMediaStreamSource(stream);
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = barCount * 2;
            data = new Uint8Array(analyser.frequencyBinCount);
            src.connect(analyser);
            el.classList.add("is-live");          // JS drives the bars now
            frame();
          })
          .catch(function () {
            /* No visualiser granted: the CSS waveform keeps animating. */
          });
      },
      stop: function () {
        el.classList.remove("is-active");
        teardownAudio();
      }
    };
  }

  /* ---------------------------------------------------------------------
     Recognition sessions — only one may listen at a time, and any active
     speech synthesis is stopped before listening begins (no feedback loop).
     The session auto-restarts after silence a few times, then reports an
     honest "no speech" outcome.
  --------------------------------------------------------------------- */
  var activeStop = null;

  function stopActiveRecognition() {
    if (activeStop) {
      var fn = activeStop;
      activeStop = null;
      fn();
    }
  }

  /**
   * Create a recognition session.
   *
   * handlers: { locale, short, onStart, onInterim(text), onFinal(fullText),
   *             onStatus(text), onError(text), onEnd(byUser) }
   *
   * Returns { stop: fn } or null when the feature is unavailable.
   */
  function createRecognitionSession(handlers) {
    if (!RecognitionCtor) {
      handlers.onError(unsupportedRecognition());
      handlers.onEnd(true);
      return null;
    }

    stopSpeech();   // never listen while speaking

    var rec = new RecognitionCtor();
    var wanted = true;
    var byUser = false;
    var done = false;
    var restarts = 0;
    var fatal = null;

    rec.lang = handlers.locale;
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    function release() {
      if (activeStop === api.stop) activeStop = null;
    }

    rec.onstart = function () {
      restarts = 0;
      if (handlers.onStart) handlers.onStart();
    };

    rec.onresult = function (event) {
      var interim = "";
      var complete = "";
      for (var i = 0; i < event.results.length; i++) {
        var res = event.results[i];
        var txt = res[0] && res[0].transcript ? res[0].transcript : "";
        if (res.isFinal) complete += txt + " ";
        else interim += txt;
      }
      if (handlers.onFinal) handlers.onFinal(complete.replace(/\s+/g, " ").trim());
      if (handlers.onInterim) handlers.onInterim(interim.replace(/\s+/g, " ").trim());
    };

    rec.onerror = function (event) {
      var err = event && event.error;
      if (!err) return;
      if (err === "aborted" && (byUser || !wanted)) return;
      if (err === "no-speech") {
        // Recoverable: Chrome ends the session after silence and onend
        // restarts it, so just surface the status.
        if (handlers.onStatus) handlers.onStatus(recognitionMessage("no-speech"));
        return;
      }
      fatal = recognitionMessage(err, handlers.short);
      wanted = false;
    };

    rec.onend = function () {
      if (done) return;
      if (wanted && !fatal && restarts < 6) {
        restarts += 1;
        try { rec.start(); return; } catch (e) { /* fall through */ }
      }
      if (wanted && !fatal) fatal = recognitionMessage("no-speech", handlers.short);
      done = true;
      release();
      if (fatal && handlers.onError) handlers.onError(fatal);
      if (handlers.onEnd) handlers.onEnd(byUser);
    };

    var api = {
      stop: function () {
        byUser = true;
        wanted = false;
        try { rec.stop(); } catch (e) { /* already stopped */ }
      }
    };

    activeStop = api.stop;
    try {
      rec.start();
    } catch (e) {
      release();
      handlers.onError(
        "The microphone could not be started. Make sure no other application " +
        "is using it, then try again.");
      handlers.onEnd(true);
      return null;
    }
    return api;
  }

  /* ---------------------------------------------------------------------
     Speech synthesis engine (shared by the assistant and the result player)
  --------------------------------------------------------------------- */
  var voices = [];
  var voiceListeners = [];

  function normalizeLang(l) {
    return String(l || "").toLowerCase().replace("_", "-");
  }

  function refreshVoices() {
    if (!synthAvailable) return;
    try {
      voices = (window.speechSynthesis.getVoices() || []).filter(function (v) {
        return v && v.lang;
      });
    } catch (e) {
      voices = [];
    }
    voiceListeners.forEach(function (fn) {
      try { fn(); } catch (e) { /* listener error must not break others */ }
    });
  }

  if (synthAvailable) {
    refreshVoices();
    if (typeof window.speechSynthesis.addEventListener === "function") {
      window.speechSynthesis.addEventListener("voiceschanged", refreshVoices);
    } else {
      window.speechSynthesis.onvoiceschanged = refreshVoices;
    }
    // Some browsers populate the voice list late and only once.
    window.setTimeout(refreshVoices, 800);
    window.setTimeout(refreshVoices, 2500);
  }

  function voicesForLocale(locale) {
    var info = langInfo(locale);
    var prefix = info.prefix;
    var exact = [], sameLanguage = [];
    voices.forEach(function (v) {
      var vl = normalizeLang(v.lang);
      if (vl === locale.toLowerCase()) exact.push(v);
      else if (vl === prefix || vl.indexOf(prefix + "-") === 0) sameLanguage.push(v);
    });
    return { exact: exact, sameLanguage: sameLanguage, all: exact.concat(sameLanguage) };
  }

  function pickVoice(locale, voiceURI) {
    if (voiceURI) {
      for (var i = 0; i < voices.length; i++) {
        if (voices[i].voiceURI === voiceURI) return voices[i];
      }
    }
    var m = voicesForLocale(locale);
    return m.exact[0] || m.sameLanguage[0] || null;
  }

  /** Honest, human description of voice availability for a locale. */
  function voiceNote(locale) {
    if (!synthAvailable) {
      return "Speech synthesis is not available in this browser — spoken output is disabled.";
    }
    if (!voices.length) {
      return "No speech voices are loaded yet — some browsers report voices only after the first playback.";
    }
    var info = langInfo(locale);
    var matches = voicesForLocale(locale).all;
    if (!matches.length) {
      return "No " + info.short + " voice is installed — the browser's default voice will be used.";
    }
    return matches.length + " " + info.short + " voice" +
      (matches.length === 1 ? "" : "s") + " available.";
  }

  function chunkText(text, max) {
    var words = String(text).split(/\s+/);
    var out = [], cur = "";
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (!w) continue;
      if (cur && (cur.length + 1 + w.length) > max) { out.push(cur); cur = w; }
      else cur = cur ? cur + " " + w : w;
    }
    if (cur) out.push(cur);
    return out;
  }

  var speech = {
    status: "idle",     // idle | speaking | paused
    chunks: [],
    index: 0,
    opts: null,
    pendingEnd: false
  };

  function notifySpeech() {
    if (speech.opts && typeof speech.opts.onState === "function") {
      try { speech.opts.onState(speech.status); } catch (e) { /* noop */ }
    }
  }

  function finishSpeech() {
    speech.status = "idle";
    speech.chunks = [];
    speech.index = 0;
    speech.pendingEnd = false;
    notifySpeech();
  }

  function advanceSpeech() {
    speech.index += 1;
    if (speech.index >= speech.chunks.length) finishSpeech();
    else window.setTimeout(playChunk, 0);
  }

  function playChunk() {
    var chunk = speech.chunks[speech.index];
    if (chunk === undefined) { finishSpeech(); return; }
    var opts = speech.opts || {};
    var utter = new window.SpeechSynthesisUtterance(chunk);
    var voice = pickVoice(opts.locale, opts.voiceURI);
    if (voice) utter.voice = voice;
    utter.lang = opts.locale || (voice ? voice.lang : "en-IN");
    if (opts.rate) utter.rate = parseFloat(opts.rate) || 1;

    utter.onend = function () {
      if (speech.status === "paused") { speech.pendingEnd = true; return; }
      if (speech.status !== "speaking") return;
      advanceSpeech();
    };
    utter.onerror = function (event) {
      var err = event && event.error;
      if (err === "interrupted" || err === "canceled") return; // we caused it
      finishSpeech();
      if (opts.onError) {
        try {
          opts.onError("Speech playback failed (" + (err || "unknown") +
            "). Try another voice or language.");
        } catch (e) { /* noop */ }
      }
    };

    try { window.speechSynthesis.speak(utter); }
    catch (e) { finishSpeech(); }
  }

  function stopSpeech() {
    if (!synthAvailable) return;
    if (speech.status === "idle") return;
    try { window.speechSynthesis.cancel(); } catch (e) { /* noop */ }
    finishSpeech();
  }

  /**
   * Speak text. Previous speech is always cancelled first (Chrome drops a
   * speak() issued immediately after cancel(), hence the short delay).
   *
   * opts: { locale, rate, voiceURI, onState(status), onNote(text), onError(text) }
   */
  function speakText(text, opts) {
    opts = opts || {};
    text = String(text || "").replace(/\s+/g, " ").trim();
    if (!synthAvailable) {
      if (opts.onError) opts.onError("Speech synthesis is not available in this browser.");
      return false;
    }
    if (!text) {
      if (opts.onError) opts.onError("There is nothing to read aloud.");
      return false;
    }

    stopActiveRecognition();   // never listen while speaking

    var wasActive = speech.status !== "idle";
    try { window.speechSynthesis.cancel(); } catch (e) { /* noop */ }

    speech.chunks = chunkText(text, CHUNK_CHARS);
    speech.index = 0;
    speech.opts = opts;
    speech.pendingEnd = false;
    speech.status = "speaking";
    notifySpeech();
    if (opts.onNote) { try { opts.onNote(voiceNote(opts.locale)); } catch (e) { /* noop */ } }

    window.setTimeout(function () {
      if (speech.status === "speaking") playChunk();
    }, wasActive ? 90 : 0);
    return true;
  }

  function pauseSpeech() {
    if (speech.status !== "speaking" || !synthAvailable) return;
    try { window.speechSynthesis.pause(); } catch (e) { /* noop */ }
    speech.status = "paused";
    notifySpeech();
  }

  function resumeSpeech() {
    if (speech.status !== "paused" || !synthAvailable) return;
    try { window.speechSynthesis.resume(); } catch (e) { /* noop */ }
    speech.status = "speaking";
    notifySpeech();
    if (speech.pendingEnd) {
      speech.pendingEnd = false;
      advanceSpeech();
    }
  }

  /* =====================================================================
     FEATURE 1 — Voice-to-text dock on /detect
     Real SpeechRecognition writing, live and editable, into the existing
     headline/article fields; the form then posts to the real /predict.
  ===================================================================== */
  function initVoiceDock() {
    var dock = $("voiceDock");
    if (!dock) return;

    var micBtn = $("vdMic");
    var startBtn = $("vdStart");
    var stopBtn = $("vdStop");
    var clearBtn = $("vdClear");
    var statusEl = $("vdStatus");
    var errorBox = $("vdErrors");
    var supportEl = $("vdSupport");
    var headline = $("headline");
    var article = $("article");
    var form = $("detectForm");

    var showError = makeErrorReporter(errorBox);
    var clearError = makeErrorClearer(errorBox);
    var wave = createWave($("vdWave"), 24, true);

    var target = "article";
    var recording = false;
    var session = null;
    var customStatus = null;
    var baseValue = "";
    var finals = "";
    var interim = "";
    var lastWritten = null;

    function field() {
      return target === "headline" ? headline : article;
    }

    function targetLabel() {
      return target === "headline" ? "Headline" : "Article";
    }

    function setStatus(text) {
      if (statusEl) statusEl.textContent = text;
    }

    function compose() {
      var base = String(baseValue || "").replace(/\s+$/, "");
      var spoken = String(finals || "");
      if (interim) spoken = spoken ? spoken + " " + interim : interim;
      spoken = spoken.replace(/^\s+/, "");
      if (!spoken) return base;
      if (!base) return spoken;
      return base + " " + spoken;
    }

    function writeTranscript() {
      var el = field();
      if (!el) return;
      var value = compose();
      lastWritten = value;
      el.value = value;
    }

    /* Manual editing always wins: if the value on screen is not what we
       wrote, the user typed — recording stops so nothing fights their
       cursor, and the next recording starts from their current text. */
    function watchField(el) {
      if (!el) return;
      on(el, "input", function () {
        if (el.value === lastWritten) return;
        if (recording) stopRecording(true, "Recording stopped — you can edit the transcript freely.");
        baseValue = "";
        finals = "";
        interim = "";
        lastWritten = null;
      });
    }
    watchField(headline);
    watchField(article);

    function setRecordingUI(active) {
      recording = active;
      if (micBtn) {
        micBtn.classList.toggle("is-recording", active);
        micBtn.setAttribute("aria-pressed", active ? "true" : "false");
        micBtn.disabled = !RecognitionCtor;
      }
      if (startBtn) startBtn.disabled = active || !RecognitionCtor;
      if (stopBtn) stopBtn.disabled = !active;
      dock.classList.toggle("is-recording", active);
    }

    function stopRecording(byUser, message) {
      if (!recording) {
        if (message) setStatus(message);
        return;
      }
      customStatus = message || null;
      if (session) {
        session.stop();                 // onEnd resets the UI asynchronously
      } else {
        setRecordingUI(false);
        if (wave) wave.stop();
        if (customStatus) { setStatus(customStatus); customStatus = null; }
      }
      if (!session && !message && byUser) setStatus("Stopped.");
    }

    function startRecording() {
      if (recording || !RecognitionCtor) return;
      clearError();

      var info = langInfo(currentLang);
      var el = field();
      if (!el) return;

      baseValue = el.value || "";
      finals = "";
      interim = "";

      session = createRecognitionSession({
        locale: currentLang,
        short: info.short,
        onStart: function () {
          setRecordingUI(true);
          setStatus("Listening… speak now (" + info.short + "). Words appear in the " +
            targetLabel() + " field as you talk.");
        },
        onFinal: function (text) { finals = text; writeTranscript(); },
        onInterim: function (text) { interim = text; writeTranscript(); },
        onStatus: function (msg) { setStatus(msg); },
        onError: function (msg) {
          showError(msg);
          setStatus("Recording stopped.");
        },
        onEnd: function (byUser) {
          if (wave) wave.stop();
          session = null;
          var wasRecording = recording;
          setRecordingUI(false);
          if (customStatus) {
            setStatus(customStatus);
            customStatus = null;
            return;
          }
          if (!wasRecording) return;
          var captured = compose().replace(/\s+/g, " ").trim();
          if (byUser) {
            setStatus(captured
              ? "Stopped — " + captured.length.toLocaleString() +
                " characters captured. Edit freely, then run the model."
              : "Stopped — no speech was captured.");
          } else if (!captured) {
            setStatus("Recording ended — nothing was captured. Press Start recording to try again.");
          } else {
            setStatus("Listening ended — the transcript was kept. Edit it, then run the model.");
          }
        }
      });

      if (!session) {
        setRecordingUI(false);
        if (!RecognitionCtor) {
          showError(unsupportedRecognition());
          if (supportEl) supportEl.textContent = unsupportedRecognition();
          setStatus("Voice input unavailable — you can still type your news text below.");
        } else {
          setStatus("Recording could not start. Check your microphone and try again.");
        }
        return;
      }

      setRecordingUI(true);
      if (wave) wave.start();
      setStatus("Starting the microphone…");
    }

    on(startBtn, "click", startRecording);
    on(stopBtn, "click", function () { stopRecording(true); });
    on(micBtn, "click", function () {
      if (recording) stopRecording(true);
      else startRecording();
    });

    on(clearBtn, "click", function () {
      var wasRecording = recording;
      stopRecording(true, "Transcription cleared.");
      baseValue = "";
      finals = "";
      interim = "";
      lastWritten = null;
      var el = field();
      if (el) { el.value = ""; lastWritten = ""; }
      clearError();
      if (!wasRecording) setStatus("Transcription cleared.");
      if (el) el.focus();
    });

    /* Destination chips (Headline / Article) */
    Array.prototype.forEach.call(dock.querySelectorAll("[data-vd-target]"), function (chip) {
      on(chip, "click", function () {
        var next = chip.getAttribute("data-vd-target");
        if (next === target) return;
        if (recording) stopRecording(true, "Recording stopped — the transcript stays in the previous field.");
        target = next;
        Array.prototype.forEach.call(dock.querySelectorAll("[data-vd-target]"), function (c) {
          var active = c === chip;
          c.classList.toggle("is-active", active);
          c.setAttribute("aria-pressed", active ? "true" : "false");
        });
        baseValue = "";
        finals = "";
        interim = "";
        setStatus("New speech will be written to the " + targetLabel() + " field.");
      });
    });

    /* Never submit while the microphone is still capturing. */
    if (form) {
      on(form, "submit", function () {
        if (recording) stopRecording(true);
      });
    }

    function updateSupportHint() {
      if (!supportEl) return;
      if (!RecognitionCtor) {
        supportEl.textContent = unsupportedRecognition() +
          " Voice input is disabled, but you can type or paste your news text as usual.";
        return;
      }
      var info = langInfo(currentLang);
      supportEl.textContent = "Recognizing " + info.short + " (" + currentLang +
        ") with your browser's Web Speech API. Whether each language works " +
        "depends on your browser — if a language is unsupported you will get " +
        "a clear message instead of a broken transcript.";
    }

    onLangChange(function () {
      if (recording) {
        stopRecording(true, "Language changed — recording stopped. Press Start " +
          "recording to continue in " + langInfo(currentLang).short + ".");
      }
      updateSupportHint();
    });

    setRecordingUI(false);
    if (!RecognitionCtor) {
      showError(unsupportedRecognition());
      setStatus("Voice input unavailable in this browser — type your text instead.");
    }
    updateSupportHint();
  }

  /* =====================================================================
     FEATURE 2 — Floating AI voice assistant
     Typed or spoken questions, rule-based replies from this Flask server,
     session conversation history, clear chat, typing animation and
     optional spoken replies.
  ===================================================================== */
  function initAssistantWidget() {
    var root = $("voiceAssistant");
    if (!root) return;

    var fab = $("vaFab");
    var panel = $("vaPanel");
    var closeBtn = $("vaClose");
    var clearBtn = $("vaClear");
    var form = $("vaForm");
    var input = $("vaInput");
    var messages = $("vaMessages");
    var sendBtn = $("vaSend");
    var micBtn = $("vaMic");
    var speakToggle = $("vaSpeakToggle");
    var statusEl = $("vaStatus");
    var errorBox = $("vaErrors");
    var intro = $("vaIntro");
    var voiceNoteEl = $("vaVoiceNote");

    var askUrl = root.getAttribute("data-ask-url");
    var historyUrl = root.getAttribute("data-history-url");
    var clearUrl = root.getAttribute("data-clear-url");

    var showError = makeErrorReporter(errorBox);
    var clearError = makeErrorClearer(errorBox);

    var historyLoaded = false;
    var listening = false;
    var micSession = null;
    var micBase = "";
    var speakingReplies = storeGet(SPEAK_KEY) === "1";
    var defaultStatus = "Rule-based — no external AI API";

    function setStatus(text) {
      if (statusEl) statusEl.textContent = text;
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
        avatar.appendChild(svgIcon("#i-spark"));
        wrap.appendChild(avatar);
      }

      var bubble = document.createElement("div");
      bubble.className = "msg-bubble";
      var para = document.createElement("p");
      para.textContent = text;   // plain text, never HTML
      bubble.appendChild(para);
      wrap.appendChild(bubble);
      messages.appendChild(wrap);
      scrollToEnd();
      return wrap;
    }

    var typingEl = null;

    function showTyping() {
      if (!messages) return;
      hideTyping();
      typingEl = document.createElement("div");
      typingEl.className = "chat-msg bot";

      var avatar = document.createElement("span");
      avatar.className = "msg-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.appendChild(svgIcon("#i-spark"));
      typingEl.appendChild(avatar);

      var bubble = document.createElement("div");
      bubble.className = "msg-bubble";
      var dots = document.createElement("span");
      dots.className = "typing";
      dots.setAttribute("aria-label", "Assistant is typing");
      dots.appendChild(document.createElement("span"));
      dots.appendChild(document.createElement("span"));
      dots.appendChild(document.createElement("span"));
      bubble.appendChild(dots);
      typingEl.appendChild(bubble);

      messages.appendChild(typingEl);
      scrollToEnd();
    }

    function hideTyping() {
      if (typingEl && typingEl.parentNode) typingEl.parentNode.removeChild(typingEl);
      typingEl = null;
    }

    function loadHistory() {
      historyLoaded = true;
      if (!historyUrl) return;
      showTyping();
      fetch(historyUrl, { headers: { "Accept": "application/json" } })
        .then(function (response) {
          return response.ok ? response.json() : null;
        })
        .then(function (data) {
          hideTyping();
          if (!data || !data.messages || !data.messages.length) return;
          if (intro) intro.hidden = true;
          data.messages.forEach(function (m) {
            addMessage(m.text, m.role === "user" ? "user" : "bot");
          });
          scrollToEnd();
        })
        .catch(function () {
          hideTyping();   // keep the opening message when history is unreachable
        });
    }

    function speakReply(reply) {
      speakText(reply, {
        locale: currentLang,
        onState: function (state) {
          setStatus(state === "speaking" ? "Speaking the reply…" :
            state === "paused" ? "Reply paused." : defaultStatus);
        },
        onError: function (msg) { setStatus(msg); }
      });
    }

    function send(text) {
      text = (text || "").trim();
      if (!text) {
        showError("Please enter or speak a message first.");
        if (input) input.focus();
        return;
      }
      if (text.length > MAX_MESSAGE) {
        showError("Message is too long. Please limit it to " +
          MAX_MESSAGE.toLocaleString() + " characters.");
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
      setStatus("Thinking…");

      fetch(askUrl, {
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
            setStatus(defaultStatus);
            return;
          }
          addMessage(result.data.reply, "bot");
          setStatus(defaultStatus);
          if (speakingReplies) speakReply(result.data.reply);
        })
        .catch(function () {
          hideTyping();
          showError("Network error — could not reach the assistant. Please try again.");
          setStatus(defaultStatus);
        })
        .then(function () {
          if (sendBtn) {
            sendBtn.classList.remove("is-loading");
            sendBtn.removeAttribute("aria-disabled");
          }
        });
    }

    /* --- panel open / close --- */
    function setOpen(open) {
      if (!panel || !fab) return;
      panel.hidden = !open;
      root.classList.toggle("is-open", open);
      fab.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        if (!historyLoaded) loadHistory();
        if (input) input.focus();
      } else {
        stopMic();
        stopSpeech();
        setStatus(defaultStatus);
      }
    }

    on(fab, "click", function () { setOpen(panel.hidden); });
    on(closeBtn, "click", function () { setOpen(false); if (fab) fab.focus(); });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && panel && !panel.hidden) {
        setOpen(false);
        if (fab) fab.focus();
      }
    });

    document.addEventListener("click", function (event) {
      if (!panel || panel.hidden) return;
      if (root.contains(event.target)) return;
      setOpen(false);
    });

    /* --- clear chat (server + local, honestly reported) --- */
    on(clearBtn, "click", function () {
      clearError();
      stopSpeech();
      if (messages) {
        Array.prototype.forEach.call(messages.querySelectorAll(".chat-msg"), function (n) {
          if (n !== intro && n.parentNode) n.parentNode.removeChild(n);
        });
      }
      if (intro) intro.hidden = false;
      if (messages) messages.scrollTop = 0;
      fetch(clearUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: "{}"
      })
        .then(function (response) {
          setStatus(response.ok
            ? "Conversation cleared."
            : "Cleared on this page — the server could not clear the saved history.");
        })
        .catch(function () {
          setStatus("Cleared on this page — the server was unreachable, so the saved session history may reappear.");
        });
    });

    /* --- form wiring --- */
    on(form, "submit", function (event) {
      event.preventDefault();
      send(input ? input.value : "");
    });
    on(input, "keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        send(input.value);
      }
    });

    /* --- microphone input --- */
    function setMicUI(active) {
      listening = active;
      if (micBtn) {
        micBtn.classList.toggle("is-recording", active);
        micBtn.setAttribute("aria-pressed", active ? "true" : "false");
      }
      root.classList.toggle("is-listening", active);
    }

    function startMic() {
      if (listening || !RecognitionCtor) {
        if (!RecognitionCtor) {
          showError(unsupportedRecognition());
          setStatus("Voice input unavailable — type your question instead.");
        }
        return;
      }
      clearError();
      var info = langInfo(currentLang);
      micBase = input ? input.value : "";
      if (micBase && !/\s$/.test(micBase)) micBase += " ";

      micSession = createRecognitionSession({
        locale: currentLang,
        short: info.short,
        onStart: function () {
          setMicUI(true);
          setStatus("Listening… ask your question (" + info.short + ").");
        },
        onFinal: function (text) { if (input) input.value = micBase + text; },
        onInterim: function (text) { if (input) input.value = micBase + text; },
        onStatus: function (msg) { setStatus(msg); },
        onError: function (msg) {
          showError(msg);
          setStatus("Voice input stopped.");
        },
        onEnd: function (byUser) {
          micSession = null;
          var wasListening = listening;
          setMicUI(false);
          if (!wasListening) return;
          var text = input ? input.value.trim() : "";
          if (byUser && text) { send(text); return; }   // one action: speak → ask
          if (!byUser && !text) {
            setStatus("Voice input ended — nothing was captured. Tap the mic to try again.");
          } else if (text) {
            setStatus("Transcript ready — press Send.");
          } else {
            setStatus("Voice input stopped.");
          }
        }
      });

      if (!micSession) {
        setMicUI(false);
        if (!RecognitionCtor) showError(unsupportedRecognition());
        return;
      }
      setMicUI(true);
      setStatus("Starting the microphone…");
    }

    function stopMic() {
      if (!listening) return;
      if (micSession) micSession.stop();
      else setMicUI(false);
    }

    on(micBtn, "click", function () {
      if (listening) stopMic();
      else startMic();
    });

    /* --- spoken replies toggle --- */
    function updateVoiceNote() {
      if (voiceNoteEl) voiceNoteEl.textContent = voiceNote(currentLang);
    }

    function renderSpeakToggle() {
      if (!speakToggle) return;
      speakToggle.setAttribute("aria-pressed", speakingReplies ? "true" : "false");
      speakToggle.classList.toggle("is-on", speakingReplies);
    }

    on(speakToggle, "click", function () {
      speakingReplies = !speakingReplies;
      storeSet(SPEAK_KEY, speakingReplies ? "1" : "0");
      renderSpeakToggle();
      if (!speakingReplies) stopSpeech();
      updateVoiceNote();
    });

    onLangChange(function () {
      stopSpeech();
      setStatus(defaultStatus);
      updateVoiceNote();
    });

    /* Refresh the availability note when the browser finishes loading its
       voice list (some engines only report voices after a short delay). */
    voiceListeners.push(updateVoiceNote);

    renderSpeakToggle();
    updateVoiceNote();
    setMicUI(false);
  }
  /* =====================================================================
     FEATURE 4 — Listen to results (text-to-speech player)
     Reads the REAL rendered result: label, confidence when available,
     and the explanation. No value is ever invented for the speech.
  ===================================================================== */
  function initTtsPlayer() {
    var panel = $("ttsPanel");
    if (!panel) return;

    var playBtn = $("ttsPlay");
    var pauseBtn = $("ttsPause");
    var resumeBtn = $("ttsResume");
    var stopBtn = $("ttsStop");
    var rateSel = $("ttsRate");
    var voiceSel = $("ttsVoice");
    var statusEl = $("ttsStatus");
    var noteEl = $("ttsNote");

    var wave = createWave($("ttsWave"), 20, false);   // CSS bars only — no mic needed
    var idleMessage = "Ready — press Listen to results.";
    var everPlayed = false;

    function setStatus(text) {
      if (statusEl) statusEl.textContent = text;
    }

    /* Build the spoken script from what is actually rendered on screen. */
    function buildScript() {
      var verdict = document.querySelector(".verdict");
      if (!verdict) return null;
      var labelEl = verdict.querySelector(".verdict-label");
      var confEl = verdict.querySelector(".meter-value");
      var summaryEl = verdict.querySelector(".verdict-summary");

      var parts = ["Prediction result."];
      var label = labelEl ? labelEl.textContent.replace(/\s+/g, " ").trim() : "";
      if (label) parts.push(label + ".");
      if (confEl) {
        var conf = confEl.textContent.replace(/\s+/g, " ").trim();
        if (conf) parts.push("Confidence of the predicted class: " +
          conf.replace("%", " percent") + ".");
      }
      var summary = summaryEl ? summaryEl.textContent.replace(/\s+/g, " ").trim() : "";
      if (summary) parts.push(summary);
      parts.push("This is a statistical model prediction, not a fact-check.");
      var script = parts.join(" ");
      return script.length > 2000 ? script.slice(0, 2000) + " …" : script;
    }

    function renderControls(state) {
      var playing = state === "speaking";
      var paused = state === "paused";
      if (playBtn) {
        playBtn.disabled = !synthAvailable;
        playBtn.classList.toggle("is-playing", playing || paused);
      }
      if (pauseBtn) pauseBtn.hidden = !playing;
      if (resumeBtn) resumeBtn.hidden = !paused;
      if (stopBtn) stopBtn.hidden = !(playing || paused);
      if (wave) {
        if (playing) wave.start();
        else wave.stop();
      }
    }

    function onState(state) {
      renderControls(state);
      if (state === "speaking") {
        setStatus("Reading the result aloud…");
        idleMessage = "Finished — press Listen to results to hear it again.";
      } else if (state === "paused") {
        setStatus("Paused.");
      } else {
        setStatus(idleMessage);
      }
    }

    on(playBtn, "click", function () {
      var script = buildScript();
      if (!script) {
        setStatus("The result text could not be found on this page.");
        return;
      }
      everPlayed = true;
      idleMessage = "Finished — press Listen to results to hear it again.";
      speakText(script, {
        locale: currentLang,
        rate: rateSel ? rateSel.value : "1",
        voiceURI: voiceSel && voiceSel.value ? voiceSel.value : "",
        onState: onState,
        onNote: function (note) { if (noteEl) noteEl.textContent = note; },
        onError: function (msg) {
          setStatus("Playback could not start.");
          if (noteEl) noteEl.textContent = msg;
        }
      });
    });

    on(pauseBtn, "click", function () {
      pauseSpeech();
      if (statusEl && speech.status === "paused") setStatus("Paused.");
    });

    on(resumeBtn, "click", resumeSpeech);

    on(stopBtn, "click", function () {
      idleMessage = "Stopped.";
      stopSpeech();
      setStatus("Stopped.");
    });

    /* --- voice selection (populated from real available voices) --- */
    function addOption(sel, value, label, selected) {
      var opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      if (selected) opt.selected = true;
      sel.appendChild(opt);
    }

    function populateVoices() {
      if (!voiceSel) return;
      var info = langInfo(currentLang);
      voiceSel.textContent = "";

      if (!synthAvailable) {
        voiceSel.disabled = true;
        addOption(voiceSel, "", "Speech synthesis unavailable");
        if (noteEl) noteEl.textContent = voiceNote(currentLang);
        return;
      }

      var matches = voicesForLocale(currentLang).all;
      if (!matches.length) {
        voiceSel.disabled = true;
        addOption(voiceSel, "", "No " + info.short + " voice installed — default voice used");
        if (noteEl) noteEl.textContent = voiceNote(currentLang);
        return;
      }

      voiceSel.disabled = matches.length < 2;
      matches.forEach(function (v, i) {
        addOption(voiceSel, v.voiceURI,
          v.name + " (" + v.lang + ")" + (v.default ? " — system default" : ""),
          i === 0);
      });
      if (noteEl) noteEl.textContent = voiceNote(currentLang);
    }

    voiceListeners.push(populateVoices);

    onLangChange(function () {
      if (speech.status !== "idle") {
        idleMessage = "Language changed — playback stopped.";
        stopSpeech();
        setStatus("Language changed — playback stopped.");
      }
      populateVoices();
    });

    if (!synthAvailable) {
      setStatus("Text-to-speech is not available in this browser.");
    }
    populateVoices();
    renderControls("idle");
    if (!everPlayed) setStatus("Ready — press Listen to results.");
  }

  /* =====================================================================
     FEATURE 2 (continued) — voice on the full /assistant chat page
     The floating widget is hidden here (this page IS the full chat), so the
     microphone, the language picker and spoken replies are wired directly
     into the existing chat form without touching its submit logic.
  ===================================================================== */
  function initAssistantPage() {
    var form = document.getElementById("assistantForm");
    var input = document.getElementById("assistantInput");
    var messages = document.getElementById("chatMessages");
    if (!form || !input) return;

    var micBtn = $("chatMic");
    var speakToggle = $("chatSpeakToggle");
    var statusEl = $("chatVoiceStatus");
    var noteEl = $("chatVoiceNote");
    var errorBox = $("chatVoiceErrors");

    var showError = makeErrorReporter(errorBox);
    var clearError = makeErrorClearer(errorBox);

    var listening = false;
    var session = null;
    var base = "";
    var speakingReplies = storeGet(SPEAK_KEY) === "1";

    function setStatus(text) {
      if (statusEl) statusEl.textContent = text || "";
    }

    /* --- microphone input ------------------------------------------- */
    function setMicUI(active) {
      listening = active;
      if (micBtn) {
        micBtn.classList.toggle("is-recording", active);
        micBtn.setAttribute("aria-pressed", active ? "true" : "false");
        micBtn.disabled = !RecognitionCtor;
      }
      if (messages) messages.classList.toggle("is-listening", active);
    }

    function startMic() {
      if (listening || !RecognitionCtor) {
        if (!RecognitionCtor) {
          showError(unsupportedRecognition());
          setStatus("Voice input unavailable — type your question instead.");
        }
        return;
      }
      clearError();
      var info = langInfo(currentLang);
      base = input.value || "";
      if (base && !/\s$/.test(base)) base += " ";

      session = createRecognitionSession({
        locale: currentLang,
        short: info.short,
        onStart: function () {
          setMicUI(true);
          setStatus("Listening… ask your question (" + info.short + ").");
        },
        onFinal: function (text) { input.value = base + text; },
        onInterim: function (text) { input.value = base + text; },
        onStatus: function (msg) { setStatus(msg); },
        onError: function (msg) {
          showError(msg);
          setStatus("Voice input stopped.");
        },
        onEnd: function (byUser) {
          session = null;
          var wasListening = listening;
          setMicUI(false);
          if (!wasListening) return;
          var text = input.value.trim();
          if (byUser && text) {
            setStatus("Transcript ready — review it, then press Send.");
          } else if (!text) {
            setStatus("Voice input ended — nothing was captured. Tap the mic to try again.");
          } else {
            setStatus("Transcript ready — press Send.");
          }
        }
      });

      if (!session) {
        setMicUI(false);
        if (!RecognitionCtor) showError(unsupportedRecognition());
        return;
      }
      setMicUI(true);
      setStatus("Starting the microphone…");
    }

    function stopMic() {
      if (!listening) return;
      if (session) session.stop();
      else setMicUI(false);
    }

    on(micBtn, "click", function () {
      if (listening) stopMic();
      else startMic();
    });

    /* Never leave the microphone running while a question is sent. */
    on(form, "submit", stopMic);

    /* --- spoken replies --------------------------------------------- */
    function updateNote() {
      if (noteEl) noteEl.textContent = voiceNote(currentLang);
    }

    function renderSpeakToggle() {
      if (!speakToggle) return;
      speakToggle.setAttribute("aria-pressed", speakingReplies ? "true" : "false");
      speakToggle.classList.toggle("is-on", speakingReplies);
    }

    on(speakToggle, "click", function () {
      speakingReplies = !speakingReplies;
      storeSet(SPEAK_KEY, speakingReplies ? "1" : "0");
      renderSpeakToggle();
      if (!speakingReplies) stopSpeech();
      updateNote();
    });

    /* Read new assistant replies aloud when the toggle is on. The typing
       indicator is skipped, and only nodes added after this observer starts
       are spoken (the server-rendered intro is never read on page load). */
    if (messages && typeof window.MutationObserver === "function") {
      var observer = new window.MutationObserver(function (mutations) {
        if (!speakingReplies) return;
        mutations.forEach(function (mutation) {
          Array.prototype.forEach.call(mutation.addedNodes, function (node) {
            if (!node || node.nodeType !== 1 || !node.classList) return;
            if (!node.classList.contains("chat-msg") || !node.classList.contains("bot")) return;
            if (node.querySelector(".typing")) return;
            var para = node.querySelector(".msg-bubble p");
            if (!para || !para.textContent) return;
            speakText(para.textContent, {
              locale: currentLang,
              onState: function (state) {
                setStatus(state === "speaking" ? "Speaking the reply…" :
                  state === "paused" ? "Reply paused." : "");
              },
              onError: function (msg) { setStatus(msg); }
            });
          });
        });
      });
      observer.observe(messages, { childList: true });
    }

    onLangChange(function () {
      stopMic();
      stopSpeech();
      setStatus("");
      updateNote();
    });

    /* Refresh the availability note once the browser reports its voices. */
    voiceListeners.push(updateNote);

    renderSpeakToggle();
    updateNote();
    setMicUI(false);
  }

  /* ---------------------------------------------------------------------
     Boot
  --------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", function () {
    initLanguage();
    initVoiceDock();
    initAssistantWidget();
    initAssistantPage();
    initTtsPlayer();
  });
})();

