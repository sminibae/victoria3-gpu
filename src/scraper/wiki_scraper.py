"""
Victoria 3 Wiki Scraper
Scrapes vic3.paradoxwikis.com and saves pages as structured markdown.
Output: data/wiki/<slug>.md
"""

import re
import sys
import time
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "https://vic3.paradoxwikis.com"
OUTPUT_DIR = Path(__file__).parents[2] / "data" / "wiki"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "victoria3-gpu-research/1.0 (academic; github.com/user/victoria3-gpu)"
}

# Priority pages for the economic model
PRIORITY_PAGES = [
    "Market",
    "Goods",
    "Needs",
    "Buildings",
    "Infrastructure",
    "Trade",
    "Population",
    "Laws",
    "Technology",
    "Production_methods",
    "Standard_of_living",
    "Government",
    "Army",
    "War",
    "Military_units",
    "Combat",
    "Diplomacy",
]


def slugify(title: str) -> str:
    return re.sub(r"[^\w\-]", "_", title).strip("_")


def fetch_page(title: str) -> str | None:
    """Fetch a wiki page by title, return HTML or None on failure."""
    url = f"{BASE_URL}/{title}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            print(f"  OK  {url}")
            return resp.text
        else:
            print(f"  {resp.status_code}  {url}")
            return None
    except Exception as e:
        print(f"  ERR {url} — {e}")
        return None


def html_to_markdown(soup: BeautifulSoup, title: str) -> str:
    """Convert wiki page HTML to clean markdown."""
    lines = [f"# {title}", "", f"Source: {BASE_URL}/{title}", ""]

    content = soup.find("div", {"id": "mw-content-text"})
    if not content:
        return "\n".join(lines)

    # Remove edit/nav clutter
    for tag in content.find_all(["sup", "table"], class_=["reference", "navbox"]):
        tag.decompose()
    for tag in content.find_all(class_=["mw-editsection"]):
        tag.decompose()

    def process_node(node):
        if isinstance(node, str):
            return node.strip()

        tag = node.name

        if tag in ("h2", "h3", "h4", "h5"):
            level = int(tag[1])
            text = node.get_text(strip=True).replace("[edit]", "").strip()
            return "\n" + "#" * level + " " + text + "\n"

        if tag == "p":
            text = node.get_text(separator=" ", strip=True)
            return text + "\n" if text else ""

        if tag in ("ul", "ol"):
            items = []
            for li in node.find_all("li", recursive=False):
                items.append("- " + li.get_text(separator=" ", strip=True))
            return "\n".join(items) + "\n" if items else ""

        if tag == "table":
            return process_table(node)

        if tag == "pre" or (tag == "code" and node.parent.name != "p"):
            return "```\n" + node.get_text() + "\n```\n"

        if tag in ("div", "section", "span"):
            parts = []
            for child in node.children:
                if hasattr(child, "name"):
                    parts.append(process_node(child))
                elif str(child).strip():
                    parts.append(str(child).strip())
            return "\n".join(p for p in parts if p)

        return node.get_text(separator=" ", strip=True)

    def process_table(table) -> str:
        rows = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            row = " | ".join(c.get_text(separator=" ", strip=True) for c in cells)
            rows.append("| " + row + " |")
        if not rows:
            return ""
        # Insert header separator after first row
        if len(rows) >= 1:
            col_count = rows[0].count("|") - 1
            separator = "| " + " | ".join(["---"] * col_count) + " |"
            rows.insert(1, separator)
        return "\n".join(rows) + "\n"

    for child in content.children:
        if hasattr(child, "name"):
            result = process_node(child)
            if result and result.strip():
                lines.append(result.strip())

    return "\n\n".join(lines)


def get_all_wiki_titles() -> list[str]:
    """Fetch all page titles from the wiki's Special:AllPages."""
    titles = set()
    url = f"{BASE_URL}/Special:AllPages"
    print(f"Fetching page index from {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")
        for link in soup.select(".mw-allpages-body a"):
            title = link.get("title", "").strip()
            if title and not title.startswith("Special:"):
                titles.add(title.replace(" ", "_"))

        # Follow "next page" links
        while True:
            next_link = soup.find("a", string=re.compile(r"Next page", re.I))
            if not next_link:
                break
            next_url = BASE_URL + next_link["href"]
            print(f"  Fetching next index page: {next_url}")
            resp = requests.get(next_url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            for link in soup.select(".mw-allpages-body a"):
                title = link.get("title", "").strip()
                if title and not title.startswith("Special:"):
                    titles.add(title.replace(" ", "_"))
            time.sleep(0.5)

    except Exception as e:
        print(f"  ERR fetching index: {e}")

    return sorted(titles)


def scrape_page(title: str) -> bool:
    """Scrape one wiki page and save as markdown. Returns True on success."""
    slug = slugify(title)
    out_path = OUTPUT_DIR / f"{slug}.md"

    if out_path.exists():
        print(f"  SKIP {title} (already saved)")
        return True

    html = fetch_page(title)
    if not html:
        return False

    soup = BeautifulSoup(html, "lxml")

    # Check it's a real content page (not redirect/missing)
    if soup.find("div", {"id": "mw-content-text"}) is None:
        print(f"  SKIP {title} (no content)")
        return False

    md = html_to_markdown(soup, title)
    out_path.write_text(md, encoding="utf-8")
    return True


def scrape_priority_pages():
    print("\n=== Scraping priority pages ===")
    for title in PRIORITY_PAGES:
        scrape_page(title)
        time.sleep(1)


def scrape_all_pages():
    print("\n=== Fetching full page index ===")
    titles = get_all_wiki_titles()
    print(f"Found {len(titles)} pages total")

    index_path = OUTPUT_DIR / "_index.json"
    index_path.write_text(json.dumps(titles, indent=2), encoding="utf-8")
    print(f"Saved index to {index_path}")

    print("\n=== Scraping all pages ===")
    ok = 0
    fail = 0
    for i, title in enumerate(titles, 1):
        print(f"[{i}/{len(titles)}] {title}")
        if scrape_page(title):
            ok += 1
        else:
            fail += 1
        time.sleep(0.8)  # polite delay

    print(f"\nDone: {ok} saved, {fail} failed")


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "priority"

    if mode == "all":
        scrape_priority_pages()
        scrape_all_pages()
    else:
        scrape_priority_pages()
