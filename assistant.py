"""
assistant.py

Rule-based "AI News Assistant" for the Fake News Detection platform.

WHAT THIS IS
------------
A deterministic, keyword-driven response engine written in plain Python. It
answers questions about how the project's REAL machine-learning pipeline
works, explains predictions produced by model.predict_news(), runs heuristic
credibility checks over pasted text, and gives fact-checking advice.

WHAT THIS IS NOT
----------------
- It is NOT a generative AI / LLM. No external AI API is configured for this
  project, and this module never claims to be one. If an external AI service
  is ever added later it must be configured through an environment variable
  and tested before anyone advertises it as working.
- It NEVER claims a prediction proves an article is true or false. Every
  analysis response repeats the limitation.

This module contains no Flask code so it can be unit tested on its own.
"""

from __future__ import annotations

import re

import model as ml

# ---------------------------------------------------------------------------
# Shared honesty text
# ---------------------------------------------------------------------------
LIMITATION = (
    "Reminder: this platform performs statistical text classification. "
    "It does not browse the internet or verify claims against sources, and "
    "no output it produces proves that a story is true or false."
)

RULE_BASED_NOTICE = (
    "Assistant mode: rule-based (no external AI API is configured)."
)

# ---------------------------------------------------------------------------
# Heuristic red-flag patterns (advice only, never a verdict)
# ---------------------------------------------------------------------------
# (label, compiled pattern, why it is worth a second look)
SENSATIONAL_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Clickbait phrasing",
        re.compile(
            r"\b(you won'?t believe|shocking|unbelievable|mind-?blowing|"
            r"what happened next|is incredible|secret|exposed|banned)\b",
            re.I,
        ),
        "Headlines built on curiosity gaps are optimised for clicks, not accuracy.",
    ),
    (
        "Urgency / suppression claims",
        re.compile(
            r"\b(share (this )?before|before it gets deleted|they don'?t want "
            r"you to know|mainstream media (is|does not)|cover-?up|censored|"
            r"silenced|wake up)\b",
            re.I,
        ),
        "Claims that information is being hidden encourage sharing before checking.",
    ),
    (
        "Excessive punctuation",
        re.compile(r"!{2,}|\?{2,}"),
        "Repeated exclamation or question marks signal emotional rather than factual writing.",
    ),
    (
        "ALL-CAPS emphasis",
        re.compile(r"\b[A-Z]{4,}\b"),
        "Heavy capitalisation is a common trait of promotional or alarmist text.",
    ),
    (
        "Absolute language",
        re.compile(
            r"\b(always|never|everyone knows|no one (wants|will tell you)|"
            r"100%|guaranteed|miracle|instantly|effortless)\b",
            re.I,
        ),
        "Absolute claims rarely hold up without specific, checkable evidence.",
    ),
    (
        "Unverified superlatives",
        re.compile(r"\b(the (best|worst|most|only|first))\b", re.I),
        "Superlatives need a named source or measurement to be meaningful.",
    ),
]


def _find_signals(text: str) -> list[dict]:
    """Return every heuristic red flag triggered by the given text."""
    signals = []
    for label, pattern, why in SENSATIONAL_PATTERNS:
        match = pattern.search(text or "")
        if match:
            signals.append({"label": label, "match": match.group(0), "why": why})
    return signals


def _looks_like_article(text: str) -> bool:
    """Heuristic: is this message long enough to be treated as article text?"""
    if not text:
        return False
    words = text.split()
    return len(text) >= 80 and len(words) >= 15


# ---------------------------------------------------------------------------
# Intents
# ---------------------------------------------------------------------------
_GREETING = re.compile(r"^\s*(hi|hello|hey|yo|good (morning|evening))\b", re.I)

_HOW_IT_WORKS = re.compile(
    r"\b(how (does|do) (it|this|the model|you)|pipeline|work flow|workflow|"
    r"preprocess|pre-process|clean(ing)?|tf-?idf|vectoriz|feature extraction|"
    r"classif|algorithm|logistic|train(ing)?|stage)\b",
    re.I,
)

_EXPLAIN_RESULT = re.compile(
    r"\b(explain|meaning|mean|understand|confidence|probability|score|"
    r"label|real or fake|why (is|was) it|interpret|result|prediction)\b",
    re.I,
)

_CHECK_TEXT = re.compile(
    r"\b(check|analy[sz]e|analyse|verify|assess|scan|judge|look at|opinion on)\b",
    re.I,
)

_MISLEADING = re.compile(
    r"\b(misleading|red flag|suspicious|manipulat|sensational|clickbait|"
    r"misleading statement|bias|propaganda|exaggerat)\b",
    re.I,
)

_CREDIBILITY = re.compile(
    r"\b(credible|credibility|fact-?check|how (do|can) i (check|verify)|"
    r"trust|reliable|source|bias|before (i|you) share)\b",
    re.I,
)

_ABOUT_ASSISTANT = re.compile(
    r"\b(are you (an? )?(ai|chatgpt|llm|gpt|bot|generative)|who are you|"
    r"what are you|your model|are you (a )?real ai)\b",
    re.I,
)

_LIMITATIONS = re.compile(
    r"\b(limit\w*|accura\w*|prove|proof|guarantee\w*|definitive|100%|"
    r"always right|wrong|false positive|false negative|bias)\b",
    re.I,
)

_UPLOAD_HELP = re.compile(
    r"\b(upload|document|\.pdf|\.docx|\.txt|file|drag|drop)\b", re.I
)

_FEED_HELP = re.compile(r"\b(news feed|feed|latest news|trending|articles?)\b", re.I)


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------
def _reply(text: str, intent: str) -> dict:
    return {"reply": text.strip(), "intent": intent, "mode": "rule-based"}


def _run_model_on(text: str) -> dict | None:
    """Run the project's real model on a piece of text; None if unavailable."""
    try:
        bundle = ml.load_model()
        return ml.predict_news("", text, bundle)
    except Exception:  # noqa: BLE001 - assistant must never crash the route
        return None


def _explain_prediction(result: dict) -> str:
    label = result["label"]
    confidence = result.get("confidence")
    lines = [
        f"The trained classifier labelled that text: {label}.",
    ]
    if confidence is not None:
        lines.append(
            f"Confidence of the predicted class: {confidence}% "
            "(the probability the model assigned to "
            f"{label} — not a measure of whether the story is true)."
        )
    else:
        lines.append(
            "No confidence value is available for this prediction "
            "(the model did not return usable class probabilities, and none "
            "has been invented)."
        )
    if label == "FAKE":
        lines.append(
            "What this means: the text resembles statistical patterns the "
            "model learned from examples labelled FAKE in the training data. "
            "It does not mean the story has been disproved."
        )
    else:
        lines.append(
            "What this means: the text resembles statistical patterns the "
            "model learned from examples labelled REAL in the training data. "
            "It does not mean the story has been confirmed."
        )
    return "\n\n".join(lines)


def _analysis_reply(text: str, signals: list[dict] | None = None) -> str:
    result = _run_model_on(text)
    parts: list[str] = []

    if result is None:
        parts.append(
            "I could not run the model on that text — the trained model file "
            "is not available right now (train it with "
            "'python train_model.py')."
        )
    else:
        parts.append(_explain_prediction(result))

    if signals is None:
        signals = _find_signals(text)

    if signals:
        parts.append("Heuristic checks on the wording (advice, not a verdict):")
        for s in signals:
            parts.append(f"- {s['label']}: found {s['match']!r}. {s['why']}")
    else:
        parts.append(
            "Heuristic checks on the wording: no strong sensationalist "
            "patterns detected. That does NOT mean the text is accurate — "
            "these checks only look at style, not facts."
        )

    parts.append(LIMITATION)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def respond(message: str, last_prediction: dict | None = None) -> dict:
    """
    Turn a user message into an assistant reply.

    Args:
        message: the raw user message (already length-checked by the caller).
        last_prediction: optional dict with "label"/"confidence" from the
            user's most recent analysis in this session, used to answer
            "explain my prediction" questions with real data.

    Returns:
        {"reply": str, "intent": str, "mode": "rule-based"}
    """
    text = (message or "").strip()
    if not text:
        return _reply(
            "Please type a question. Try one of the suggestion chips below "
            "the chat box to get started.",
            "empty",
        )

    # 1. Greeting / small talk -------------------------------------------
    if _GREETING.match(text) and len(text) < 120:
        return _reply(
            "Hello! I'm the News Intelligence Assistant for this project.\n\n"
            "I can:\n"
            "- explain how the detection model actually processes text\n"
            "- explain a prediction, including what confidence means\n"
            "- scan pasted text for sensationalist wording (heuristics)\n"
            "- suggest practical steps for checking a claim yourself\n\n"
            + RULE_BASED_NOTICE
            + "\n"
            + LIMITATION,
            "greeting",
        )

    # 2. "What are you?" — always honest about being rule-based ----------
    if _ABOUT_ASSISTANT.search(text) and len(text) < 200:
        return _reply(
            "I am a rule-based assistant built into this Flask application — "
            "a small set of written response rules, not a generative AI "
            "model and not an external chatbot. No AI API key is configured "
            "for this project, so nothing you type is sent to a language "
            "model.\n\n"
            "The separate machine-learning model in this project is a "
            "TF-IDF + Logistic Regression text classifier trained on a "
            "labelled dataset. It labels text REAL or FAKE; it does not "
            "generate answers.\n\n"
            "I keep my answers to what this codebase can actually do.",
            "identity",
        )

    # 3. Pasted article + explicit ask to check/analyze it ---------------
    if _looks_like_article(text) and _CHECK_TEXT.search(text):
        return _reply(_analysis_reply(text), "analyze-text")

    # 4. Pasted article + request for misleading-statement analysis -------
    if _looks_like_article(text) and _MISLEADING.search(text):
        signals = _find_signals(text)
        parts = ["Here is what a wording scan of your text found:"]
        if signals:
            for s in signals:
                parts.append(f"- {s['label']}: {s['match']!r} — {s['why']}")
            parts.append(
                "These are writing-style signals only. None of them proves "
                "any statement is false; they are prompts to verify the "
                "claims independently."
            )
        else:
            parts.append(
                "- No strong sensationalist patterns were detected. Absence "
                "of flags is not evidence of accuracy — plain, calm writing "
                "can still contain false claims."
            )
        parts.append(LIMITATION)
        return _reply("\n\n".join(parts), "misleading-scan")

    # 5. Explain a prediction --------------------------------------------
    if _EXPLAIN_RESULT.search(text) and not _looks_like_article(text):
        if last_prediction:
            label = last_prediction.get("label")
            confidence = last_prediction.get("confidence")
            summary = f"Your most recent analysis in this session was: {label}"
            if confidence is not None:
                summary += f" (confidence {confidence}%)."
            else:
                summary += " (no confidence value was available)."
            return _reply(
                summary
                + "\n\n"
                + _explain_prediction(
                    {"label": label, "confidence": confidence}
                )
                + "\n\n"
                + "To explain a different text, paste it into the chat and "
                "say 'check this text'.\n\n"
                + LIMITATION,
                "explain-prediction",
            )
        return _reply(
            "Here is how to read any prediction on this platform:\n\n"
            "- REAL / FAKE: the single class the Logistic Regression "
            "classifier assigned to your text.\n"
            "- Confidence: the probability the model gave that class "
            "(predict_proba). It describes the model's certainty about its "
            "own label — it is NOT a probability that the story is true.\n"
            "- The label comes from statistical patterns in the training "
            "dataset, not from checking the claim against any source.\n\n"
            "Run an analysis first and ask me again, or paste text and say "
            "'check this text', and I will show you a real prediction with "
            "this explanation attached.\n\n"
            + LIMITATION,
            "explain-prediction",
        )

    # 6. How the pipeline works ------------------------------------------
    if _HOW_IT_WORKS.search(text) and not _looks_like_article(text):
        return _reply(
            "The real pipeline in this project (nothing here is simulated):\n\n"
            "1. Input — a headline and/or article body, up to 10,000 "
            "characters, validated on the server.\n"
            "2. Preprocessing — headline and article are combined into one "
            "text blob (model.combine_headline_and_article).\n"
            "3. Cleaning — model.preprocess_text lowercases the text, strips "
            "HTML tags, removes URLs, removes punctuation and non-alphabetic "
            "characters, then collapses whitespace.\n"
            "4. Feature extraction — the TF-IDF vectorizer fitted during "
            "training (max 5,000 features, unigrams + bigrams, min_df=2, "
            "English stop words) converts the cleaned text into numbers.\n"
            "5. Classification — a Logistic Regression classifier returns the "
            "predicted class.\n"
            "6. Prediction generation — the label plus, when available, the "
            "class probability from predict_proba() as a confidence "
            "percentage. If probabilities cannot be computed, no score is "
            "shown rather than an invented one.\n"
            "7. Result page — label, confidence (when available), the "
            "submitted text, a plain-language explanation and a disclaimer.\n\n"
            "Training uses the same cleaning function (imported from "
            "model.py) so training and prediction text are processed "
            "identically.",
            "how-it-works",
        )

    # 7. Heuristic request about misleading wording -----------------------
    if _MISLEADING.search(text) and not _looks_like_article(text):
        return _reply(
            "I can flag wording patterns commonly seen in misleading copy. "
            "Paste the text you want scanned and include a phrase such as "
            "'red flags' or 'misleading statements', and I will run the "
            "heuristic scan over it.\n\n"
            "What I look for: clickbait phrasing, urgency or suppression "
            "claims ('share before it's deleted'), repeated punctuation, "
            "ALL-CAPS emphasis, absolute language and unsourced "
            "superlatives.\n\n"
            "These are style signals, never proof — a clean-written article "
            "can still be wrong, and an alarmist one can still be true.",
            "misleading-help",
        )

    # 8. Credibility / fact-checking advice ------------------------------
    if _CREDIBILITY.search(text):
        return _reply(
            "Practical steps for checking a claim yourself:\n\n"
            "1. Find the original source — who published it, and is there a "
            "named author and date?\n"
            "2. Read beyond the headline — do the details in the body "
            "actually support the claim?\n"
            "3. Look for independent coverage — do other reputable outlets "
            "report the same thing?\n"
            "4. Check images and quotes — reverse-search images and confirm "
            "quotes in their full context.\n"
            "5. Watch for emotional triggers — urgency, outrage and "
            "'share before it's deleted' are pressure tactics.\n"
            "6. Consult established fact-checking organisations for "
            "widely circulated claims.\n\n"
            "This platform's model can offer a first-pass signal, but it "
            "cannot do any of the above for you — it never leaves the "
            "server to verify anything.\n\n"
            + LIMITATION,
            "credibility",
        )

    # 9. Limitations / accuracy questions --------------------------------
    if _LIMITATIONS.search(text) and not _looks_like_article(text):
        return _reply(
            "Honest limitations of this project:\n\n"
            "- It does not prove anything true or false. It reports a "
            "statistical label learned from a labelled dataset.\n"
            "- It does not browse the web, check sources or read metadata.\n"
            "- It can be wrong — especially on sarcasm, satire, new topics "
            "or text unlike its training data.\n"
            "- Its accuracy depends entirely on the dataset it was trained "
            "from; dataset bias becomes model bias.\n"
            "- Confidence is the model's probability for its own label, not "
            "the probability that the story is accurate.\n\n"
            "Treat every output as one signal to weigh alongside real "
            "fact-checking, never as a verdict.",
            "limitations",
        )

    # 10. Upload help ----------------------------------------------------
    if _UPLOAD_HELP.search(text) and not _looks_like_article(text):
        return _reply(
            "Document upload works like this on the Detect News page:\n\n"
            "- Drag a file onto the upload zone or use the file button "
            "(TXT, PDF or DOCX, up to 2 MB).\n"
            "- The server reads the file in memory, extracts its plain text "
            "(pypdf for PDF, python-docx for DOCX) and never executes or "
            "permanently stores it.\n"
            "- The extracted text is capped at the same 10,000-character "
            "limit as typed input, then passed to the real prediction "
            "pipeline.\n"
            "- Empty or unreadable files are rejected with a clear message.\n\n"
            + LIMITATION,
            "upload-help",
        )

    # 11. Feed help ------------------------------------------------------
    if _FEED_HELP.search(text) and not _looks_like_article(text):
        return _reply(
            "The News Feed page shows demonstration content only: no news "
            "API is configured for this project, so every card is sample "
            "text with a visible 'Demo' badge, a 'Demonstration content' "
            "source line and a 'Sample entry' date.\n\n"
            "Use the category chips and the search bar to filter the cards, "
            "and 'Read more' to expand a sample body. To show real "
            "reporting, wire the feed to a properly configured and tested "
            "news API.",
            "feed-help",
        )

    # 12. Fallback -------------------------------------------------------
    return _reply(
        "I'm a rule-based assistant, so I answer best within these topics:\n\n"
        "- how the model preprocesses, vectorizes and classifies text\n"
        "- what a REAL/FAKE label and a confidence percentage mean\n"
        "- scanning pasted text for sensationalist wording (heuristics)\n"
        "- practical fact-checking and credibility tips\n"
        "- document upload, the demo news feed and this page's limits\n\n"
        "Try: 'How does the model work?', paste an article and say 'check "
        "this text', or ask 'how do I check if a claim is credible?'.\n\n"
        + RULE_BASED_NOTICE
        + "\n"
        + LIMITATION,
        "fallback",
    )
