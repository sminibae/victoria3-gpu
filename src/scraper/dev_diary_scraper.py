"""
Victoria 3 Developer Diary Scraper
Crawls forum.paradoxplaza.com/forum/forums/victoria-3.1095/ with the
dev-diary thread filter, downloads each diary's first post, and saves
structured markdown files.

Output:
  data/dev_diaries/<slug>.md       — individual diary files
  data/dev_diaries/_index.json     — title / date / topics / url per diary
  data/dev_diaries/_by_topic.json  — slugs grouped by topic tag

Usage:
  python dev_diary_scraper.py              # crawl all; skip already saved
  python dev_diary_scraper.py --recheck   # re-download everything
"""

import re
import sys
import time
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FORUM_BASE = "https://forum.paradoxplaza.com"
VIC3_DIARY_LISTING = (
    f"{FORUM_BASE}/forum/forums/victoria-3.1095/?thread_type=prdx_dev_diary"
)
OUTPUT_DIR = Path(__file__).parents[2] / "data" / "dev_diaries"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "victoria3-gpu-research/1.0 (academic; github.com/user/victoria3-gpu)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_DELAY = 1.5  # seconds between requests

# Topic keywords for automatic tagging
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "economy": [
        "econom", "market", "trade", "price", "good", "goods", "supply",
        "demand", "profit", "revenue", "gdp", "production", "throughput",
        "input", "output", "tariff", "subsidy", "currency",
    ],
    "population": [
        "pop", "population", "strata", "wealth", "needs", "consumption",
        "standard of living", "literacy", "migration", "emigration",
        "workforce", "employment", "unemployment", "aristocrat", "capitalist",
        "laborer", "peasant", "clerk",
    ],
    "buildings": [
        "building", "factory", "farm", "mine", "construction", "infrastructure",
        "railway", "port", "production method", "throughput",
    ],
    "simulation": [
        "simulation", "tick", "performance", "cpu", "thread", "engine",
        "jomini", "clausewitz", "iteration", "convergence", "algorithm",
        "calculation", "formula", "mechanic",
    ],
    "politics": [
        "law", "government", "political", "party", "movement", "ideology",
        "reform", "revolution", "election", "interest group",
    ],
    "military": [
        "military", "army", "war", "battle", "combat", "navy", "front",
        "mobilization", "conscription", "general",
    ],
    "diplomacy": [
        "diplomacy", "diplomatic", "treaty", "alliance", "rival", "tension",
        "prestige", "influence", "sphere", "subject",
    ],
    "technology": [
        "technology", "research", "invention", "innovation", "journal",
        "tech tree", "diffusion",
    ],
    "balance": [
        "balance", "tweak", "patch", "hotfix", "update", "changelog",
        "buff", "nerf", "feedback", "1.1", "1.2", "1.3", "1.4", "1.5",
        "1.6", "1.7", "1.8",
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(title: str) -> str:
    s = title.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s[:100]


def tag_topics(text: str) -> list[str]:
    text_lower = text.lower()
    return sorted(
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(kw in text_lower for kw in keywords)
    )


def fetch(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        if resp.status_code == 200:
            return resp.text
        print(f"  HTTP {resp.status_code}  {url}")
        return None
    except Exception as exc:
        print(f"  ERR  {url} — {exc}")
        return None


# ---------------------------------------------------------------------------
# Discovery: walk the Victoria 3 forum listing filtered to dev diaries
# ---------------------------------------------------------------------------

def discover_diary_entries() -> list[dict]:
    """
    Walk the Victoria 3 forum listing pages (thread_type=prdx_dev_diary)
    and collect all dev diary thread entries.

    Returns list of dicts: {num, title, url, date_str}
    """
    entries: dict[int, dict] = {}  # keyed by diary number to deduplicate

    page = 1
    while True:
        url = f"{VIC3_DIARY_LISTING}&page={page}"
        print(f"  Listing page {page}: {url}")
        html = fetch(url)
        if not html:
            break

        soup = BeautifulSoup(html, "lxml")
        new_this_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Only thread permalinks (not pagination sub-links like /page-3)
            if not re.search(r"victoria-3-dev-diary-\d+[^/]*\.\d+/", href.rstrip("/") + "/"):
                continue

            m = re.search(r"dev-diary-(\d+)", href)
            if not m:
                continue
            num = int(m.group(1))

            if num in entries:
                continue

            # Full URL
            full_url = FORUM_BASE + href if href.startswith("/") else href

            # Title: from the link text or nearby heading
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                parent = a.find_parent(["li", "div", "article"])
                if parent:
                    h = parent.find(["h3", "h2", "h4"])
                    if h:
                        title = h.get_text(strip=True)
            if not title:
                title = f"Dev Diary #{num}"

            # Date: from a nearby <time> tag
            date_str = ""
            parent = a.find_parent(["li", "div", "article"])
            if parent:
                t = parent.find("time")
                if t:
                    date_str = t.get("datetime", t.get_text(strip=True))

            entries[num] = {
                "num": num,
                "title": title,
                "url": full_url,
                "date_str": date_str,
            }
            new_this_page += 1

        nums_this_page = sorted(
            k for k in entries if k not in {e["num"] for e in list(entries.values())[:-new_this_page]}
        ) if new_this_page else []
        print(f"    +{new_this_page} new entries this page")

        if new_this_page == 0:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    result = sorted(entries.values(), key=lambda e: e["num"])
    print(f"Discovered {len(result)} dev diary threads")
    return result


# ---------------------------------------------------------------------------
# Parse one dev diary forum thread
# ---------------------------------------------------------------------------

def parse_diary_page(html: str, url: str, num: int, title_hint: str) -> dict:
    """
    Extract structured content from a forum dev diary page.
    The OP content lives in div.block.prdx_diary_firstPost > .bbWrapper
    (or .message-userContent if prdx_diary_firstPost is absent).
    """
    soup = BeautifulSoup(html, "lxml")

    # --- Title ---
    title = title_hint
    h1 = soup.find("h1")
    if h1:
        t = h1.get_text(strip=True)
        if len(t) > 5:
            title = t

    # --- Date ---
    date_str = ""
    # XenForo stores publication date in .u-dt or nearby <time> in thread header
    for sel in [".threadmarkItem time", ".p-body-header time", "time.u-dt"]:
        el = soup.select_one(sel)
        if el:
            date_str = el.get("datetime", el.get_text(strip=True))
            break
    if not date_str:
        for meta in soup.find_all("meta"):
            prop = meta.get("property", "") or meta.get("name", "")
            if "published" in prop or "date" in prop.lower():
                date_str = meta.get("content", "")
                break

    # --- Author (thread starter) ---
    author = ""
    for sel in [".p-body-header .username", ".prdx_diary_firstPost .username",
                ".p-description .username", ".message-name .username"]:
        el = soup.select_one(sel)
        if el:
            author = el.get_text(strip=True)
            break

    # --- Body: first-post content block ---
    body_el = (
        soup.select_one("div.block.prdx_diary_firstPost .bbWrapper")
        or soup.select_one("div.prdx_diary_firstPost .message-userContent")
        or soup.select_one("div.prdx_diary_firstPost .bbWrapper")
    )
    # Fallback: first article.message-body's bbWrapper
    if body_el is None:
        for art in soup.select("article.message-body"):
            bw = art.select_one(".bbWrapper")
            if bw and len(bw.get_text(strip=True)) > 500:
                body_el = bw
                break

    body_md = bbwrapper_to_markdown(body_el) if body_el else "(content not found)"
    topics = tag_topics(f"#{num} {title} {body_md}")

    return {
        "num": num,
        "title": title,
        "date": date_str,
        "author": author,
        "url": url,
        "topics": topics,
        "body_md": body_md,
    }


# ---------------------------------------------------------------------------
# Convert XenForo bbWrapper HTML to markdown
# ---------------------------------------------------------------------------

def bbwrapper_to_markdown(el: BeautifulSoup) -> str:
    """Convert XenForo .bbWrapper element to clean markdown."""
    # Remove noise elements before processing
    for tag in el.find_all(["script", "style", "noscript"]):
        tag.decompose()
    for tag in el.find_all(class_=re.compile(r"(bbCodeSpoiler|attachedImages)", re.I)):
        tag.decompose()

    lines: list[str] = []

    def node(n) -> str:
        if isinstance(n, str):
            return n  # preserve whitespace for inline context

        tag = getattr(n, "name", None)
        if tag is None:
            return ""

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            return "\n" + "#" * level + " " + n.get_text(strip=True) + "\n"

        if tag == "p":
            inner = "".join(node(c) for c in n.children).strip()
            return inner + "\n" if inner else ""

        if tag in ("ul", "ol"):
            items = []
            for li in n.find_all("li", recursive=False):
                items.append("- " + li.get_text(separator=" ", strip=True))
            return "\n".join(items) + "\n" if items else ""

        if tag == "blockquote":
            # XenForo quote blocks — extract the quoted text
            inner = n.select_one(".bbCodeBlock-content, .bbCodeBlock-expandContent")
            text = (inner or n).get_text(separator=" ", strip=True)
            return "> " + text[:400] + "\n" if text else ""

        if tag == "table":
            return _table(n)

        if tag in ("pre", "code"):
            return "```\n" + n.get_text() + "\n```\n"

        if tag == "hr":
            return "\n---\n"

        if tag == "br":
            return "\n"

        if tag == "img":
            alt = n.get("alt", "image")
            src = n.get("src", n.get("data-src", ""))
            return f"![{alt}]({src})\n" if src else ""

        if tag == "a":
            href = n.get("href", "")
            text = n.get_text(strip=True)
            if href and text:
                return f"[{text}]({href})"
            return text

        if tag in ("b", "strong"):
            inner = "".join(node(c) for c in n.children).strip()
            return f"**{inner}**" if inner else ""

        if tag in ("i", "em"):
            inner = "".join(node(c) for c in n.children).strip()
            return f"*{inner}*" if inner else ""

        # Generic container — recurse
        return "".join(node(c) for c in n.children)

    def _table(tbl) -> str:
        rows = []
        for tr in tbl.find_all("tr"):
            cells = [c.get_text(separator=" ", strip=True) for c in tr.find_all(["th", "td"])]
            rows.append("| " + " | ".join(cells) + " |")
        if not rows:
            return ""
        col_count = rows[0].count("|") - 1
        rows.insert(1, "| " + " | ".join(["---"] * col_count) + " |")
        return "\n".join(rows) + "\n"

    # Process top-level children of bbWrapper
    for child in el.children:
        md = node(child)
        if md and md.strip():
            lines.append(md)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Save one diary
# ---------------------------------------------------------------------------

def save_diary(entry: dict, recheck: bool = False) -> str | None:
    """Download and save one dev diary. Returns slug on success."""
    num = entry["num"]
    url = entry["url"]

    # Build slug from diary number + title
    title_slug = slugify(entry.get("title", f"dev-diary-{num}"))
    slug = f"dd-{num:03d}-{title_slug}"
    out_path = OUTPUT_DIR / f"{slug}.md"

    if out_path.exists() and not recheck:
        print(f"  SKIP DD#{num:3d} (already saved)")
        return slug

    html = fetch(url)
    if not html:
        return None

    data = parse_diary_page(html, url, num, entry.get("title", ""))

    lines = [
        f"# {data['title']}",
        "",
        f"**Diary**: #{num}",
        f"**URL**: {url}",
    ]
    if data["date"]:
        lines.append(f"**Date**: {data['date']}")
    if data["author"]:
        lines.append(f"**Author**: {data['author']}")
    if data["topics"]:
        lines.append(f"**Topics**: {', '.join(data['topics'])}")
    lines += ["", "---", "", data["body_md"]]

    out_path.write_text("\n".join(lines), encoding="utf-8")

    body_len = len(data["body_md"])
    topic_str = ", ".join(data["topics"]) if data["topics"] else "untagged"
    print(f"  SAVE DD#{num:3d}  {body_len:5d} chars  [{topic_str}]")
    return slug


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

def build_index(entries: list[dict], slug_map: dict[str, str]) -> None:
    """Write _index.json and _by_topic.json."""
    index = []
    by_topic: dict[str, list[str]] = {}

    for entry in entries:
        slug = slug_map.get(entry["url"])
        if not slug:
            continue

        fpath = OUTPUT_DIR / f"{slug}.md"
        topics: list[str] = []
        if fpath.exists():
            for line in fpath.read_text(encoding="utf-8").splitlines()[:12]:
                if line.startswith("**Topics**:"):
                    raw = line.split(":", 1)[1].strip()
                    topics = [t.strip() for t in raw.split(",") if t.strip()]

        record = {
            "num": entry["num"],
            "slug": slug,
            "title": entry.get("title", ""),
            "url": entry["url"],
            "date": entry.get("date_str", ""),
            "topics": topics,
        }
        index.append(record)
        for topic in topics:
            by_topic.setdefault(topic, []).append(slug)

    index.sort(key=lambda r: r["num"])

    (OUTPUT_DIR / "_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "_by_topic.json").write_text(
        json.dumps(by_topic, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nIndex: {len(index)} diaries, {len(by_topic)} topic tags")
    for topic, slugs in sorted(by_topic.items(), key=lambda x: -len(x[1])):
        print(f"  {topic:15s}  {len(slugs):3d} diaries")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Victoria 3 dev diary scraper")
    parser.add_argument(
        "--recheck", action="store_true",
        help="Re-download even if the markdown file already exists"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print raw HTML and all hrefs from the first listing page to diagnose selector issues"
    )
    args = parser.parse_args()

    if args.debug:
        url = f"{VIC3_DIARY_LISTING}&page=1"
        print(f"Fetching: {url}")
        html = fetch(url)
        if not html:
            print("Fetch failed.")
            return
        soup = BeautifulSoup(html, "lxml")
        title = soup.find("title")
        print(f"Page title: {title.get_text() if title else '(none)'}")
        print(f"HTML length: {len(html)}")
        hrefs = [a["href"] for a in soup.find_all("a", href=True)]
        print(f"Total <a href> tags: {len(hrefs)}")
        diary_like = [h for h in hrefs if "diary" in h.lower() or "thread" in h.lower()]
        print(f"  href containing 'diary' or 'thread': {len(diary_like)}")
        for h in diary_like[:30]:
            print(f"    {h}")
        if not diary_like:
            print("  (none — possible Cloudflare/JS-rendered page)")
            print("\nFirst 2000 chars of HTML:")
            print(html[:2000])
        return

    print(f"=== Victoria 3 Dev Diary Scraper ===")
    print(f"Output directory: {OUTPUT_DIR}\n")

    # 1. Discover all diary thread URLs
    print("=== Discovering diary URLs ===")
    entries = discover_diary_entries()

    if not entries:
        print("No entries found. Check the listing URL and selectors.")
        return

    nums = [e["num"] for e in entries]
    print(f"Range: DD#{min(nums)} – DD#{max(nums)}")
    expected = set(range(min(nums), max(nums) + 1))
    missing = sorted(expected - set(nums))
    if missing:
        print(f"Missing diary numbers: {missing}")

    # 2. Download each diary
    print(f"\n=== Downloading {len(entries)} diaries ===")
    slug_map: dict[str, str] = {}  # url -> slug

    for i, entry in enumerate(entries, 1):
        print(f"[{i:3d}/{len(entries)}] DD#{entry['num']:3d}  {entry['title'][:60]}")
        slug = save_diary(entry, recheck=args.recheck)
        if slug:
            slug_map[entry["url"]] = slug
        time.sleep(REQUEST_DELAY)

    # 3. Build searchable index
    print("\n=== Building index ===")
    build_index(entries, slug_map)

    saved = len(slug_map)
    print(f"\nDone: {saved}/{len(entries)} saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
