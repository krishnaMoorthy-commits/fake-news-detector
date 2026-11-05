"""
app.py

Flask web application for the "Fake News Detection Using Data Science"
college project.

Routes:
    GET  /            -> redesigned home page (hero, workflow, live preview form)
    GET  /detect      -> news-input form + document upload panel
    POST /predict     -> runs the ML prediction and renders the result page
    POST /upload      -> extracts text from a TXT/PDF/DOCX file and predicts
    GET  /feed        -> news feed interface (clearly labelled demo content)
    GET  /assistant   -> AI News Assistant chat interface
    POST /assistant/ask -> rule-based assistant replies (JSON)
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
from datetime import date

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
    }


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
    )


@app.route("/predict", methods=["POST"])
def predict():
    headline = (request.form.get("headline") or "").strip()
    article = (request.form.get("article") or "").strip()
    return run_prediction(headline, article)


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
