"""
app.py

Flask web application for the "Fake News Detection Using Data Science"
college project.

Routes:
    GET  /            -> redesigned home page (hero, workflow, live preview form)
    GET  /detect      -> news-input form + document upload panel
    POST /predict     -> runs the ML prediction and renders the result page
    POST /upload      -> extracts text from a TXT/PDF/DOCX file and predicts
    GET/POST /compare -> News Comparison Lab (two articles, same model)
    GET  /analytics   -> Intelligence Analytics dashboard (session data only)
    GET  /feed        -> news feed interface (clearly labelled demo content)
    GET  /assistant   -> AI News Assistant chat interface
    POST /assistant/ask -> rule-based assistant replies (JSON)
    GET  /assistant/history -> session conversation history (JSON, voice widget)
    POST /assistant/clear   -> clears the session conversation history (JSON)
    GET  /about       -> about page (including the model card)
    GET  /healthz     -> lightweight health check used by the hosting platform
    404 / 500         -> friendly error pages

Session-based statistics (total checked / real / fake) are stored in the
Flask session so that each visitor sees their own running counts. This is
NOT a persistent database - refreshing after closing the browser / clearing
cookies resets the counts, which is expected behavior for a lightweight
college demonstration project.
"""

import io
import logging
import os
import re
import secrets
import time
from collections import Counter
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, render_template, request, session

import assistant as assistant_engine
import model as ml
import news_feed

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Secret key
# ---------------------------------------------------------------------------
# Prefer an environment variable in any real deployment. Fall back to a
# randomly generated key for local/demo use so the app still runs out of the
# box. NOTE: because this fallback key is regenerated every process start,
# sessions (and therefore dashboard stats) reset whenever the server restarts.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

MAX_INPUT_LENGTH = 10_000
ARTICLE_PREVIEW_LENGTH = 500

# --- Document upload -------------------------------------------------------
# Files are read into memory (never executed, never permanently stored) and
# rejected before parsing if they exceed the size or extension limits.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_UPLOAD_EXTENSIONS = (".txt", ".pdf", ".docx")

# pypdf logs parser warnings (e.g. "EOF marker not found" for corrupt files)
# to stderr; extraction failures are already converted into friendly messages
# below, so keep the server log clean.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# --- AI News Assistant -----------------------------------------------------
ASSISTANT_MAX_MESSAGE = 6_000

# Conversation history shown by the floating voice assistant. Session-scoped
# (Flask signed cookie) and capped so a long chat can never bloat the cookie.
ASSISTANT_HISTORY_LIMIT = 40

# --- Voice intelligence ----------------------------------------------------
# Speech recognition / synthesis locales offered by the UI. Availability of
# any specific locale depends entirely on the browser and installed OS
# voices; the front end detects this at runtime and reports it honestly
# instead of pretending an unsupported language works.
SUPPORTED_VOICE_LANGUAGES = (
    {"code": "en-IN", "label": "English (India)", "short": "English"},
    {"code": "ta-IN", "label": "Tamil (India)", "short": "Tamil"},
    {"code": "hi-IN", "label": "Hindi (India)", "short": "Hindi"},
)

# Control characters that must never survive text extraction (newlines and
# tabs are intentionally preserved).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def get_stats() -> dict:
    """Fetch (or initialize) the current-session statistics dict."""
    if "stats" not in session:
        session["stats"] = {"total": 0, "real": 0, "fake": 0}
    return session["stats"]


def update_stats(label: str) -> dict:
    """Increment session statistics based on a prediction label."""
    stats = get_stats()
    stats["total"] += 1
    if label == "REAL":
        stats["real"] += 1
    else:
        stats["fake"] += 1
    session["stats"] = stats
    session.modified = True
    return stats


# ---------------------------------------------------------------------------
# Per-session analysis history (powers the Intelligence Analytics dashboard)
# ---------------------------------------------------------------------------
# Like the counters above, this lives in the signed Flask session cookie:
# each visitor only ever sees their own analyses, nothing is shared between
# users, and closing the browser / restarting the server clears it. Entries
# are shape-checked on read so a tampered cookie can never inject markup or
# bogus labels into the dashboard.
ANALYSIS_HISTORY_LIMIT = 30


def get_analysis_history() -> list[dict]:
    """Return the current session's validated analysis history (oldest first)."""
    history = session.get("analysis_history")
    if not isinstance(history, list):
        return []
    clean = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        ts = entry.get("ts")
        if label not in ("REAL", "FAKE") or not isinstance(ts, (int, float)):
            continue
        confidence = entry.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = None
        clean.append(
            {
                "label": label,
                "confidence": round(float(confidence), 2)
                if confidence is not None
                else None,
                "snippet": str(entry.get("snippet") or "")[:160],
                "ts": float(ts),
            }
        )
    return clean


def append_analysis_history(headline: str, article: str, result: dict) -> None:
    """Remember one real prediction for the analytics dashboard (session only)."""
    raw = (headline or "").strip() or (article or "").strip()
    snippet = re.sub(r"\s+", " ", raw).strip()[:150]
    history = get_analysis_history()
    history.append(
        {
            "label": result.get("label"),
            "confidence": result.get("confidence"),
            "snippet": snippet,
            "ts": time.time(),
        }
    )
    session["analysis_history"] = history[-ANALYSIS_HISTORY_LIMIT:]
    session.modified = True


# ---------------------------------------------------------------------------
# Assistant conversation history (session-scoped, used by the voice widget)
# ---------------------------------------------------------------------------
def get_assistant_history() -> list[dict]:
    """Return the current session's assistant chat history as a list."""
    history = session.get("assistant_history")
    if not isinstance(history, list):
        return []
    # Defensive filter: only well-formed, in-cap messages ever reach a client.
    clean = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        text = entry.get("text")
        if role in ("user", "assistant") and isinstance(text, str) and text:
            clean.append({"role": role, "text": text[:ASSISTANT_MAX_MESSAGE]})
    return clean


def append_assistant_history(user_message: str, reply: str) -> None:
    """Append one user/assistant exchange, trimming to the history cap."""
    history = get_assistant_history()
    history.append({"role": "user", "text": user_message[:ASSISTANT_MAX_MESSAGE]})
    history.append({"role": "assistant", "text": reply[:ASSISTANT_MAX_MESSAGE]})
    session["assistant_history"] = history[-ASSISTANT_HISTORY_LIMIT:]
    session.modified = True


# ---------------------------------------------------------------------------
# Model language capability (English-only preprocessing — see model.py)
# ---------------------------------------------------------------------------
_DEVANAGARI_RE = re.compile("[\u0900-\u097F]")  # Hindi / Devanagari block
_TAMIL_RE = re.compile("[\u0B80-\u0BFF]")  # Tamil block


def script_language_warning(headline: str, article: str) -> str | None:
    """
    Honestly describe when a prediction cannot be trusted because of script.

    model.preprocess_text() keeps only the ASCII letters a-z, so Tamil or
    Hindi (Devanagari) characters are stripped before vectorization and an
    English-only classifier would then score an effectively empty string.
    This app never silently translates: instead we attach a clear warning so
    the user knows the result below is unreliable for non-English text.
    """
    raw = f"{headline or ''} {article or ''}".strip()
    if not raw:
        return None

    scripts = []
    if _TAMIL_RE.search(raw):
        scripts.append("Tamil")
    if _DEVANAGARI_RE.search(raw):
        scripts.append("Hindi (Devanagari)")
    if scripts:
        joined = " and ".join(scripts)
        return (
            f"This text contains {joined} script, but the model in this project "
            "was trained on English news only: preprocessing keeps just the "
            "English letters a–z, so these characters are removed before "
            "classification. This application does not translate text, and the "
            "prediction below is therefore unreliable for this input — submit "
            "an English version of the article for a meaningful result."
        )

    if not ml.preprocess_text(raw):
        return (
            "After preprocessing, no English letters remained in this text, so "
            "the classifier received an empty feature string. The prediction "
            "below cannot be considered reliable."
        )
    return None


def get_model_metrics() -> dict:
    """
    Return the evaluation metrics recorded inside the trained model bundle.

    These numbers are produced by train_model.py at training time and saved
    into model/fake_news_model.pkl alongside the vectorizer and classifier.
    Nothing here is hard-coded: if the bundle carries no metrics (for example
    a model trained by an older script), an empty dict is returned and the
    About page renders an explanatory message instead of showing figures.
    """
    try:
        bundle = ml.load_model()
    except Exception:  # noqa: BLE001 - missing/corrupt model must not break the page
        return {}

    metrics = bundle.get("metrics")
    if isinstance(metrics, dict) and metrics:
        return metrics
    return {}


@app.context_processor
def inject_stats():
    """Make current stats and page context available to every template."""
    return {
        "stats": get_stats(),
        # Drives the active indicator in the shared navigation bar.
        "active_page": request.endpoint or "",
        "current_year": date.today().year,
        # Locales offered by every voice-language dropdown in the UI.
        "voice_languages": SUPPORTED_VOICE_LANGUAGES,
    }


@app.template_filter("timestamp_label")
def timestamp_label(ts) -> str:
    """Human-friendly local timestamp for analytics history rows."""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%d %b, %I:%M %p")
    except (TypeError, ValueError, OSError, OverflowError):
        # A tampered/odd cookie value must never break the dashboard.
        return "unknown time"


@app.route("/healthz")
def healthz():
    """Lightweight health check used by the hosting platform."""
    return {"status": "ok", "model_ready": ml.model_exists()}


@app.route("/")
def index():
    return render_template(
        "index.html",
        model_ready=ml.model_exists(),
        metrics=get_model_metrics(),
        # Clearly labelled demonstration entries for the "Latest news" section.
        latest_news=news_feed.all_articles()[:3],
    )


@app.route("/detect")
def detect():
    """Dedicated news-input page hosting the real prediction form."""
    return render_template("detect.html", model_ready=ml.model_exists())


@app.route("/about")
def about():
    return render_template("about.html", metrics=get_model_metrics())


def detect_page(**context):
    """Render /detect with the model state injected unless already given."""
    context.setdefault("model_ready", ml.model_exists())
    return render_template("detect.html", **context)


def run_prediction(headline: str, article: str, *, error_field: str = "error",
                   source_note: str | None = None):
    """
    Shared prediction flow used by POST /predict and POST /upload.

    Validation, model loading, prediction, statistics and rendering behave
    exactly as they always have for the original form; the extras are:

        error_field  - which template variable receives a validation/model
                       message ("error" for the analysis form, "upload_error"
                       for the document upload panel)
        source_note  - optional provenance line shown on the result page
                       (used for uploaded documents)
    """
    # --- Validation -------------------------------------------------------
    if not headline and not article:
        return detect_page(
            **{
                error_field: "Please enter a news headline or article before checking.",
                "headline": headline,
                "article": article,
            }
        )

    combined_length = len(headline) + len(article)
    if combined_length > MAX_INPUT_LENGTH:
        return detect_page(
            **{
                error_field: (
                    f"Input is too long. Please limit your text to "
                    f"{MAX_INPUT_LENGTH:,} characters."
                ),
                "headline": headline,
                "article": article,
            }
        )

    # --- Model loading ------------------------------------------------------
    try:
        bundle = ml.load_model()
    except ml.ModelNotFoundError:
        return detect_page(
            model_ready=False,
            **{
                error_field: (
                    "The trained model is not available. Please place your dataset "
                    "at dataset/news.csv and run 'python train_model.py'."
                ),
                "headline": headline,
                "article": article,
            },
        )
    except ml.ModelLoadError as exc:
        return detect_page(
            model_ready=False,
            **{error_field: str(exc), "headline": headline, "article": article},
        )

    # --- Prediction -----------------------------------------------------
    try:
        result = ml.predict_news(headline, article, bundle)
    except Exception:
        # Never leak internal stack traces to the end user.
        return detect_page(
            **{
                error_field: (
                    "Something went wrong while analyzing this text. Please try again."
                ),
                "headline": headline,
                "article": article,
            }
        )

    stats = update_stats(result["label"])
    # Remember the analysis for the Intelligence Analytics dashboard
    # (session-scoped — other visitors never see it).
    append_analysis_history(headline, article, result)

    # Remember the latest real prediction so the AI News Assistant can
    # explain it on request (session-scoped, never fabricated).
    session["last_prediction"] = {
        "label": result["label"],
        "confidence": result["confidence"],
    }
    session.modified = True

    article_preview = article
    truncated = False
    if len(article_preview) > ARTICLE_PREVIEW_LENGTH:
        article_preview = article_preview[:ARTICLE_PREVIEW_LENGTH]
        truncated = True

    if result["label"] == "FAKE":
        explanation = (
            "The machine-learning model classified this text as potentially "
            "misleading based on patterns learned from the training dataset."
        )
    else:
        explanation = (
            "The machine-learning model classified this text as likely real "
            "based on patterns learned from the training dataset."
        )

    return render_template(
        "result.html",
        headline=headline,
        article_preview=article_preview,
        truncated=truncated,
        label=result["label"],
        confidence=result["confidence"],
        explanation=explanation,
        stats=stats,
        source_note=source_note,
        # Honest notice when the English-only preprocessing made the input
        # unusable (Tamil/Hindi script or no ASCII letters left).
        language_warning=script_language_warning(headline, article),
    )


@app.route("/predict", methods=["POST"])
def predict():
    headline = (request.form.get("headline") or "").strip()
    article = (request.form.get("article") or "").strip()
    return run_prediction(headline, article)


# ---------------------------------------------------------------------------
# News Comparison Lab (/compare)
# ---------------------------------------------------------------------------
def text_similarity(text_a: str, text_b: str) -> dict:
    """
    Genuine word-level similarity between two texts.

    Both texts go through the model's own preprocessing (model.py), then a
    Jaccard index over the resulting word sets is computed together with the
    shared vocabulary. Every number returned here is calculated from the
    submitted text — nothing is estimated or invented. An empty side (no
    English letters survived preprocessing) yields jaccard=None so the page
    can say "not comparable" instead of showing a fake 0%.
    """
    words_a = ml.preprocess_text(text_a or "").split()
    words_b = ml.preprocess_text(text_b or "").split()
    set_a, set_b = set(words_a), set(words_b)
    union = set_a | set_b
    intersection = set_a & set_b

    jaccard = None
    if union:
        jaccard = round(100.0 * len(intersection) / len(union), 1)

    # Shared terms ranked by combined frequency (Counter addition keeps only
    # keys present in both counters, so the result really is shared vocabulary).
    shared_terms = [
        word for word, _ in (Counter(words_a) + Counter(words_b)).most_common(12)
    ]

    # Terms only one side uses, ranked by how often they appear on that side.
    # These are real vocabulary differences computed from the submitted text.
    unique_a_terms = [
        word for word, _ in Counter(words_a).most_common(40) if word in set_a - set_b
    ][:8]
    unique_b_terms = [
        word for word, _ in Counter(words_b).most_common(40) if word in set_b - set_a
    ][:8]

    return {
        "jaccard": jaccard,
        "shared_terms": shared_terms,
        "unique_a_terms": unique_a_terms,
        "unique_b_terms": unique_b_terms,
        "shared_count": len(intersection),
        "unique_a": len(set_a - set_b),
        "unique_b": len(set_b - set_a),
        "words_a": len(words_a),
        "words_b": len(words_b),
        "comparable": bool(union),
    }


def _compare_side(headline: str, article: str, error_field: str):
    """
    Validate one side of the comparison form.

    Returns (None, error_message) on failure or (combined_text, None) on
    success, where combined_text is what the model would actually score.
    """
    label = "Article A" if error_field == "error_a" else "Article B"
    if not headline and not article:
        return None, f"Please enter a headline or article text for {label}."
    if len(headline) + len(article) > MAX_INPUT_LENGTH:
        return None, (
            f"{label} is too long. Please limit each article to "
            f"{MAX_INPUT_LENGTH:,} characters in total."
        )
    return f"{headline.strip()} {article.strip()}".strip(), None


@app.route("/compare", methods=["GET", "POST"])
def compare():
    """
    News Comparison Lab: run the SAME trained model over two articles and
    present both predictions side by side with a genuine word-level
    similarity calculation.

    Differing labels are never presented as proof that one article is
    factually wrong — two model outputs are still just two model outputs.
    """
    if request.method == "GET":
        return render_template("compare.html", model_ready=ml.model_exists())

    headline_a = (request.form.get("headline_a") or "").strip()
    article_a = (request.form.get("article_a") or "").strip()
    headline_b = (request.form.get("headline_b") or "").strip()
    article_b = (request.form.get("article_b") or "").strip()

    context = {
        "headline_a": headline_a,
        "article_a": article_a,
        "headline_b": headline_b,
        "article_b": article_b,
        "model_ready": ml.model_exists(),
    }

    combined_a, error_a = _compare_side(headline_a, article_a, "error_a")
    combined_b, error_b = _compare_side(headline_b, article_b, "error_b")
    if error_a or error_b:
        context["error_a"] = error_a
        context["error_b"] = error_b
        return render_template("compare.html", **context)

    try:
        bundle = ml.load_model()
    except ml.ModelNotFoundError:
        context["error"] = (
            "The trained model is not available. Please place your dataset "
            "at dataset/news.csv and run 'python train_model.py'."
        )
        return render_template("compare.html", **context)
    except ml.ModelLoadError as exc:
        context["error"] = str(exc)
        return render_template("compare.html", **context)

    try:
        # Both articles are scored by the SAME loaded bundle: identical
        # preprocessing, identical vectorizer, identical classifier.
        result_a = ml.predict_news(headline_a, article_a, bundle)
        result_b = ml.predict_news(headline_b, article_b, bundle)
    except Exception:  # noqa: BLE001 - never leak stack traces to the client
        context["error"] = (
            "Something went wrong while analyzing these articles. Please try again."
        )
        return render_template("compare.html", **context)

    # Both analyses are real model runs, so both count toward this session's
    # statistics and history — exactly like two separate /predict submissions.
    for hl, art, res in (
        (headline_a, article_a, result_a),
        (headline_b, article_b, result_b),
    ):
        update_stats(res["label"])
        append_analysis_history(hl, art, res)

    similarity = text_similarity(combined_a, combined_b)

    confidence_gap = None
    if result_a["confidence"] is not None and result_b["confidence"] is not None:
        confidence_gap = round(abs(result_a["confidence"] - result_b["confidence"]), 2)

    context.update(
        {
            "analyzed": True,
            "result_a": result_a,
            "result_b": result_b,
            "similarity": similarity,
            "labels_match": result_a["label"] == result_b["label"],
            "confidence_gap": confidence_gap,
            "warning_a": script_language_warning(headline_a, article_a),
            "warning_b": script_language_warning(headline_b, article_b),
            "explanation_a": (
                "The machine-learning model classified this text as potentially "
                "misleading based on patterns learned from the training dataset."
                if result_a["label"] == "FAKE"
                else "The machine-learning model classified this text as likely real "
                "based on patterns learned from the training dataset."
            ),
            "explanation_b": (
                "The machine-learning model classified this text as potentially "
                "misleading based on patterns learned from the training dataset."
                if result_b["label"] == "FAKE"
                else "The machine-learning model classified this text as likely real "
                "based on patterns learned from the training dataset."
            ),
        }
    )
    return render_template("compare.html", **context)


# ---------------------------------------------------------------------------
# Intelligence Analytics dashboard (/analytics)
# ---------------------------------------------------------------------------
@app.route("/analytics")
def analytics():
    """
    Session-scoped analytics dashboard.

    Every figure on this page comes from real data: the session's own
    counters and analysis history, or metrics recorded inside the trained
    model bundle at training time. No sample data is ever mixed in, and one
    visitor's history is never visible to another (it lives in their own
    signed session cookie).
    """
    stats = get_stats()
    history = get_analysis_history()

    # --- Recent activity (newest first, capped for display) ---------------
    recent = list(reversed(history[-8:]))

    # --- Weekly activity: only when timestamps exist ----------------------
    weekly = []
    if history:
        today = date.today()
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        counts = {d.isoformat(): 0 for d in days}
        for entry in history:
            # Session timestamps are local epoch seconds; a value outside the
            # last 7 days simply falls outside the buckets and is ignored.
            day = datetime.fromtimestamp(entry["ts"]).date().isoformat()
            if day in counts:
                counts[day] += 1
        weekly = [
            {
                "day": d.strftime("%a"),
                "date": d.isoformat(),
                "count": counts[d.isoformat()],
            }
            for d in days
        ]

    # --- Label distribution (genuine, derived from the counters) ----------
    distribution = {"REAL": stats["real"], "FAKE": stats["fake"]}

    return render_template(
        "analytics.html",
        stats=stats,
        recent=recent,
        weekly=weekly,
        distribution=distribution,
        has_history=bool(history),
        history_limit=ANALYSIS_HISTORY_LIMIT,
        metrics=get_model_metrics(),
    )


# ---------------------------------------------------------------------------
# Document upload (TXT / PDF / DOCX)
# ---------------------------------------------------------------------------
def extract_document_text(file_storage) -> tuple[str | None, str | None]:
    """
    Safely extract plain text from an uploaded file.

    The file is read into memory at most once, capped at MAX_UPLOAD_BYTES,
    parsed according to its extension, and never executed or written to disk.
    Empty and unreadable documents are rejected with a friendly message.

    Returns:
        (text, None) on success, (None, error_message) on failure.
    """
    filename = (file_storage.filename or "").strip()
    extension = os.path.splitext(filename)[1].lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        supported = ", ".join(ext.upper() for ext in ALLOWED_UPLOAD_EXTENSIONS)
        return None, f"Unsupported file type. Please upload one of: {supported}."

    # Read one byte beyond the limit so oversized files can be detected
    # without ever holding more than the limit + 1 in memory.
    data = file_storage.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        return None, (
            f"File is too large. The maximum allowed size is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    if not data:
        return None, "The selected file is empty."

    try:
        if extension == ".txt":
            # utf-8-sig handles BOMs; errors="replace" keeps odd byte
            # sequences readable instead of crashing the request.
            text = data.decode("utf-8-sig", errors="replace")
        elif extension == ".pdf":
            from pypdf import PdfReader  # lazy: dependency lives in requirements

            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
        else:  # .docx
            import docx  # lazy: python-docx package

            document = docx.Document(io.BytesIO(data))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception:  # noqa: BLE001 - any parse failure gets a friendly message
        readable = extension.upper().lstrip(".")
        return None, (
            f"The file could not be read as a {readable} document. It may be "
            "corrupted, password-protected or not really a {readable} file."
        )

    text = _CONTROL_CHARS_RE.sub(" ", text or "").strip()
    if not text:
        return None, (
            "No readable text was found in the document. The file may be "
            "image-only, corrupted or empty."
        )
    return text, None


@app.route("/upload", methods=["POST"])
def upload():
    """Extract text from an uploaded document and run the real prediction."""
    document = request.files.get("document")
    if document is None or not (document.filename or "").strip():
        return detect_page(upload_error="Please choose a file to upload before analyzing.")

    text, error = extract_document_text(document)
    if error:
        return detect_page(upload_error=error)

    truncated = len(text) > MAX_INPUT_LENGTH
    if truncated:
        text = text[:MAX_INPUT_LENGTH]

    filename = os.path.basename(document.filename.strip())
    source_note = f"Uploaded document: {filename}"
    if truncated:
        source_note += f" (first {MAX_INPUT_LENGTH:,} characters analyzed)"

    # The extracted text travels through the exact same prediction flow as
    # typed input: same validation, same model, same result page.
    return run_prediction("", text, error_field="upload_error",
                          source_note=source_note)


# ---------------------------------------------------------------------------
# News feed (demonstration content — no news API is configured)
# ---------------------------------------------------------------------------
@app.route("/feed")
def feed():
    raw_category = (request.args.get("category") or "").strip()
    query = (request.args.get("q") or "").strip()

    # Known categories map to their canonical name; an unknown value is kept
    # as-is so it simply matches nothing and renders the empty state.
    known = {name.lower(): name for name in news_feed.categories()}
    active_category = known.get(raw_category.lower(), raw_category)

    articles = news_feed.filter_articles(active_category, query)

    # Trending is a separate block but only ever highlights articles that
    # pass the active filter, so the page stays internally consistent.
    filtered_ids = {item["id"] for item in articles}
    trending = [
        item for item in news_feed.trending_articles()
        if item["id"] in filtered_ids
    ]

    return render_template(
        "feed.html",
        articles=articles,
        trending=trending,
        categories=news_feed.categories(),
        active_category=active_category,
        query=query,
        feed_notice=news_feed.FEED_NOTICE,
        total_articles=len(news_feed.all_articles()),
    )


# ---------------------------------------------------------------------------
# AI News Assistant (rule-based — no external AI API is configured)
# ---------------------------------------------------------------------------
@app.route("/assistant")
def assistant():
    """Chat-style assistant interface."""
    return render_template(
        "assistant.html",
        last_prediction=session.get("last_prediction"),
        assistant_notice=assistant_engine.RULE_BASED_NOTICE,
        assistant_limitation=assistant_engine.LIMITATION,
    )


@app.route("/assistant/ask", methods=["POST"])
def assistant_ask():
    """Assistant replies as JSON for the chat UI, or an HTML fallback without JS."""
    payload = request.get_json(silent=True)
    if payload is None:
        # Plain form post (JavaScript disabled) — read the field instead.
        payload = request.form.to_dict() if request.form else {}

    message = str(payload.get("message") or "").strip()

    if not message:
        error = "Please enter a message before sending."
        if request.is_json:
            return jsonify({"error": error}), 400
        return render_template(
            "assistant.html",
            last_prediction=session.get("last_prediction"),
            assistant_notice=assistant_engine.RULE_BASED_NOTICE,
            assistant_limitation=assistant_engine.LIMITATION,
            initial_error=error,
        ), 400
    if len(message) > ASSISTANT_MAX_MESSAGE:
        error = (
            f"Message is too long. Please limit it to "
            f"{ASSISTANT_MAX_MESSAGE:,} characters."
        )
        if request.is_json:
            return jsonify({"error": error}), 400
        return render_template(
            "assistant.html",
            last_prediction=session.get("last_prediction"),
            assistant_notice=assistant_engine.RULE_BASED_NOTICE,
            assistant_limitation=assistant_engine.LIMITATION,
            initial_error=error,
        ), 400

    try:
        result = assistant_engine.respond(message, session.get("last_prediction"))
    except Exception:  # noqa: BLE001 - never leak stack traces to the client
        if request.is_json:
            return jsonify({
                "error": "The assistant could not process that message. Please try again."
            }), 500
        return render_template(
            "assistant.html",
            last_prediction=session.get("last_prediction"),
            assistant_notice=assistant_engine.RULE_BASED_NOTICE,
            assistant_limitation=assistant_engine.LIMITATION,
            initial_error="The assistant could not process that message. Please try again.",
        ), 500

    # Remember the exchange for the floating voice assistant widget so chat
    # history survives navigation within the same browser session.
    append_assistant_history(message, result["reply"])

    if request.is_json:
        return jsonify(result)

    # No-JS fallback: re-render the page with the reply already in the log.
    return render_template(
        "assistant.html",
        last_prediction=session.get("last_prediction"),
        assistant_notice=assistant_engine.RULE_BASED_NOTICE,
        assistant_limitation=assistant_engine.LIMITATION,
        initial_user=message,
        initial_reply=result["reply"],
    )


@app.route("/assistant/history")
def assistant_history():
    """
    Session conversation history for the floating voice assistant widget.

    Returns only the capped, shape-checked messages produced by
    append_assistant_history(); nothing user-supplied is echoed as HTML and
    no other session data is exposed.
    """
    return jsonify(
        {
            "messages": get_assistant_history(),
            "last_prediction": session.get("last_prediction"),
            "limit": ASSISTANT_HISTORY_LIMIT,
        }
    )


@app.route("/assistant/clear", methods=["POST"])
def assistant_clear():
    """Clear the current session's assistant conversation history."""
    session.pop("assistant_history", None)
    session.modified = True
    return jsonify({"ok": True, "messages": []})


@app.errorhandler(404)
def not_found(_error):
    # Dedicated 404 page (previously the About page was rendered for unknown
    # URLs, which read as a bug rather than an intentional fallback).
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_error):
    return (
        render_template(
            "index.html",
            model_ready=ml.model_exists(),
            error="An unexpected server error occurred. Please try again.",
        ),
        500,
    )


if __name__ == "__main__":
    # Local development server only. In production the app is served by
    # gunicorn (see Dockerfile / render.yaml), which imports `app:app`.
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
