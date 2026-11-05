"""
End-to-end test suite for the redesigned Fake News Detection app.

Run with:  python _test_app.py

Everything below exercises the REAL Flask application object and the REAL
machine-learning model — no mocking of prediction logic (the only patch is a
counter wrapper around model.predict_news so we can prove it was invoked).

Covers: page rendering, navigation integrity, the prediction workflow,
document upload (TXT / PDF / DOCX plus failure modes), the news feed,
the rule-based AI News Assistant, and template escaping.
"""

import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


print("=" * 78)
print("1. PYTHON SYNTAX CHECK")
print("=" * 78)
import py_compile

for py_file in ["app.py", "model.py", "train_model.py"]:
    try:
        py_compile.compile(str(BASE / py_file), doraise=True)
        check(f"syntax ok: {py_file}", True)
    except py_compile.PyCompileError as exc:
        check(f"syntax ok: {py_file}", False, str(exc))

print()
print("=" * 78)
print("2. IMPORTS / APP FACTORY")
print("=" * 78)

import app as app_module
import model as ml

check("app imports", app_module.app is not None)
check("model file present", ml.model_exists())

# --- Wrap predict_news with a call counter (does not alter behaviour) ---
original_predict = ml.predict_news
call_counter = {"n": 0, "args": None}


def counting_predict(headline, article, bundle):
    call_counter["n"] += 1
    call_counter["args"] = (headline, article)
    return original_predict(headline, article, bundle)


ml.predict_news = counting_predict

app_module.app.config["TESTING"] = True
client = app_module.app.test_client()

print()
print("=" * 78)
print("3. ROUTES / PAGE RENDERING")
print("=" * 78)

# --- routes declared ---
rules = {str(r) for r in app_module.app.url_map.iter_rules()}
for expected in ["/", "/detect", "/predict", "/about", "/healthz",
                 "/upload", "/feed", "/assistant", "/assistant/ask"]:
    check(f"route exists: {expected}", expected in rules, f"got {sorted(rules)}")

pages = [
    ("/", 200, ["Discover the Truth", "Behind Every Headline",
                "AI-powered news intelligence", "Explore Platform"]),
    ("/detect", 200, ["Analyze a news article"]),
    ("/about", 200, ["Fake News Detection Using Data Science"]),
    ("/feed", 200, ["Demonstration feed", "Trending in this demonstration feed"]),
    ("/assistant", 200, ["News Intelligence Assistant", "rule-based"]),
    ("/definitely-not-a-page", 404, ["could not be found"]),
]

for path, expected_status, markers in pages:
    resp = client.get(path)
    body = resp.get_data(as_text=True)
    check(f"GET {path} -> {expected_status}", resp.status_code == expected_status,
          f"got {resp.status_code}")
    for marker in markers:
        check(f"GET {path} contains {marker!r}", marker in body,
              "marker missing from rendered HTML")

resp = client.get("/healthz")
payload = json.loads(resp.get_data(as_text=True))
check("GET /healthz -> 200", resp.status_code == 200, str(resp.status_code))
check("/healthz reports model_ready=true", payload.get("model_ready") is True, str(payload))

print()
print("=" * 78)
print("4. TEMPLATE / NAVIGATION INTEGRITY")
print("=" * 78)

home = client.get("/").get_data(as_text=True)
detect_page = client.get("/detect").get_data(as_text=True)
about_page = client.get("/about").get_data(as_text=True)

check("home uses shared base template (single doctype)",
      home.count("<!DOCTYPE html>") == 1, f"count={home.count('<!DOCTYPE html>')}")
check("detect page uses shared base template",
      detect_page.count("<!DOCTYPE html>") == 1)
check("about page uses shared base template",
      about_page.count("<!DOCTYPE html>") == 1)

# No external CDN dependencies any more
for name, body in [("home", home), ("detect", detect_page), ("about", about_page)]:
    check(f"{name}: no CDN <link>/<script> urls",
          "cdn.jsdelivr.net" not in body and "fonts.googleapis" not in body)

# Required navigation items present in the <nav> block of every page
nav_items = ["Home", "Detect News", "How It Works", "About Project", "Analyze News",
             "News Feed", "AI Assistant"]
for name, body in [("home", home), ("detect", detect_page), ("about", about_page)]:
    nav_match = re.search(r'<nav class="nav-menu".*?</nav>', body, re.S)
    nav_html = nav_match.group(0) if nav_match else ""
    check(f"{name}: <nav> block rendered", bool(nav_html), "nav-menu not found")
    for item in nav_items:
        check(f"{name}: nav has {item!r}", item in nav_html, "nav item missing")

# Active page indicator
check("home marks Home active", 'aria-current="page"' in home)
check("detect marks Detect active", home.count('aria-current="page"') >= 1 and
      'aria-current="page"' in detect_page)

# Form wiring
check("predict form action -> /predict", 'action="/predict"' in detect_page)
check("predict form method -> POST", 'method="POST"' in detect_page)
check("headline field name preserved", 'name="headline"' in detect_page)
check("article field name preserved", 'name="article"' in detect_page)
check("home preview also posts to /predict", 'action="/predict"' in home)

# Asset references resolve to real files
asset_paths = set(re.findall(r'/static/([a-zA-Z0-9_\-./]+)"', home + detect_page + about_page))
missing = [a for a in asset_paths if not (BASE / "static" / a).exists()]
check("all referenced static assets exist on disk", not missing, f"missing: {missing}")
check("css stylesheet referenced", "static/css/style.css" in home)
check("js script referenced", "static/js/script.js" in home)

# Internal links collected from all pages must resolve to real routes/anchors
all_html = home + detect_page + about_page
hrefs = set(re.findall(r'href="([^"]+)"', all_html))
internal = {h for h in hrefs
            if (h.startswith("/") or h.startswith("#")) and not h.startswith("/static/")}
route_paths = {str(r) for r in app_module.app.url_map.iter_rules() if str(r) != "/<path:_path>"}
broken = []
for href in sorted(internal):
    if href.startswith("#"):
        anchor = href[1:]
        if anchor and anchor not in all_html and anchor != "top":
            broken.append(href)
        continue
    path = href.split("#")[0]
    if path and path not in route_paths:
        broken.append(href)
check("no broken internal links/anchors", not broken, f"broken: {broken}")

# Anchor targets referenced on the home page actually exist in the markup
home_anchors = set(re.findall(r'href="#([^"]+)"', home))
missing_anchors = [a for a in home_anchors if f'id="{a}"' not in home]
check("home anchors resolve within the home page", not missing_anchors,
      f"missing ids: {missing_anchors}")

print()
print("=" * 78)
print("5. PREDICTION WORKFLOW (real ML)")
print("=" * 78)

call_counter["n"] = 0
resp = client.post("/predict", data={
    "headline": "Researchers publish results of a long term climate study",
    "article": "The findings appeared in a peer reviewed journal this week after four "
               "years of field work and independent replication by two other teams.",
}, follow_redirects=False)
body = resp.get_data(as_text=True)
check("POST /predict valid input -> 200", resp.status_code == 200, str(resp.status_code))
check("real ml.predict_news was called exactly once", call_counter["n"] == 1,
      f"count={call_counter['n']}")
check("result page rendered (verdict block)", "verdict-label" in body)
check("result page shows a label", ("Labelled likely real" in body) or
      ("Labelled potentially misleading" in body))
check("confidence rendered as a number", re.search(r'class="meter-value">[\d.]+%', body) is not None,
      "no numeric confidence found")
flat_body = " ".join(body.split())
check("result page carries the limitation disclaimer",
      "not a substitute for professional fact-checking" in flat_body,
      "disclaimer text missing")
check("session stats incremented", "mini-stat" in body)

# --- empty input (server-side validation must still work with JS disabled) ---
call_counter["n"] = 0
resp = client.post("/predict", data={"headline": "", "article": ""})
body = resp.get_data(as_text=True)
check("empty input rejected -> 200 page", resp.status_code == 200, str(resp.status_code))
check("empty input shows validation message",
      "Please enter a news headline or article before checking." in body)
check("empty input did NOT reach the model", call_counter["n"] == 0,
      f"count={call_counter['n']}")

# --- whitespace-only input ---
call_counter["n"] = 0
resp = client.post("/predict", data={"headline": "   ", "article": "  \n\t "})
body = resp.get_data(as_text=True)
check("whitespace-only input rejected", "Please enter a news headline" in body)
check("whitespace-only input did NOT reach the model", call_counter["n"] == 0)

# --- over-length input ---
call_counter["n"] = 0
resp = client.post("/predict", data={
    "headline": "x" * 500,
    "article": "y" * 10_000,
})
body = resp.get_data(as_text=True)
check("over-length input rejected", "Input is too long" in body)
check("over-length input did NOT reach the model", call_counter["n"] == 0)

# --- input echoing / XSS escaping ---
xss_headline = '<script>alert("xss")</script> Breaking headline'
resp = client.post("/predict", data={"headline": xss_headline, "article": ""})
body = resp.get_data(as_text=True)
check("raw <script> not echoed as HTML", "<script>alert" not in body,
      "user input rendered unescaped!")
check("script tag escaped on result page", "&lt;script&gt;" in body)
check("headline preserved in echoed text", "Breaking headline" in body)

# --- article preview truncation ---
resp = client.post("/predict", data={
    "headline": "Short headline",
    "article": "A" * 900,
})
body = resp.get_data(as_text=True)
check("long article truncated for display", "truncated for display" in body)

print()
print("=" * 78)
print("6. VALIDATION ROUTES BACK TO THE DETECTION PAGE")
print("=" * 78)
resp = client.post("/predict", data={"headline": "", "article": ""})
check("validation errors render the /detect form", 'action="/predict"' in
      resp.get_data(as_text=True) and "Please enter a news headline" in
      resp.get_data(as_text=True))

print()
print("=" * 78)
print("7. ESCAPING IN ALL USER-FACING TEMPLATES")
print("=" * 78)
for tpl in ["index.html", "detect.html", "result.html", "about.html", "404.html",
            "base.html", "feed.html", "assistant.html"]:
    src = (BASE / "templates" / tpl).read_text(encoding="utf-8")
    bad = re.findall(r"\{\{[^}]*\|\s*safe[^}]*\}\}", src)
    check(f"{tpl}: no |safe filter on user data", not bad, f"found {bad}")

print()
print("=" * 78)
print("8. DOCUMENT UPLOAD (real TXT / PDF / DOCX parsing)")
print("=" * 78)

import tempfile

import docx as docx_lib


def make_pdf(text: str) -> bytes:
    """Build a minimal, structurally valid single-page PDF for testing."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
         b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"),
        None,  # content stream, built below
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode("latin-1")
    objects[3] = (b"<< /Length " + str(len(stream)).encode() +
                  b" >>\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n"
    out += f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return bytes(out)


def post_upload(filename, content):
    """POST a file to /upload through the real multipart endpoint."""
    from io import BytesIO
    return client.post(
        "/upload",
        data={"document": (BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # --- happy path: TXT -------------------------------------------------
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text(
        "City council approves budget for riverside park project. "
        "The funding package covers walking paths and improved lighting.",
        encoding="utf-8",
    )
    call_counter["n"] = 0
    resp = client.post(
        "/upload",
        data={"document": (open(txt_path, "rb"), "sample.txt")},
        content_type="multipart/form-data",
    )
    body = resp.get_data(as_text=True)
    check("TXT upload -> 200", resp.status_code == 200, str(resp.status_code))
    check("TXT upload reached the real model exactly once", call_counter["n"] == 1,
          f"count={call_counter['n']}")
    check("TXT result page rendered", "verdict-label" in body)
    check("TXT source shown on result page", "Uploaded document: sample.txt" in body)
    check("TXT extracted text analyzed", "riverside park project" in body)

    # --- happy path: DOCX ------------------------------------------------
    doc = docx_lib.Document()
    doc.add_paragraph(
        "DOCX extraction check: committee approves open data portal pilot "
        "after public consultation."
    )
    docx_path = tmp_path / "sample.docx"
    doc.save(str(docx_path))
    call_counter["n"] = 0
    resp = client.post(
        "/upload",
        data={"document": (open(docx_path, "rb"), "sample.docx")},
        content_type="multipart/form-data",
    )
    body = resp.get_data(as_text=True)
    check("DOCX upload -> 200", resp.status_code == 200, str(resp.status_code))
    check("DOCX reached the real model", call_counter["n"] == 1,
          f"count={call_counter['n']}")
    check("DOCX text extracted", "open data portal pilot" in body)
    check("DOCX source shown", "Uploaded document: sample.docx" in body)

    # --- happy path: PDF -------------------------------------------------
    pdf_bytes = make_pdf(
        "PDF extraction check: laboratory publishes replication study results"
    )
    call_counter["n"] = 0
    resp = post_upload("sample.pdf", pdf_bytes)
    body = resp.get_data(as_text=True)
    check("PDF upload -> 200", resp.status_code == 200, str(resp.status_code))
    check("PDF reached the real model", call_counter["n"] == 1,
          f"count={call_counter['n']}")
    check("PDF text extracted", "replication study results" in body)

    # --- failure modes ---------------------------------------------------
    call_counter["n"] = 0
    resp = post_upload("malware.exe", b"MZ\x90\x00 not a document")
    body = resp.get_data(as_text=True)
    check("unsupported extension rejected", "Unsupported file type" in body)
    check("unsupported extension never reaches the model", call_counter["n"] == 0)

    call_counter["n"] = 0
    resp = post_upload("huge.txt", b"a" * (2 * 1024 * 1024 + 64))
    body = resp.get_data(as_text=True)
    check("oversized file rejected", "File is too large" in body)
    check("oversized file never reaches the model", call_counter["n"] == 0)

    call_counter["n"] = 0
    resp = post_upload("empty.txt", b"")
    body = resp.get_data(as_text=True)
    check("empty file rejected", "The selected file is empty" in body)
    check("empty file never reaches the model", call_counter["n"] == 0)

    call_counter["n"] = 0
    resp = post_upload("broken.pdf", b"%PDF-1.4\nthis is not really a pdf")
    body = resp.get_data(as_text=True)
    check("unreadable PDF rejected with friendly message",
          "could not be read" in body)
    check("unreadable PDF never reaches the model", call_counter["n"] == 0)

    call_counter["n"] = 0
    resp = client.post("/upload", data={}, content_type="multipart/form-data")
    body = resp.get_data(as_text=True)
    check("missing file rejected",
          "Please choose a file to upload before analyzing." in body)
    check("missing file never reaches the model", call_counter["n"] == 0)

    # --- long document truncates to the model limit ----------------------
    resp = post_upload("long.txt", ("The report describes a long committee "
                                    "session. " * 600).encode("utf-8"))
    body = resp.get_data(as_text=True)
    check("long document truncated at 10,000 characters",
          "first 10,000 characters analyzed" in body)

print()
print("=" * 78)
print("9. NEWS FEED (demonstration content)")
print("=" * 78)

feed_page = client.get("/feed").get_data(as_text=True)
check("feed shows the demonstration notice", "no news API is configured" in feed_page)
check("feed renders article cards", feed_page.count('class="news-card reveal"') >= 8,
      f"count={feed_page.count('class=\"news-card reveal\"')}")
check("feed labels cards as demo", feed_page.count(">Demo<") >= 8)
check("feed has a search bar", 'role="search"' in feed_page and 'name="q"' in feed_page)
check("feed has category filters", 'Filter by category' in feed_page)
check("feed marks trending entries", "Trending in this demonstration feed" in feed_page)

health_page = client.get("/feed?category=Health").get_data(as_text=True)
check("category filter keeps matching cards",
      "hospital shares seasonal vaccination" in health_page)
check("category filter hides other categories",
      "budget hearing" not in health_page and "open data portal" not in health_page)

search_page = client.get("/feed?q=portal").get_data(as_text=True)
check("search finds matching article", "open data portal" in search_page)
check("search hides non-matching article",
      "vaccination advice" not in search_page)

empty_page = client.get("/feed?category=NotACategory").get_data(as_text=True)
check("unknown category renders empty state",
      "No demonstration articles match" in empty_page)
empty_page = client.get("/feed?q=zzz-no-such-article").get_data(as_text=True)
check("no-match search renders empty state",
      "No demonstration articles match" in empty_page)

check("home has a Latest news section", 'id="latest-news"' in home)
check("home latest-news cards are labelled demo", home.count(">Demo<") >= 3)

print()
print("=" * 78)
print("10. AI NEWS ASSISTANT (rule-based, no external API)")
print("=" * 78)

assistant_page = client.get("/assistant").get_data(as_text=True)
check("assistant page declares rule-based mode",
      "external AI API is configured" in assistant_page)
check("assistant page states limitations",
      "never claims" in assistant_page or "proves anything true or false"
      in assistant_page)
check("assistant chat form wired", 'action="/assistant/ask"' in assistant_page)
check("assistant textarea present", 'id="assistantInput"' in assistant_page)

resp = client.post("/assistant/ask", json={"message": "How does the model work?"})
data = json.loads(resp.get_data(as_text=True))
check("assistant JSON question -> 200", resp.status_code == 200, str(resp.status_code))
check("assistant identifies pipeline intent", data.get("intent") == "how-it-works",
      str(data.get("intent")))
check("assistant explains the real TF-IDF step", "TF-IDF" in data.get("reply", ""))
check("assistant replies are marked rule-based", data.get("mode") == "rule-based")

resp = client.post("/assistant/ask", json={"message": "Are you ChatGPT?"})
data = json.loads(resp.get_data(as_text=True))
check("assistant honestly denies being generative AI",
      "not a generative AI" in data.get("reply", ""))

resp = client.post("/assistant/ask",
                   json={"message": "How do I check if a claim is credible?"})
data = json.loads(resp.get_data(as_text=True))
check("assistant gives credibility steps",
      "original source" in data.get("reply", ""))

resp = client.post("/assistant/ask", json={"message": "What are your limitations?"})
data = json.loads(resp.get_data(as_text=True))
limit_reply = data.get("reply", "")
check("assistant states it cannot prove anything",
      "prove anything true or false" in limit_reply)
check("limitation reply carries the standing disclaimer",
      "never treat" in limit_reply or "does not prove" in limit_reply)

# Pasted article + explicit request -> real model run + heuristic scan
sample_article = (
    "Researchers at the coastal institute published a five year study on "
    "estuary recovery this week. The paper reports measurable improvement in "
    "three of four monitored zones and has been peer reviewed by two "
    "independent teams. SHOCKING results you won't BELIEVE!!! Share this "
    "before it gets deleted, because they don't want you to know the truth."
)
call_counter["n"] = 0
resp = client.post("/assistant/ask",
                   json={"message": "Please check this text: " + sample_article})
data = json.loads(resp.get_data(as_text=True))
reply = data.get("reply", "")
check("assistant analysis used the real model", call_counter["n"] == 1,
      f"count={call_counter['n']}")
check("assistant analysis shows the predicted label",
      "labelled that text" in reply)
check("assistant analysis runs heuristic scans",
      "Clickbait phrasing" in reply or "Urgency / suppression claims" in reply)
check("assistant analysis repeats the limitation",
      "does not browse the internet" in reply)
check("assistant reply contains no HTML injection", "<script" not in reply)

# Explain-my-prediction uses the real session result (from section 5)
resp = client.post("/assistant/ask", json={"message": "Explain my last prediction"})
data = json.loads(resp.get_data(as_text=True))
explain_reply = data.get("reply", "")
check("assistant references the real session prediction",
      "Your most recent analysis in this session" in explain_reply)
check("assistant explains what confidence means",
      "not a probability that the story is true" in explain_reply or
      "not a measure of whether the story is true" in explain_reply)

# Empty and oversized messages
resp = client.post("/assistant/ask", json={"message": "   "})
check("empty assistant message -> 400", resp.status_code == 400, str(resp.status_code))
resp = client.post("/assistant/ask", json={"message": "x" * 6001})
check("oversized assistant message -> 400", resp.status_code == 400,
      str(resp.status_code))

# No-JavaScript fallback: a plain form POST renders the reply as HTML
resp = client.post("/assistant/ask", data={"message": "What are your limitations?"})
html = resp.get_data(as_text=True)
check("assistant works without JavaScript", resp.status_code == 200 and
      "prove anything true or false" in html, str(resp.status_code))

# ...and user input echoed into that HTML must be escaped
resp = client.post("/assistant/ask",
                   data={"message": "limitations <script>alert(1)</script>"})
html = resp.get_data(as_text=True)
check("no-JS assistant echoes user input escaped",
      "<script>alert" not in html and "&lt;script&gt;" in html)

print()
print("=" * 78)
print("11. WORKFLOW VISUALIZATION, UPLOAD WIRING & DESIGN ASSETS")
print("=" * 78)

check("home has the workflow section", 'id="workflow"' in home)
check("workflow has 7 stages", home.count('data-step="') == 7,
      f"count={home.count('data-step=\"')}")
check("workflow shows the real TF-IDF settings", "max_features=5000" in home)
check("workflow shows the real classifier settings", "max_iter=1000" in home)
check("workflow names the real cleaning function", "preprocess_text" in home)
check("workflow shows honest confidence handling",
      "never fabricated" in home or "no score is produced" in home)
check("workflow states it does not fake predictions",
      "does not submit text or fake a prediction" in home)

check("upload form posts to /upload", 'action="/upload"' in detect_page)
check("upload form is multipart",
      'enctype="multipart/form-data"' in detect_page)
check("file input accepts txt/pdf/docx", 'accept=".txt,.pdf,.docx' in detect_page)
check("file input named document", 'name="document"' in detect_page)
check("upload panel is on the detection page", 'id="upload"' in detect_page)

check("assistant page rendered with chat", 'id="assistantForm"' in assistant_page)

css_src = (BASE / "static" / "css" / "style.css").read_text(encoding="utf-8")
check("CSS: glassmorphism present", "backdrop-filter" in css_src)
check("CSS: animated background present", ".bg-orb" in css_src and ".bg-particles" in css_src)
check("CSS: workflow styles present", ".wf-node" in css_src)
check("CSS: upload styles present", ".dropzone" in css_src)
check("CSS: feed styles present", ".news-card" in css_src)
check("CSS: assistant styles present", ".chat-messages" in css_src)
check("CSS: reduced-motion support for new animations",
      css_src.count("prefers-reduced-motion") >= 2)

js_src = (BASE / "static" / "js" / "script.js").read_text(encoding="utf-8")
for fn in ["initParticles", "initCountUp", "initWorkflow",
           "initUpload", "initFeed", "initAssistant"]:
    check(f"JS: {fn} implemented", f"function {fn}" in js_src)
check("JS honours prefers-reduced-motion", "prefers-reduced-motion" in js_src)

print()
print("=" * 78)
print("12. VOICE INTELLIGENCE SYSTEM")
print("=" * 78)

# --- new backend routes ---------------------------------------------------
for expected in ["/assistant/history", "/assistant/clear"]:
    check(f"route exists: {expected}", expected in rules, f"got {sorted(rules)}")

# --- session conversation history (floating assistant widget) -------------
resp = client.post("/assistant/ask", json={"message": "How does the model work?"})
check("assistant ask (JSON) -> 200", resp.status_code == 200, str(resp.status_code))
reply_payload = resp.get_json()
check("assistant ask returns a reply", bool(reply_payload and reply_payload.get("reply")))

resp = client.get("/assistant/history")
history = resp.get_json() or {}
msgs = history.get("messages") or []
check("GET /assistant/history -> 200", resp.status_code == 200, str(resp.status_code))
check("history contains the user message",
      any(m.get("role") == "user" and "model work" in m.get("text", "") for m in msgs), str(msgs))
check("history contains the assistant reply",
      any(m.get("role") == "assistant" and m.get("text") for m in msgs), str(msgs))
check("history exposes a limit", history.get("limit") == 40, str(history.get("limit")))
check("history never returns raw session internals",
      "stats" not in history and "secret" not in str(history).lower(), str(history.keys()))

resp = client.post("/assistant/clear")
check("POST /assistant/clear -> 200", resp.status_code == 200, str(resp.status_code))
cleared = resp.get_json() or {}
check("clear empties the history", cleared.get("ok") is True and cleared.get("messages") == [], str(cleared))
check("history is empty after clearing",
      (client.get("/assistant/history").get_json() or {}).get("messages") == [])

# --- voice dock on /detect ------------------------------------------------
detect_voice = client.get("/detect").get_data(as_text=True)
for marker in ['id="voiceDock"', 'id="vdMic"', 'id="vdStart"', 'id="vdStop"',
               'id="vdClear"', 'id="vdWave"', 'id="vdStatus"', 'id="vdErrors"',
               'data-vd-target="headline"', 'data-vd-target="article"',
               'value="en-IN"', 'value="ta-IN"', 'value="hi-IN"']:
    check(f"detect voice dock: {marker}", marker in detect_voice, "marker missing")
check("detect dock explains the English-only model",
      "Model language: English" in detect_voice and "not" in detect_voice, "")
check("voice dock sits inside the real prediction form page",
      'action="/predict"' in detect_voice and 'id="voiceDock"' in detect_voice, "")
check("voice.js is loaded on /detect", "js/voice.js" in detect_voice, "")

# --- floating assistant widget -------------------------------------------
widget_marker = 'id="voiceAssistant"'
check("widget present on home page", widget_marker in home, "")
check("widget wired to real endpoints",
      'data-ask-url="/assistant/ask"' in home and 'data-history-url="/assistant/history"' in home
      and 'data-clear-url="/assistant/clear"' in home, "")
assistant_now = client.get("/assistant").get_data(as_text=True)
check("widget hidden on the full assistant page",
      widget_marker not in assistant_now, "widget should not duplicate the full chat")
check("widget has mic + clear + speak controls",
      all(m in home for m in ['id="vaMic"', 'id="vaClear"', 'id="vaSpeakToggle"',
                               'id="vaLang"', 'id="vaForm"']), "")

# --- text-to-speech result panel -----------------------------------------
resp = client.post("/predict", data={
    "headline": "Council approves riverside park budget",
    "article": "The council voted on Tuesday to approve funding for a riverside park.",
})
result_page = resp.get_data(as_text=True)
check("/predict renders the result page", resp.status_code == 200, str(resp.status_code))
for marker in ['id="ttsPanel"', 'id="ttsPlay"', 'id="ttsPause"', 'id="ttsResume"',
               'id="ttsStop"', 'id="ttsRate"', 'id="ttsVoice"', 'id="ttsWave"',
               'id="ttsStatus"', 'value="0.75"', 'value="1.5"']:
    check(f"tts panel: {marker}", marker in result_page, "marker missing")
check("tts panel offers the three voice languages",
      all(v in result_page for v in ['value="en-IN"', 'value="ta-IN"', 'value="hi-IN"']), "")

# --- honest language warning for non-English input -----------------------
resp = client.post("/predict", data={"headline": "", "article": "செய்தி தலைப்பு ஒரு சோதனை"})
tamil_page = resp.get_data(as_text=True)
check("Tamil input triggers the language limitation warning",
      "Language limitation" in tamil_page and "does not translate" in tamil_page, "")
resp = client.post("/predict", data={"headline": "", "article": "यह एक परीक्षण समाचार है।"})
hindi_page = resp.get_data(as_text=True)
check("Hindi input triggers the language limitation warning",
      "Language limitation" in hindi_page, "")
resp = client.post("/predict", data={"headline": "Normal English headline",
                                     "article": "An ordinary English article body."})
english_page = resp.get_data(as_text=True)
check("English input has no language warning",
      "Language limitation" not in english_page, "false positive warning")

# --- voice assets ---------------------------------------------------------
voice_js = (BASE / "static" / "js" / "voice.js").read_text(encoding="utf-8")
for fn in ["initVoiceDock", "initAssistantWidget", "initTtsPlayer", "initLanguage",
           "createRecognitionSession", "speakText", "stopSpeech", "createWave",
           "recognitionMessage", "voiceNote", "refreshVoices"]:
    check(f"voice.js: {fn} implemented", f"function {fn}" in voice_js, "")
check("voice.js uses SpeechRecognition with webkit fallback",
      "window.SpeechRecognition || window.webkitSpeechRecognition" in voice_js)
check("voice.js uses SpeechSynthesisUtterance", "SpeechSynthesisUtterance" in voice_js)
check("voice.js uses the three required locales",
      all(c in voice_js for c in ['"en-IN"', '"ta-IN"', '"hi-IN"']), "")
check("voice.js honours prefers-reduced-motion", "prefers-reduced-motion" in voice_js)
check("voice.js never injects raw HTML for transcripts",
      not re.search(r"\.innerHTML\s*=", voice_js), "innerHTML assignment found — use textContent")
check("voice.js contains no API keys or external services",
      not re.search(r"api[_-]?key|Bearer |rapidapi|openai", voice_js, re.I), "possible secret/external API")
check("voice.js stops previous speech before new playback",
      voice_js.count("speechSynthesis.cancel()") >= 2, str(voice_js.count("speechSynthesis.cancel()")))

for icon in ['id="i-mic"', 'id="i-play"', 'id="i-pause"', 'id="i-stop"',
             'id="i-volume"', 'id="i-refresh"']:
    check(f"icon sprite: {icon}", icon in home, "")

css_check = (BASE / "static" / "css" / "style.css").read_text(encoding="utf-8")
for cls in [".voice-dock", ".mic-btn", ".waveform", ".va-fab", ".va-panel",
            ".tts-panel", ".select", "@keyframes mic-pulse", "@keyframes wave-bar"]:
    check(f"CSS: {cls} present", cls in css_check, "")
check("CSS: reduced-motion covers the voice animations",
      css_check.count("prefers-reduced-motion") >= 3, str(css_check.count("prefers-reduced-motion")))

# --- voice on the full /assistant chat page --------------------------------
assistant_voice = client.get("/assistant").get_data(as_text=True)
for marker in ['id="chatMic"', 'id="chatLang"', 'id="chatSpeakToggle"',
               'id="chatVoiceNote"', 'id="chatVoiceStatus"', 'id="chatVoiceErrors"',
               'value="en-IN"', 'value="ta-IN"', 'value="hi-IN"']:
    check(f"assistant page voice control: {marker}", marker in assistant_voice, "marker missing")
check("assistant page loads voice.js", "js/voice.js" in assistant_voice, "")
check("voice.js: initAssistantPage implemented", "function initAssistantPage" in voice_js, "")
check("voice.js boots the assistant page module",
      "initAssistantPage();" in voice_js, "")
for cls in [".chat-head-actions", ".chat-actions-right", ".chat-voice-row", ".chat-mic"]:
    check(f"CSS: {cls} present", cls in css_check, "")

# --- nothing broke in the original flow ----------------------------------
resp = client.post("/predict", data={"headline": "Existing text detection still works",
                                     "article": "This body must still reach the real model."})
check("existing text prediction still works", resp.status_code == 200
      and "Prediction result" in resp.get_data(as_text=True), str(resp.status_code))
check("widget still hidden on assistant page after voice additions",
      'id="voiceAssistant"' not in client.get("/assistant").get_data(as_text=True), "")

print()
print("=" * 78)
print("13. NEWS COMPARISON LAB / ANALYTICS / 3D EXPERIENCE")
print("=" * 78)

# --- new routes declared ---------------------------------------------------
rules = {str(r) for r in app_module.app.url_map.iter_rules()}
for expected in ["/compare", "/analytics"]:
    check(f"route exists: {expected}", expected in rules, f"got {sorted(rules)}")

# --- GET /compare ----------------------------------------------------------
compare_page = client.get("/compare")
compare_html = compare_page.get_data(as_text=True)
check("GET /compare -> 200", compare_page.status_code == 200, str(compare_page.status_code))
for marker in ["Article inputs", 'id="headlineA"', 'id="articleA"',
               'id="headlineB"', 'id="articleB"', "Analyze both articles",
               "Clear all", 'data-scene="panels"']:
    check(f"/compare contains {marker!r}", marker in compare_html, "marker missing")
check("/compare warns output is not a fact-check",
      "not a verified fact-check" in compare_html, "")
check("/compare loads compare.js", "js/compare.js" in compare_html, "")

# --- POST /compare: two real model runs -----------------------------------
before_calls = call_counter["n"]
resp = client.post("/compare", data={
    "headline_a": "Council approves riverside park budget",
    "article_a": ("The city council voted on Tuesday to approve a funding package "
                  "for a new riverside park with walking paths and lighting."),
    "headline_b": "You won't BELIEVE this park secret",
    "article_b": ("Share this before it gets deleted because officials are hiding "
                  "the truth about the park from the public forever."),
})
compare_result = resp.get_data(as_text=True)
check("POST /compare -> 200 with results", resp.status_code == 200
      and "Side-by-side results" in compare_result, str(resp.status_code))
check("POST /compare runs the model exactly twice",
      call_counter["n"] - before_calls == 2,
      f"delta={call_counter['n'] - before_calls}")
check("compare shows Article A verdict", "Article A &mdash; model prediction" in compare_result)
check("compare shows Article B verdict", "Article B &mdash; model prediction" in compare_result)
check("compare shows a genuine similarity calculation",
      "Word-level similarity" in compare_result
      and re.search(r'id="simValue">\d+(\.\d+)?%', compare_result) is not None,
      "no computed overlap value found")
compare_norm = re.sub(r"\s+", " ", compare_result)
check("compare explains differing labels are not proof of inconsistency",
      "factually inconsistent" in compare_norm
      or "the model found similar statistical patterns" in compare_norm,
      "neither interpretation note found")
check("compare never claims independent verification",
      "does not verify claims against independent sources" in compare_result, "")
check("compare offers a download report control",
      'id="downloadReport"' in compare_result, "")

# --- identical texts must produce 100% overlap ----------------------------
resp = client.post("/compare", data={
    "headline_a": "Same headline for both sides",
    "article_a": "Identical wording appears in both panels for this overlap test.",
    "headline_b": "Same headline for both sides",
    "article_b": "Identical wording appears in both panels for this overlap test.",
})
identical = resp.get_data(as_text=True)
check("identical articles report 100% word overlap",
      re.search(r'id="simValue">100(\.0)?%', identical) is not None,
      "expected 100% jaccard for identical text")

# --- missing side is rejected server-side ---------------------------------
resp = client.post("/compare", data={
    "headline_a": "Only article A exists here",
    "article_a": "Some text for A.",
    "headline_b": "", "article_b": "",
})
missing = resp.get_data(as_text=True)
check("compare rejects an empty Article B",
      resp.status_code == 200
      and "Please enter a headline or article text for Article B." in missing,
      str(resp.status_code))

# --- XSS: user text is escaped on the compare page ------------------------
resp = client.post("/compare", data={
    "headline_a": '<script>alert("cmp")</script>',
    "article_a": "Plain body text for the escaping check.",
    "headline_b": "Safe headline B",
    "article_b": "Plain body text for the escaping check.",
})
xss = resp.get_data(as_text=True)
check("compare escapes submitted headlines",
      "<script>alert" not in xss and "&lt;script&gt;" in xss, "raw script tag leaked")

# --- genuine similarity helper (unit level) -------------------------------
sim = app_module.text_similarity("the quick brown fox", "the quick brown fox")
check("text_similarity: identical text -> 100%", sim["jaccard"] == 100.0, str(sim))
sim = app_module.text_similarity("apple banana cherry", "zebra quantum physics")
check("text_similarity: disjoint text -> 0%", sim["jaccard"] == 0.0, str(sim))
sim = app_module.text_similarity("", "   ")
check("text_similarity: empty text is flagged not comparable",
      sim["comparable"] is False and sim["jaccard"] is None, str(sim))
sim = app_module.text_similarity(
    "market shares rose sharply today after the vote",
    "shares rose today but market observers warned of risk")
check("text_similarity: shared terms are really shared",
      "shares" in sim["shared_terms"] and sim["shared_count"] >= 3, str(sim))
check("text_similarity: unique vocabularies listed per side",
      len(sim["unique_a_terms"]) > 0 and len(sim["unique_b_terms"]) > 0, str(sim))

# --- GET /analytics --------------------------------------------------------
fresh = app_module.app.test_client()   # brand-new session = brand-new visitor
fresh_html = fresh.get("/analytics").get_data(as_text=True)
analytics_html = client.get("/analytics").get_data(as_text=True)

for marker in ["Intelligence Analytics", "Articles analyzed", "Labelled REAL",
               "Labelled FAKE", "session only", "Model quality (recorded at training time)",
               'id="analyticsData"']:
    check(f"/analytics contains {marker!r}", marker in analytics_html, "marker missing")

check("fresh visitor sees zeroed empty states (no sample data)",
      "No analyses yet." in fresh_html and "No timestamps to plot yet." in fresh_html,
      "fresh session must not display invented statistics")
check("fresh visitor analytics shows 0 analyzed",
      'data-count="0"' in fresh_html, "")

# --- session privacy: one visitor's history never reaches another ---------
client.post("/predict", data={"headline": "PRIVATE_SESSION_MARKER headline",
                              "article": "PRIVATE_SESSION_MARKER body text."})
own = client.get("/analytics").get_data(as_text=True)
other = fresh.get("/analytics").get_data(as_text=True)
check("owner sees their own analysis in history",
      "PRIVATE_SESSION_MARKER" in own, "own history missing snippet")
check("other sessions never see someone else's history",
      "PRIVATE_SESSION_MARKER" not in other, "cross-session leak detected")
check("analytics totals reflect this session's real runs",
      int(re.search(r'data-count="(\d+)"', own).group(1)) > 0, "")
check("owner sees the weekly activity chart (timestamps exist)",
      'id="weekChart"' in own and "Weekly activity" in own, "")

# --- navigation ------------------------------------------------------------
nav_markers = ["News Comparison Lab", "Intelligence Analytics"]
home_html = home  # homepage fetched earlier
for label in ["Compare", "Analytics"]:
    check(f"navigation offers {label!r}", f">{label}</a>" in home_html, "")
for label in nav_markers:
    check(f"footer offers {label!r}", f">{label}</a>" in home_html, "")
check("nav marks Compare active on /compare",
      'class="nav-link is-active"' in compare_html and "aria-current=\"page\"" in compare_html, "")
check("nav marks Analytics active on /analytics",
      'class="nav-link is-active"' in fresh_html and "aria-current=\"page\"" in fresh_html, "")

# --- premium 3D experience assets -----------------------------------------
scene_js = (BASE / "static" / "js" / "scene3d.js").read_text(encoding="utf-8")
check("scene3d.js implements all four scenes",
      all(fn in scene_js for fn in
          ["buildNeural", "buildScanner", "buildPanels", "buildBars"]), "")
check("scene3d.js maps every declared scene type",
      all(t in scene_js for t in
          ["neural:", "scanner:", "panels:", "bars:"]), "")
check("scene3d.js lazy-loads three.js", "vendor/three.min.js" in scene_js, "")
check("scene3d.js honours prefers-reduced-motion", "prefers-reduced-motion" in scene_js, "")
check("scene3d.js probes WebGL before rendering", "webglAvailable" in scene_js, "")
check("scene3d.js pauses off-screen rendering", "IntersectionObserver" in scene_js
      and "document.hidden" in scene_js, "")
check("scene3d.js contains no innerHTML assignment",
      ".innerHTML" not in scene_js, "")
check("scene3d.js contains no external CDN or API key",
      re.search(r"api[_-]?key|Bearer |cdn\.|unpkg|jsdelivr", scene_js, re.I) is None, "")

for path, marker in [("/", 'data-scene="neural"'), ("/detect", 'data-scene="scanner"')]:
    page = client.get(path).get_data(as_text=True)
    check(f"{path} declares its 3D scene", marker in page, "")
check("base.html loads scene3d.js on every page", "js/scene3d.js" in home_html, "")

three_js = BASE / "static" / "js" / "vendor" / "three.min.js"
chart_js = BASE / "static" / "js" / "vendor" / "chart.umd.min.js"
check("three.js vendored locally (>400 KB)",
      three_js.exists() and three_js.stat().st_size > 400_000,
      str(three_js.stat().st_size if three_js.exists() else 0))
check("chart.js vendored locally (>100 KB)",
      chart_js.exists() and chart_js.stat().st_size > 100_000,
      str(chart_js.stat().st_size if chart_js.exists() else 0))

analytics_js = (BASE / "static" / "js" / "analytics.js").read_text(encoding="utf-8")
check("analytics.js animates counters", "data-count" in analytics_js, "")
check("analytics.js degrades to text if Chart.js fails",
      "could not be loaded" in analytics_js, "")
check("analytics.js reads server-rendered session data",
      "analyticsData" in analytics_js and "getElementById(\"analyticsData\")" in analytics_js, "")
check("analytics.js contains no hardcoded statistics",
      re.search(r"\b(distribution|weekly)\s*[:=]\s*\{[^}]*\d", analytics_js) is None,
      "possible fabricated chart data")
check("analytics page loads vendored chart.js", "vendor/chart.umd.min.js"
      in client.get("/analytics").get_data(as_text=True), "")

# --- premium detection page additions -------------------------------------
check("detect page offers the paste-article button",
      'id="pasteArticleBtn"' in detect_page and 'id="pasteNote"' in detect_page, "")
check("script.js implements initPasteButton", "function initPasteButton"
      in (BASE / "static" / "js" / "script.js").read_text(encoding="utf-8"), "")

# --- CSS for the new experience -------------------------------------------
for cls in [".cmp-input-grid", ".cmp-verdict-grid", ".cmp-agree", ".cmp-sim-value",
            ".dash-grid", ".dash-card", ".scene", "[data-tilt]", ".history-item",
            ".mic-btn::after", "@keyframes sim-grow", "@keyframes sf-spin"]:
    check(f"CSS: {cls} present", cls in css_check, "")
check("CSS: reduced-motion covers the 3D + tilt layer",
      css_check.count("prefers-reduced-motion") >= 4,
      str(css_check.count("prefers-reduced-motion")))
check("CSS: hero scenes hidden on phones",
      ".page-hero .scene { display: none; }" in css_check.replace("  ", " "), "")

# --- new JS contains no secrets / no raw HTML injection -------------------
for js_name in ["compare.js", "analytics.js"]:
    src = (BASE / "static" / "js" / js_name).read_text(encoding="utf-8")
    check(f"{js_name} contains no API keys or external services",
          re.search(r"api[_-]?key|Bearer |rapidapi|openai", src, re.I) is None, "")
    check(f"{js_name} never assigns innerHTML", ".innerHTML" not in src, "")

# --- final regression sweep ------------------------------------------------
resp = client.post("/predict", data={"headline": "Final regression check",
                                     "article": "The original single-article flow must still work."})
check("single-article prediction still works after all additions",
      resp.status_code == 200 and "Prediction result" in resp.get_data(as_text=True),
      str(resp.status_code))

print()
print("=" * 78)
print("SUMMARY")
print("=" * 78)
print(f"  passed: {len(PASS)}")
print(f"  failed: {len(FAIL)}")
if FAIL:
    for f in FAIL:
        print(f"    - {f}")
    sys.exit(1)
print("  ALL CHECKS PASSED")
