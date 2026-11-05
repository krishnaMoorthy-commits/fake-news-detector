# News Intelligence Platform — Fake News Detection Using Data Science

A Flask web application that classifies news text (headline + article) as
**REAL** or **FAKE** using a TF-IDF + Logistic Regression Machine Learning
model — wrapped in a premium, futuristic news-intelligence interface with
document upload, an interactive pipeline visualization, a clearly labelled
demonstration news feed and a rule-based AI News Assistant. Built as a
college academic project demonstrating an end-to-end Data Science pipeline:
data collection → cleaning → feature extraction → Machine Learning →
prediction.

> **Important honesty note:** This application performs statistical text
> classification learned from a labelled dataset. It does **not** browse the
> internet, does not fact-check claims against real-world sources, and its
> predictions should never be treated as a definitive verdict on whether a
> story is true or false.

---

## Features (Actually Implemented)

- Premium AI-style home page: deep midnight-navy theme, glassmorphism cards,
  electric-blue/cyan glow accents, animated background (drifting glow orbs,
  floating particle canvas, fading grid) and scroll-reveal transitions —
  all disabled automatically under `prefers-reduced-motion`
- Web form to submit a news headline and/or full article
- Document upload (drag-and-drop zone + file picker) for **TXT, PDF and
  DOCX** — extension and 2 MB size validation, in-memory text extraction
  (`pypdf`, `python-docx`), files are never executed or permanently stored
- Interactive 7-stage AI workflow visualization that mirrors the **real**
  pipeline: input → preprocessing → cleaning → TF-IDF features → Logistic
  Regression → prediction → result (each stage shows the actual function
  and parameters from `model.py` / `train_model.py`)
- News feed interface with category filters, search bar, trending block and
  expandable cards — **demonstration content only**: no news API is
  configured, so every card is visibly labelled "Demo" with a
  "Demonstration content" source line and "Sample entry" date
- AI News Assistant: chat interface backed by transparent rule-based logic
  (`assistant.py`) — explains the pipeline and real predictions, scans pasted
  text for sensationalist wording (heuristics), gives fact-checking advice,
  and states its limitations. No external AI API is used or claimed
- **Voice intelligence (browser Web Speech API only — no API keys, no external
  services):**
  - *Voice input dock* on `/detect`: speech is transcribed live and editable
    into the real headline/article field you choose before you submit it
  - *Floating voice assistant* (every page except `/assistant`, which already
    hosts the full chat): typed or spoken questions, rule-based replies read
    aloud on request, session conversation history with a clear button
  - *Voice on the full chat page* (`/assistant`): microphone input for
    questions, its own language picker, an optional "Speak replies" toggle
    that reads new answers aloud, and live availability/recording status
  - *"Listen to results"* player on the result page: reads the actual
    rendered label, confidence and explanation, with play / pause / resume /
    stop, voice speed and installed-voice selection
  - `en-IN` / `ta-IN` / `hi-IN` language choice shared by every control;
    unsupported browsers, blocked microphones, missing voices and unsupported
    languages are reported with honest, specific messages instead of failing
    silently. Animations respect `prefers-reduced-motion`
- Honest language limitation: preprocessing keeps only the English letters
  `a–z`, so Tamil or Hindi (Devanagari) input triggers a visible "Language
  limitation" warning on the result page rather than a silently meaningless
  score — the app never claims to translate text
- **News Comparison Lab (`/compare`)**: two headline/article panels scored by
  the *same* trained model in one submission, side-by-side verdict cards with
  the real confidence scores, an animated label-agreement indicator, a
  **genuine word-level similarity calculation** (Jaccard overlap + shared /
  unique vocabulary computed from the actual input), a downloadable text
  report built from the rendered results, and an explicit note that differing
  predictions are *not* proof the articles are factually inconsistent
- **Intelligence Analytics (`/analytics`)**: session-scoped dashboard with
  animated counters (total / REAL / FAKE / REAL share), a prediction
  distribution doughnut and a 7-day activity bar chart (Chart.js, vendored
  locally), the recent-analysis history with timestamps, and the model-quality
  metrics recorded inside the `.pkl` bundle at training time. Empty sessions
  show honest empty states — no sample data is ever mixed in, and one
  visitor's history never reaches another session
- **Premium 3D experience (Three.js, loaded on demand)**: holographic neural
  network in the home hero, holographic news scanner rings on `/detect`,
  floating article panels on `/compare` and floating statistic bars on
  `/analytics`; CSS 3D tilt cards, mouse parallax and a layered 3D microphone
  with an equalizer-floor waveform. WebGL failure, missing libraries or
  `prefers-reduced-motion` fall back to animated CSS visuals; decorative hero
  scenes are hidden on phones to protect performance
- **Paste-article button** on the analysis form: reads the system clipboard
  into the article field via the async Clipboard API and reports blocked or
  empty clipboard access honestly (with a Ctrl+V fallback message)
- Server-side text preprocessing (lowercasing, HTML/URL/punctuation removal)
- TF-IDF vectorization of submitted text
- Logistic Regression classification (REAL / FAKE)
- Confidence percentage via `predict_proba()` (only shown when genuinely available)
- Result page with prediction, confidence bar, explanation, source note for
  uploaded documents and disclaimer
- Session-based statistics (Total Checked / Real / Fake / Fake Rate) shown on the
  home and result pages, with animated count-up numbers
- Animated metrics band on the home page reading the real evaluation numbers
  stored inside the trained `.pkl` bundle (no figure is hardcoded)
- Model card on the About page that reads the metrics stored inside the
  trained `.pkl` bundle (no figure is hardcoded in the templates)
- Graceful handling of a missing dataset or missing trained model
- Responsive from wide desktop to small phones: one hand-written CSS design
  system, inline SVG icon sprite and vanilla JavaScript (no Bootstrap, no
  CDN assets)
- Sticky blur navigation with an active-page indicator, accessible hamburger
  menu, skip link, visible focus rings and `prefers-reduced-motion` support
- No-JavaScript fallbacks: the analysis form, feed filters (server-side GET),
  upload form (normal POST) and assistant (HTML reply) all work without JS

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | Python 3, Flask | Web server & routing |
| ML | scikit-learn (TF-IDF, Logistic Regression) | Text classification |
| Data | Pandas, NumPy | Dataset loading & manipulation |
| Document parsing | pypdf, python-docx | Extracting text from uploaded PDF/DOCX files |
| Persistence | joblib | Saving/loading the trained vectorizer + model |
| Frontend | HTML5, Jinja2, CSS3 (custom design system), vanilla JavaScript | UI |
| Icons / artwork | Inline SVG sprite and hand-drawn SVG illustration | No image or icon library |
| Production server | gunicorn | WSGI server on Render |

---

## Project Structure

```
fake_news_detector/
│
├── app.py                   <- Flask routes, upload extraction, validation, error handlers
├── model.py                 <- preprocessing, model loading, predict_news()
├── train_model.py           <- training script (not needed at runtime)
├── news_feed.py             <- demonstration feed data (no news API)
├── assistant.py             <- rule-based AI News Assistant engine (no external AI API)
├── requirements.txt
├── README.md
├── render.yaml              <- Render blueprint (gunicorn, $PORT, /healthz)
├── _test_app.py             <- backend test suite (python _test_app.py)
│
├── dataset/
│   └── news.csv             <- you provide this
│
├── model/
│   └── fake_news_model.pkl  <- generated by train_model.py
│
├── templates/
│   ├── base.html            <- shared shell: nav, icon sprite, animated bg, footer
│   ├── index.html           <- premium home page (hero, workflow, feed preview…)
│   ├── detect.html          <- analysis form + document upload panel (/detect)
│   ├── result.html          <- prediction result (/predict, /upload)
│   ├── compare.html         <- News Comparison Lab (/compare)
│   ├── analytics.html       <- Intelligence Analytics dashboard (/analytics)
│   ├── feed.html            <- news feed with filters and search (/feed)
│   ├── assistant.html       <- AI News Assistant chat (/assistant)
│   ├── about.html           <- about + model card
│   ├── 404.html             <- not-found page
│   └── partials/
│       └── analyze_form.html <- reusable form (used by /detect and home preview)
│
└── static/
    ├── css/
    │   └── style.css        <- design system (CSS variables, all sections, animations)
    ├── js/
    │   ├── script.js        <- nav, reveals, count-ups, workflow, upload, paste, chat, feed
    │   ├── voice.js         <- Web Speech API: voice dock, voice assistant, TTS player
    │   ├── scene3d.js       <- Three.js scenes (lazy), CSS 3D tilt, mouse parallax
    │   ├── compare.js       <- comparison validation, loading state, report download
    │   ├── analytics.js     <- animated counters + Chart.js dashboard charts
    │   └── vendor/
    │       ├── three.min.js       <- vendored Three.js (no CDN at runtime)
    │       └── chart.umd.min.js   <- vendored Chart.js (no CDN at runtime)
    └── img/
        └── favicon.svg
```

---

## Pages & Routes

| Route | Method | Page |
|---|---|---|
| `/` | GET | Home — hero, about, how it works, AI workflow visualization, capabilities, latest news, why us, stack, session snapshot, preview form |
| `/detect` | GET | Analysis form + document upload panel (also used to re-render validation errors) |
| `/predict` | POST | Runs the real model and renders the result page |
| `/upload` | POST | Extracts text from an uploaded TXT/PDF/DOCX file (in memory) and runs the same prediction flow |
| `/compare` | GET | News Comparison Lab — two-article input panels |
| `/compare` | POST | Scores **both** articles with the same model and renders side-by-side verdicts + genuine word-level similarity |
| `/analytics` | GET | Intelligence Analytics dashboard (counters, charts, history — session data only) |
| `/feed` | GET | News feed — category filter (`?category=`) and search (`?q=`), demonstration content |
| `/assistant` | GET | AI News Assistant chat interface |
| `/assistant/ask` | POST | Assistant replies: JSON for the chat UI, HTML fallback without JavaScript |
| `/assistant/history` | GET | Capped session conversation history (JSON) for the floating voice assistant |
| `/assistant/clear` | POST | Clears the session conversation history (JSON) |
| `/about` | GET | Project background, pipeline, limitations, model card |
| `/healthz` | GET | Health probe for Render (JSON: `{"status": "ok", ...}`) |
| anything else | — | `404.html` |

The form fields (`headline`, `article`), the `POST /predict` action and the
server-side validation rules are unchanged from the original project —
`/predict` and `/upload` share one prediction helper, so typed text and
uploaded documents always travel through the identical pipeline.

---

## Dataset Setup

Place your dataset at:

```
dataset/news.csv
```

**Preferred CSV format:**

```csv
title,text,label
"Example headline","Example article content...","REAL"
"False claim example","Example misleading article...","FAKE"
```

- `title` — the news headline
- `text` — the full article content
- `label` — `REAL` or `FAKE` (the training script also tolerates
  `TRUE`/`FALSE`, `1`/`0`, and a few common column-name variations such as
  `headline`/`content`/`class`, but the format above is preferred and
  documented for the project write-up)

This project does **not** ship with a bundled dataset. You must supply your
own labelled fake/real news dataset (for example, a public Kaggle fake-news
dataset) and place it at the path above before training.

---

## Installation (Windows)

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Train the Model

```bat
python train_model.py
```

This reads `dataset/news.csv`, cleans and splits the data, trains a
TF-IDF + Logistic Regression model, prints real evaluation metrics
(accuracy, precision, recall, F1-score, confusion matrix — all computed
from your actual dataset), and saves the trained bundle to:

```
model/fake_news_model.pkl
```

## Run the Application

```bat
python app.py
```

## Open in Browser

```
http://127.0.0.1:5000
```

---

## Testing

Backend suite (syntax, routes, navigation integrity, asset existence,
server-side validation, XSS escaping, and proof that the real
`model.predict_news()` is invoked):

```bat
python _test_app.py
```

Latest run: **376/376 checks passed**, covering 13 sections:

1. Python syntax checks
2. Imports & app factory
3. Route registration & page rendering (hero copy, feed and assistant markers)
4. Template/navigation integrity (nav items, form wiring, no CDN assets,
   internal links resolve)
5. Prediction workflow (real model invoked exactly once per submission,
   escaping, truncation, session stats)
6. Validation returning to the detection page
7. Escaping in every user-facing template (no `|safe` on user data)
8. Document upload with real parsing: TXT / PDF / DOCX happy paths plus
   rejection of unsupported extensions, oversized files, empty files,
   unreadable PDFs and missing files — rejected uploads never reach the model
9. News feed: demo labelling, category filter, search, empty states
10. AI News Assistant: intent routing, honest rule-based/limitation replies,
    a real model run for pasted text, session-prediction explanation,
    length limits and the no-JavaScript HTML fallback
11. Workflow visualization, upload wiring and design assets (7 real stages,
    CSS/JS initializers, reduced-motion support)
12. Voice intelligence: `/assistant/history` + `/assistant/clear` session
    flow, the voice dock / floating widget / TTS panel / full-page chat
    voice controls markup, the honest Tamil & Hindi language warnings (and
    their absence for English), the `voice.js` feature set (no `innerHTML`,
    no API keys, reduced-motion) and the matching CSS
13. News Comparison Lab, Intelligence Analytics and the 3D experience:
    `/compare` running the model exactly twice per submission with genuine
    similarity maths (100% for identical text, 0% for disjoint text),
    server-side rejection of an empty side, XSS escaping on both panels,
    `/analytics` empty states for fresh visitors, **session privacy** (one
    visitor's history never appears in another session), nav/footer links
    and active states, the vendored Three.js/Chart.js bundles, `scene3d.js`
    feature guards, the paste-article control and the new CSS layer

Live HTTP checks against a running server: every page and static asset
returns 200, `/predict` returns a real prediction with confidence, multipart
uploads of TXT/PDF/DOCX return the result page with extracted text, an
`.exe` upload is rejected, the assistant JSON endpoint answers, an empty
POST re-renders the form with an error, and the voice endpoints
(`/assistant/history`, `/assistant/clear`) round-trip a real session cookie.

Responsive browser pass (headless Chrome via the DevTools protocol, driver
kept outside the repository): 5 pages × 4 viewports
(1440 / 1024 / 768 / 390 px) — **0 console errors, 0 failed network
requests, 0 stuck reveal animations** — plus interaction checks (workflow
stage selection, feed live search, assistant chat round-trip) and a
`prefers-reduced-motion` emulation run, with full-page screenshots reviewed
at every breakpoint.

Voice intelligence browser suite (same protocol, Chrome launched with a fake
microphone device and a relaxed autoplay policy): **51/51 checks, 0 console
errors, 0 failed requests** — capability detection, the voice dock recording
cycle (start → listen → stop → cleanup), microphone denial messaging,
transcribing into the real form fields and submitting them to `/predict`,
the TTS player's play / pause / resume / stop states with its waveform and
voice-speed options, language switching, assistant microphone input,
typed and spoken assistant replies, widget open / clear / Escape, and
horizontal-overflow checks at 390 px for `/`, `/detect` and `/assistant`.
Speech *recognition accuracy* itself cannot be asserted headlessly — that
still needs a human speaking into a real microphone.

Platform-upgrade browser suite (same protocol): **30/30 checks, 0 console
errors, 0 failed requests** — the three.js scenes rendering on `/`,
`/detect`, `/compare` and `/analytics` (with the CSS fallback verified as
the alternative path), the full comparison flow (fill → analyze → verdicts,
overlap score, agreement card, shared-vocabulary chips, clear-all), the
analytics dashboard drawing real pixels into both charts from session data,
the paste-button outcome message, microphone tilt, and 390 px overflow +
phone scene-hiding checks for `/compare`, `/analytics` and `/detect`.

---

## Deployment (Render, free tier)

The trained model (`model/fake_news_model.pkl`) is committed, so the server
does not need the dataset. `render.yaml` defines the web service:

- Build: `pip install -r requirements.txt` (exact versions pinned so the
  pickled model loads with the same scikit-learn it was trained with)
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`
- Health check: `/healthz`
- `FLASK_SECRET_KEY` is generated automatically by Render

On Render: **New → Blueprint**, select this repository, and apply.

If you retrain with a different scikit-learn version, update
`requirements.txt` to match before redeploying.

---

## How It Works

```
User Input (headline + article)
        ↓
Server-side validation
        ↓
Text preprocessing (lowercase, strip HTML/URLs/punctuation)
        ↓
TF-IDF vectorization (using the vectorizer fitted during training)
        ↓
Logistic Regression prediction
        ↓
Confidence score (when predict_proba is available)
        ↓
Result page with explanation & disclaimer
```

---

## Model Performance

Model performance metrics (accuracy, precision, recall, F1-score) are
**calculated at training time from your dataset** and printed to the
console by `train_model.py`. No accuracy figure is hardcoded anywhere in
this codebase.

The About page renders a **model card** whose numbers are read at runtime
from the `metrics` entry inside `model/fake_news_model.pkl`, so the page can
never drift from the model that is actually deployed. If a bundle has no
metrics stored, the card says so instead of inventing a value.

---

## Algorithms Discussed vs. Implemented

The academic write-up for this project discusses several classification
algorithms relevant to text classification:

- Logistic Regression
- Naive Bayes
- Decision Tree
- Random Forest
- Support Vector Machine

**Only Logistic Regression (with TF-IDF features) is implemented** in this
web application, because it offers a good balance of simplicity,
interpretability, and performance for a college-level NLP project. The
other algorithms are discussed for academic completeness but are not wired
into the running application.

---

## Limitations

- Does not browse the internet or access any external fact-checking API.
- Does not independently verify factual claims against real-world sources.
- Predictions depend entirely on the quality and coverage of the training
  dataset provided by the user.
- Can produce incorrect predictions, like any statistical model.
- Can be affected by bias present in the training dataset.
- May struggle with sarcasm, satire, or novel forms of misinformation not
  represented in the training data.
- Dashboard statistics are per-session only (stored in the Flask session)
  and reset when the session/cookies are cleared or the server restarts.
- **News feed:** no news API is configured, so the feed serves static
  demonstration content that is explicitly labelled as such — it is not
  live or breaking news.
- **AI News Assistant:** no external AI API is configured, so the assistant
  is rule-based (written responses in `assistant.py`), not a generative
  model. It explains what it is programmed to explain and says so.
- **Uploaded documents** are parsed in memory and discarded; extracted text
  beyond 10,000 characters is not analyzed.
- **Voice features** depend entirely on the browser: speech recognition
  requires Chrome/Edge (Web Speech API) and, in most browsers, an internet
  connection to the vendor's recognition service; speech synthesis uses only
  the voices installed on the device. When a feature, language or voice is
  unavailable the interface says so plainly instead of pretending it worked.
- **Model language:** the classifier was trained on English news and
  preprocessing discards every character outside `a–z`, so Tamil and Hindi
  input is neither translated nor meaningfully classified — the result page
  warns about this rather than showing a confident-looking but empty result.
- **3D visuals:** the WebGL scenes (neural network, scanner rings,
  comparison panels, statistic bars) are decorative only. They are loaded
  only on pages that declare a scene, pause off-screen and in background
  tabs, are hidden on small hero areas, and are replaced by CSS animations
  when WebGL is unavailable or `prefers-reduced-motion` is set — the site
  remains fully usable with no 3D at all.
- **Comparison Lab:** a similarity score measures word-set overlap after
  preprocessing; it says nothing about whether the articles are true, and
  two different model labels are never presented as evidence that the
  articles contradict each other.
- **Analytics dashboard:** charts and counters are computed live from the
  current browser session only (Flask signed cookie). They reset when the
  session ends or the server restarts, and are never shared between
  visitors — this is by design, not a bug.

---

## Security & Validation Notes

- Empty submissions (no headline and no article) are rejected both
  client-side and server-side.
- Input length is capped at 10,000 characters, enforced both client-side
  (JavaScript + `maxlength`) and server-side (Flask).
- All user-submitted text is rendered through Jinja's default auto-escaping
  — no raw/unsafe HTML rendering is used anywhere (including assistant
  replies and the no-JS chat fallback).
- Missing dataset and missing/corrupted model files are handled with
  friendly, non-technical error messages instead of raw stack traces.
- No third-party front-end assets at runtime: CSS, JavaScript, icons and the
  hero illustration all ship from `static/`, and the only libraries
  (Three.js, Chart.js) are **vendored into `static/js/vendor/`** — nothing
  depends on a CDN at runtime (and nothing breaks if one is unreachable).
  `scene3d.js` fetches three.js only when a page actually declares a 3D
  scene, so other pages never pay for it.
- Uploaded documents are validated by extension (`.txt`, `.pdf`, `.docx`)
  and size (2 MB max), read into memory a single time, parsed with dedicated
  libraries, never executed and never written to disk. Empty and unreadable
  files are rejected with a friendly message before the model is touched,
  and the server never echoes internal stack traces to the browser.
- No API keys are used or exposed: the feed and the assistant are local,
  and nothing user-submitted is sent to an external service.
