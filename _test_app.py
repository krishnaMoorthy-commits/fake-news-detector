"""
End-to-end test suite for the redesigned Fake News Detection app.

Run with:  python _test_app.py

Everything below exercises the REAL Flask application object and the REAL
machine-learning model — no mocking of prediction logic (the only patch is a
counter wrapper around model.predict_news so we can prove it was invoked).
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
for expected in ["/", "/detect", "/predict", "/about", "/healthz"]:
    check(f"route exists: {expected}", expected in rules, f"got {sorted(rules)}")

pages = [
    ("/", 200, ["Think", "Before You Believe"]),
    ("/detect", 200, ["Analyze a news article"]),
    ("/about", 200, ["Fake News Detection Using Data Science"]),
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
nav_items = ["Home", "Detect News", "How It Works", "About Project", "Analyze News"]
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
for tpl in ["index.html", "detect.html", "result.html", "about.html", "404.html", "base.html"]:
    src = (BASE / "templates" / tpl).read_text(encoding="utf-8")
    bad = re.findall(r"\{\{[^}]*\|\s*safe[^}]*\}\}", src)
    check(f"{tpl}: no |safe filter on user data", not bad, f"found {bad}")

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
