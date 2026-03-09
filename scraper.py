#!/usr/bin/env python3
"""
OLX.ba Apartment Listing Watcher
Scrapes OLX.ba search results and sends notifications for new listings.
Supports Email (SMTP) and/or Telegram notifications.
Designed to run on GitHub Actions every 5 minutes.
"""

import json
import os
import re
import smtplib
import sys
import time
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime, timezone

# ─── Configuration ───────────────────────────────────────────────────────────

SEARCH_URL = os.environ.get(
    "OLX_SEARCH_URL",
    "https://olx.ba/pretraga?category_id=23&attr_encoded=1"
    "&attr=3730313228497a6e616a6d6c6a6976616e6a6529&canton=4&cities=42"
)

# --- Telegram (optional) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- Email (optional) ---
SMTP_HOST = os.environ.get("SMTP_HOST", "")           # e.g. smtp.gmail.com
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))    # 587 for TLS, 465 for SSL
SMTP_USER = os.environ.get("SMTP_USER", "")            # e.g. your.email@gmail.com
SMTP_PASS = os.environ.get("SMTP_PASS", "")            # App Password (not your login password)
EMAIL_TO = os.environ.get("EMAIL_TO", "")               # Where to send notifications
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")           # Sender address (defaults to SMTP_USER)

SEEN_IDS_FILE = Path(os.environ.get("SEEN_IDS_FILE", "seen_ids.json"))

# ─── Notifications ───────────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    """Send a message via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                print(f"[OK] Telegram message sent.")
                return True
            else:
                print(f"[ERR] Telegram API error: {result}")
                return False
    except Exception as e:
        print(f"[ERR] Failed to send Telegram message: {e}")
        return False


def send_email(subject: str, body_html: str, body_text: str = "") -> bool:
    """Send an email via SMTP (works with Gmail, Outlook, Yahoo, etc.)."""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not EMAIL_TO:
        return False

    sender = EMAIL_FROM or SMTP_USER
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"OLX Watcher <{sender}>"
    msg["To"] = EMAIL_TO

    # Plain text fallback
    if not body_text:
        body_text = re.sub(r"<[^>]+>", "", body_html)
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if SMTP_PORT == 465:
            # SSL connection
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
        else:
            # STARTTLS connection (port 587)
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            server.starttls()

        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(sender, [EMAIL_TO], msg.as_string())
        server.quit()
        print(f"[OK] Email sent to {EMAIL_TO}.")
        return True
    except Exception as e:
        print(f"[ERR] Failed to send email: {e}")
        return False


def notify(message_html: str, subject: str = "🏠 Novi oglas na OLX.ba"):
    """Send notification via all configured channels."""
    sent = False

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        if send_telegram(message_html):
            sent = True

    if SMTP_HOST and EMAIL_TO:
        # Wrap in a nice HTML email template
        email_body = f"""
        <div style="font-family: -apple-system, Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
            <div style="background: #f0f7ff; border-left: 4px solid #2563eb; padding: 16px; border-radius: 8px;">
                {message_html.replace(chr(10), '<br>')}
            </div>
            <p style="color: #888; font-size: 12px; margin-top: 16px;">
                Automatska obavijest od OLX Watcher bota
            </p>
        </div>
        """
        if send_email(subject, email_body):
            sent = True

    if not sent:
        print(f"[WARN] No notification channel configured. Message:\n{message_html}")


# ─── State Management ────────────────────────────────────────────────────────

def load_seen_ids() -> set:
    """Load previously seen listing IDs from JSON file."""
    if SEEN_IDS_FILE.exists():
        try:
            data = json.loads(SEEN_IDS_FILE.read_text(encoding="utf-8"))
            return set(data.get("ids", []))
        except (json.JSONDecodeError, KeyError):
            return set()
    return set()


def save_seen_ids(ids: set):
    """Persist seen listing IDs to JSON file."""
    data = {
        "ids": sorted(ids),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(ids),
    }
    SEEN_IDS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Saved {len(ids)} seen IDs.")


# ─── Scraping Methods ────────────────────────────────────────────────────────

def extract_listings_from_html(html: str) -> list[dict]:
    """
    Try to extract listings from page HTML.
    Method 1: Look for embedded JSON data (Nuxt/Next __NUXT_DATA__ or similar).
    Method 2: Parse listing cards from rendered HTML.
    """
    listings = []

    # Method 1: Look for JSON data embedded in script tags
    # OLX.ba often embeds initial state as JSON in a script tag
    json_patterns = [
        r'window\.__NUXT__\s*=\s*({.+?})\s*;?\s*</script>',
        r'window\.__INITIAL_STATE__\s*=\s*({.+?})\s*;?\s*</script>',
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.+?)</script>',
        r'"listings"\s*:\s*(\[.+?\])',
        r'"items"\s*:\s*(\[.+?\])',
        r'"data"\s*:\s*(\[.+?\])\s*,\s*"meta"',
    ]
    for pattern in json_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                print(f"[INFO] Found embedded JSON data via pattern.")
                # Try to extract listing info from the JSON structure
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and ("id" in item or "slug" in item):
                            listings.append({
                                "id": str(item.get("id", item.get("slug", ""))),
                                "title": item.get("title", "N/A"),
                                "price": item.get("display_price", item.get("price", "N/A")),
                                "url": f"https://olx.ba/artikal/{item['id']}" if "id" in item else "",
                                "location": item.get("location", {}).get("city_name", ""),
                            })
                break
            except (json.JSONDecodeError, TypeError):
                continue

    # Method 2: Parse listing cards from HTML (works if SSR is enabled)
    if not listings:
        # Look for article/listing links with IDs
        article_pattern = r'href="[/]?artikal[/](\d+)"'
        found_ids = re.findall(article_pattern, html)

        # Also try other common patterns
        if not found_ids:
            article_pattern = r'/artikal/(\d+)'
            found_ids = re.findall(article_pattern, html)

        for article_id in set(found_ids):
            listings.append({
                "id": article_id,
                "title": "New listing",
                "price": "N/A",
                "url": f"https://olx.ba/artikal/{article_id}",
                "location": "",
            })

    return listings


def scrape_with_playwright() -> list[dict]:
    """Use Playwright to render the SPA and extract listings."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERR] Playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    listings = []
    print(f"[INFO] Launching Playwright for: {SEARCH_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="bs-BA",
        )
        page = context.new_page()

        try:
            page.goto(SEARCH_URL, wait_until="networkidle", timeout=45000)
            # Give extra time for dynamic content to load
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[WARN] Page load issue: {e}. Continuing with partial content...")

        # Try to get listing data from the page
        try:
            # First, try to intercept API responses
            # The page has already loaded, so let's extract from DOM
            listing_elements = page.query_selector_all(
                'a[href*="/artikal/"], '
                '[class*="listing"], '
                '[class*="article"], '
                '[class*="product-item"], '
                '[class*="ad-item"], '
                '[class*="classified"]'
            )

            if not listing_elements:
                # Broader search - look for any cards/items in the results area
                listing_elements = page.query_selector_all(
                    '.product-card, .listing-card, .ad-card, '
                    '[data-listing-id], [data-id], '
                    'article, .item'
                )

            print(f"[INFO] Found {len(listing_elements)} potential listing elements in DOM.")

            # Extract article links from the page
            all_links = page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a[href*="/artikal/"]');
                    return Array.from(links).map(a => {
                        const card = a.closest('[class*="listing"], [class*="product"], [class*="article"], [class*="card"], article, .item') || a.parentElement?.parentElement;
                        return {
                            href: a.href,
                            text: card ? card.innerText.trim().substring(0, 300) : a.innerText.trim().substring(0, 300),
                        };
                    });
                }
            """)

            seen_urls = set()
            for link_data in all_links:
                href = link_data.get("href", "")
                text = link_data.get("text", "")

                match = re.search(r'/artikal/(\d+)', href)
                if match and href not in seen_urls:
                    seen_urls.add(href)
                    article_id = match.group(1)

                    # Parse title and price from the card text
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    title = lines[0] if lines else "New listing"
                    price = "N/A"
                    for line in lines:
                        if "KM" in line or "€" in line or re.search(r'\d+[\.,]\d+', line):
                            price = line
                            break

                    listings.append({
                        "id": article_id,
                        "title": title[:100],
                        "price": price[:50],
                        "url": f"https://olx.ba/artikal/{article_id}",
                        "location": "",
                    })

            # If we still found nothing, try getting the full page HTML
            if not listings:
                html = page.content()
                listings = extract_listings_from_html(html)

        except Exception as e:
            print(f"[ERR] Error extracting listings: {e}")
            # Last resort: get page HTML and parse
            try:
                html = page.content()
                listings = extract_listings_from_html(html)
            except Exception:
                pass

        browser.close()

    return listings


def scrape_with_requests() -> list[dict]:
    """
    Try a lightweight approach first using urllib (no browser needed).
    Attempts to call the OLX.ba internal API directly.
    """
    listings = []

    # Parse search URL parameters
    parsed = urllib.parse.urlparse(SEARCH_URL)
    params = urllib.parse.parse_qs(parsed.query)

    # Try the internal API endpoint that the frontend likely uses
    api_urls = [
        f"https://api.olx.ba/search?{parsed.query}",
        f"https://olx.ba/api/search?{parsed.query}",
        f"https://api.olx.ba/listings?category_id={params.get('category_id', [''])[0]}"
        f"&canton={params.get('canton', [''])[0]}"
        f"&cities={params.get('cities', [''])[0]}"
        f"&listing_type=rent",
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "bs,en;q=0.9",
        "Referer": "https://olx.ba/",
    }

    for api_url in api_urls:
        try:
            print(f"[INFO] Trying API: {api_url[:80]}...")
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")

                # Try to parse as JSON (API response)
                try:
                    data = json.loads(content)
                    items = []
                    if isinstance(data, dict):
                        items = data.get("data", data.get("listings", data.get("items", [])))
                    elif isinstance(data, list):
                        items = data

                    if items:
                        for item in items:
                            if isinstance(item, dict) and "id" in item:
                                listings.append({
                                    "id": str(item["id"]),
                                    "title": item.get("title", "N/A"),
                                    "price": item.get("display_price", str(item.get("price", "N/A"))),
                                    "url": f"https://olx.ba/artikal/{item['id']}",
                                    "location": "",
                                })
                        if listings:
                            print(f"[OK] Got {len(listings)} listings from API.")
                            return listings
                except json.JSONDecodeError:
                    pass

                # Try to parse as HTML
                html_listings = extract_listings_from_html(content)
                if html_listings:
                    listings = html_listings
                    print(f"[OK] Got {len(listings)} listings from HTML.")
                    return listings

        except Exception as e:
            print(f"[WARN] API attempt failed: {e}")
            continue

    # Also try fetching the search page directly
    try:
        print(f"[INFO] Fetching search page directly...")
        req = urllib.request.Request(SEARCH_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8")
            listings = extract_listings_from_html(html)
            if listings:
                print(f"[OK] Got {len(listings)} listings from search page HTML.")
    except Exception as e:
        print(f"[WARN] Direct page fetch failed: {e}")

    return listings


# ─── Main Logic ──────────────────────────────────────────────────────────────

def format_notification(listing: dict) -> str:
    """Format a single listing as a Telegram notification message."""
    return (
        f"🏠 <b>Novi oglas na OLX.ba!</b>\n\n"
        f"📌 <b>{listing['title']}</b>\n"
        f"💰 {listing['price']}\n"
        f"🔗 {listing['url']}"
    )


def main():
    print(f"\n{'='*60}")
    print(f"OLX.ba Watcher - {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    # Load previously seen IDs
    seen_ids = load_seen_ids()
    is_first_run = len(seen_ids) == 0
    print(f"[INFO] Loaded {len(seen_ids)} previously seen IDs. First run: {is_first_run}")

    # Try lightweight approach first, fall back to Playwright
    listings = scrape_with_requests()

    if not listings:
        print("[INFO] Lightweight scraping found nothing. Trying Playwright...")
        listings = scrape_with_playwright()

    if not listings:
        print("[WARN] No listings found by any method. The page structure may have changed.")
        notify("⚠️ OLX Watcher: Nije pronađen nijedan oglas. Možda je stranica promijenjena.",
               subject="⚠️ OLX Watcher — Problem")
        sys.exit(0)

    print(f"\n[INFO] Total listings found: {len(listings)}")
    for l in listings:
        print(f"  - [{l['id']}] {l['title'][:50]} | {l['price']}")

    # Find new listings
    current_ids = {l["id"] for l in listings}
    new_ids = current_ids - seen_ids

    if is_first_run:
        print(f"\n[INFO] First run - saving {len(current_ids)} listings as baseline. No notifications sent.")
        save_seen_ids(current_ids)
        notify(
            f"✅ <b>OLX Watcher pokrenut!</b>\n\n"
            f"Pratim oglase za iznajmljivanje stanova u Zenici.\n"
            f"Trenutno {len(current_ids)} aktivnih oglasa.\n"
            f"Obavijestit ću te čim se pojavi novi oglas! 🔔",
            subject="✅ OLX Watcher pokrenut!"
        )
        return

    if new_ids:
        new_listings = [l for l in listings if l["id"] in new_ids]
        print(f"\n🔔 Found {len(new_listings)} NEW listing(s)!")

        # For email: batch all new listings into one email
        if SMTP_HOST and EMAIL_TO and len(new_listings) > 1:
            batch_html = "🏠 <b>Novi oglasi na OLX.ba!</b>\n\n"
            for listing in new_listings:
                batch_html += (
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📌 <b>{listing['title']}</b>\n"
                    f"💰 {listing['price']}\n"
                    f"🔗 <a href=\"{listing['url']}\">{listing['url']}</a>\n\n"
                )
            email_body = f"""
            <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #2563eb;">🏠 {len(new_listings)} novih oglasa na OLX.ba!</h2>
                {''.join(f'''
                <div style="background: #f0f7ff; border-left: 4px solid #2563eb; padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                    <b>{l['title']}</b><br>
                    💰 {l['price']}<br>
                    <a href="{l['url']}" style="color: #2563eb;">{l['url']}</a>
                </div>
                ''' for l in new_listings)}
                <p style="color: #888; font-size: 12px; margin-top: 16px;">Automatska obavijest od OLX Watcher bota</p>
            </div>
            """
            send_email(
                subject=f"🏠 {len(new_listings)} novih oglasa na OLX.ba",
                body_html=email_body
            )
        elif SMTP_HOST and EMAIL_TO:
            # Single new listing — send individual email
            listing = new_listings[0]
            notify(format_notification(listing))

        # For Telegram: always send individual messages
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            for listing in new_listings:
                msg = format_notification(listing)
                send_telegram(msg)
                time.sleep(0.5)  # Avoid Telegram rate limits

        # If only email is configured and we already sent batch, skip
        # If neither is configured, notify() handles the warning
        if not (SMTP_HOST and EMAIL_TO) and not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
            for listing in new_listings:
                notify(format_notification(listing))

        # Update seen IDs (keep current + previously seen to handle removed/re-added)
        seen_ids.update(current_ids)
        save_seen_ids(seen_ids)
    else:
        print(f"\n[INFO] No new listings. All {len(current_ids)} listings already seen.")
        # Still update the file to refresh timestamp
        seen_ids.update(current_ids)
        save_seen_ids(seen_ids)

    # Cleanup: remove very old IDs to prevent file from growing indefinitely
    # Keep last 500 IDs max
    if len(seen_ids) > 500:
        print("[INFO] Pruning old IDs (keeping last 500)...")
        # Keep the most recent ones (highest IDs are usually newest)
        sorted_ids = sorted(seen_ids, key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
        seen_ids = set(sorted_ids[:500])
        save_seen_ids(seen_ids)


if __name__ == "__main__":
    main()
