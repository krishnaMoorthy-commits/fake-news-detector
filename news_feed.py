"""
news_feed.py

Demonstration news-feed content for the Fake News Detection platform.

IMPORTANT HONESTY NOTE
----------------------
No news API is configured for this project, so this module does NOT provide
live news. Every entry below is static demonstration content written purely to
exercise the feed interface (cards, category filters, search, read-more).

Templates must keep the demonstration labelling visible (banner + "Demo"
badge) so a visitor can never mistake these entries for live reporting.
"""

from __future__ import annotations

# Banner text rendered above the feed (kept here so wording lives in one place).
FEED_NOTICE = (
    "Demonstration feed — no news API is configured for this project. "
    "The entries below are sample content written to show the interface, "
    "not live or breaking news."
)

# Categories shown as filter chips (order matters: it is the display order).
CATEGORIES = ["Technology", "Health", "Politics", "Science", "Business"]

# Each article:
#   id       - stable identifier used as a DOM key
#   category - must be one of CATEGORIES
#   title    - sample headline
#   summary  - short teaser shown on the card
#   body     - fuller sample text revealed by "Read more"
#   source   - always "Demonstration content" (there is no real publisher)
#   date     - "Sample entry" (there is no real publication date)
#   trending - flagged items are also listed in the Trending block
DEMO_ARTICLES: list[dict] = [
    {
        "id": "demo-1",
        "category": "Technology",
        "trending": True,
        "title": "Sample story: council publishes an open data portal",
        "summary": (
            "Demonstration article describing how a local authority might "
            "publish spending records online, used here to show a "
            "technology-category card in the feed."
        ),
        "body": (
            "This is demonstration content, not a news report. It exists so "
            "the news-feed interface can display a realistic technology story: "
            "a short summary, a category badge, a source line and an "
            "expandable body. Replace news_feed.py with a real, properly "
            "sourced feed (for example a configured news API) if you want "
            "genuine articles to appear here."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-2",
        "category": "Health",
        "trending": True,
        "title": "Sample story: hospital shares seasonal vaccination advice",
        "summary": (
            "Fictional placeholder used to demonstrate a health-category card, "
            "including how a summary and publication metadata are rendered."
        ),
        "body": (
            "Demonstration content only — this text was written for the "
            "project interface and is not medical guidance. It illustrates "
            "how a health-related card would look: category badge, summary, "
            "source and date labels, plus a read-more expansion."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-3",
        "category": "Politics",
        "trending": False,
        "title": "Sample story: committee schedules a public budget hearing",
        "summary": (
            "Placeholder politics entry showing how the category filter and "
            "search bar interact with a card in this demonstration feed."
        ),
        "body": (
            "This is sample content created for interface demonstration. It "
            "is not reporting on any real committee, hearing or date. Use the "
            "category chips and the search field to see how filtering behaves "
            "across the demo entries."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-4",
        "category": "Science",
        "trending": True,
        "title": "Sample story: university lab opens a citizen science programme",
        "summary": (
            "Fictional science-category sample used to show card layout, "
            "metadata lines and the read-more behaviour."
        ),
        "body": (
            "Demonstration content. This placeholder exists to populate the "
            "science category in the feed; it does not describe a real "
            "university, laboratory or programme. All feed entries are "
            "labelled so visitors can tell them apart from genuine reporting."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-5",
        "category": "Business",
        "trending": False,
        "title": "Sample story: small retailers report a steady quarter",
        "summary": (
            "Business-category placeholder demonstrating metadata, filtering "
            "and expandable body text in the demo feed."
        ),
        "body": (
            "This is not a market report — it is sample text written to show "
            "a business-category card. No figures, companies or events "
            "mentioned here are real. Feeds with genuine data should be wired "
            "to a properly configured and tested news API."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-6",
        "category": "Technology",
        "trending": False,
        "title": "Sample story: how a spam filter differs from a fact checker",
        "summary": (
            "Educational placeholder explaining, in sample form, why a text "
            "classifier is not a verification service."
        ),
        "body": (
            "Demonstration content with an educational angle: a classifier "
            "like the one in this project looks at statistical patterns in "
            "words, while a fact checker verifies claims against independent "
            "sources. The two are not interchangeable — and this card is "
            "still just sample feed data."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-7",
        "category": "Health",
        "trending": False,
        "title": "Sample story: reading a health headline critically",
        "summary": (
            "Placeholder card modelled on the kind of headline the platform "
            "encourages readers to slow down and examine."
        ),
        "body": (
            "Sample content for interface demonstration. It is not health "
            "advice and does not report any study. Cards like this one exist "
            "so the search bar, category filters and expandable summaries can "
            "be tested against realistic lengths of text."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-8",
        "category": "Politics",
        "trending": False,
        "title": "Sample story: what a source line should tell you",
        "summary": (
            "Fictional entry that models good metadata practice: a visible "
            "source and date on every card."
        ),
        "body": (
            "Demonstration content. In a real feed, the source line should "
            "name the publisher and the date should be the actual publication "
            "date. Because no news API is configured here, both fields are "
            "explicitly labelled as sample values."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-9",
        "category": "Science",
        "trending": False,
        "title": "Sample story: replication, peer review and why both matter",
        "summary": (
            "Educational placeholder describing verification steps a reader "
            "can take before trusting a claim."
        ),
        "body": (
            "Sample content written for this project's feed interface. It "
            "summarises, in fictional form, the kind of verification advice "
            "the AI News Assistant also gives — check the publisher, look for "
            "independent coverage, and confirm claims at the original source."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
    {
        "id": "demo-10",
        "category": "Business",
        "trending": False,
        "title": "Sample story: why 'too good to be true' pricing deserves a pause",
        "summary": (
            "Business-category sample used to round out the feed and give the "
            "search field a third category to match against."
        ),
        "body": (
            "Demonstration content only. No company, product or price is "
            "described here; the card exists to populate the business "
            "category for filtering and search tests."
        ),
        "source": "Demonstration content",
        "date": "Sample entry",
    },
]


def categories() -> list[str]:
    """Return the ordered category list used to build filter chips."""
    return list(CATEGORIES)


def all_articles() -> list[dict]:
    """Return every demonstration article (newest list order first)."""
    return list(DEMO_ARTICLES)


def trending_articles() -> list[dict]:
    """Return the articles flagged as trending within the demo feed."""
    return [a for a in DEMO_ARTICLES if a.get("trending")]


def filter_articles(category: str = "", query: str = "") -> list[dict]:
    """
    Filter the demo feed.

    Args:
        category: exact category name, or "" for all categories.
        query: free-text case-insensitive match against title and summary.

    Returns:
        The matching articles, preserving list order. Unknown categories
        simply match nothing (the caller renders an empty state).
    """
    items = all_articles()

    if category:
        items = [a for a in items if a["category"].lower() == category.lower()]

    if query:
        needle = query.lower()
        items = [
            a
            for a in items
            if needle in a["title"].lower() or needle in a["summary"].lower()
        ]

    return items
