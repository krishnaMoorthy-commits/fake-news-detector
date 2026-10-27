"""
app.py

Flask web application for the "Fake News Detection Using Data Science"
college project.

Routes:
    GET  /            -> redesigned home page (hero, pipeline, live preview form)
    GET  /detect      -> dedicated news-input / prediction form page
    POST /predict     -> runs the ML prediction and renders the result page
    GET  /about       -> about page (including the model card)
    GET  /healthz     -> lightweight health check used by the hosting platform
    404 / 500         -> friendly error pages

Session-based statistics (total checked / real / fake) are stored in the
Flask session so that each visitor sees their own running counts. This is
NOT a persistent database - refreshing after closing the browser / clearing
cookies resets the counts, which is expected behavior for a lightweight
college demonstration project.
"""

import os
import secrets
from datetime import date

from flask import Flask, render_template, request, session

import model as ml

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
    return render_template("index.html", model_ready=ml.model_exists())


@app.route("/detect")
def detect():
    """Dedicated news-input page hosting the real prediction form."""
    return render_template("detect.html", model_ready=ml.model_exists())


@app.route("/about")
def about():
    return render_template("about.html", metrics=get_model_metrics())


@app.route("/predict", methods=["POST"])
def predict():
    headline = (request.form.get("headline") or "").strip()
    article = (request.form.get("article") or "").strip()

    # --- Validation -------------------------------------------------------
    if not headline and not article:
        return render_template(
            "detect.html",
            model_ready=ml.model_exists(),
            error="Please enter a news headline or article before checking.",
            headline=headline,
            article=article,
        )

    combined_length = len(headline) + len(article)
    if combined_length > MAX_INPUT_LENGTH:
        return render_template(
            "detect.html",
            model_ready=ml.model_exists(),
            error=f"Input is too long. Please limit your text to {MAX_INPUT_LENGTH:,} characters.",
            headline=headline,
            article=article,
        )

    # --- Model loading ------------------------------------------------------
    try:
        bundle = ml.load_model()
    except ml.ModelNotFoundError:
        return render_template(
            "detect.html",
            model_ready=False,
            error=(
                "The trained model is not available. Please place your dataset "
                "at dataset/news.csv and run 'python train_model.py'."
            ),
            headline=headline,
            article=article,
        )
    except ml.ModelLoadError as exc:
        return render_template(
            "detect.html",
            model_ready=False,
            error=str(exc),
            headline=headline,
            article=article,
        )

    # --- Prediction -----------------------------------------------------
    try:
        result = ml.predict_news(headline, article, bundle)
    except Exception:
        # Never leak internal stack traces to the end user.
        return render_template(
            "detect.html",
            model_ready=ml.model_exists(),
            error="Something went wrong while analyzing this text. Please try again.",
            headline=headline,
            article=article,
        )

    stats = update_stats(result["label"])

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
