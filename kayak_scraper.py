#!/usr/bin/env python3
"""Standalone Kayak price scraper with anti-bot measures."""
import re
import json
import sys
import random
import time

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
]


def extract_prices(page):
    """Extract flight prices from Kayak page using multiple selectors."""
    parsed = []
    # Try specific Kayak price selectors first
    for selector in ['.Hv20-value', '[class*="hYzH-price"]', '[class*="price-text"]']:
        for el in page.query_selector_all(selector):
            txt = el.inner_text().strip().replace("\xa0", " ").replace("\u202f", " ")
            m = re.search(r"(\d[\d\s,.]*\d)\s*zł", txt)
            if m:
                try:
                    val = int(m.group(1).replace(" ", "").replace(",", "").replace(".", ""))
                    if 200 <= val <= 50000:
                        parsed.append(val)
                except ValueError:
                    pass
        if parsed:
            return parsed

    # Fallback: broader [class*="price"]
    for el in page.query_selector_all('[class*="price"]'):
        txt = el.inner_text().strip().replace("\xa0", " ").replace("\u202f", " ")
        m = re.search(r"(\d[\d\s,.]*\d)\s*zł", txt)
        if m:
            try:
                val = int(m.group(1).replace(" ", "").replace(",", "").replace(".", ""))
                if 200 <= val <= 50000:
                    parsed.append(val)
            except ValueError:
                pass
    return parsed


def scrape_kayak(url, max_retries=2):
    from playwright.sync_api import sync_playwright

    # Extract expected route from URL for validation
    route_match = re.search(r'/flights/([A-Z]{3})-([A-Z]{3})/', url)
    expected_origin = route_match.group(1) if route_match else None
    expected_dest = route_match.group(2) if route_match else None

    # Random delay before starting (avoid burst patterns)
    time.sleep(random.uniform(1, 4))

    for attempt in range(max_retries):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        f"--window-size={random.randint(1200,1400)},{random.randint(750,900)}",
                    ],
                )
                ctx = browser.new_context(
                    locale="pl-PL",
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": random.randint(1200, 1400), "height": random.randint(750, 900)},
                    java_script_enabled=True,
                )
                page = ctx.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    window.chrome = {runtime: {}};
                """)

                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                # Wait with random duration
                page.wait_for_timeout(random.randint(10000, 15000))

                # Check for bot detection / redirects
                final_url = page.url
                if "security" in final_url or "captcha" in final_url:
                    ctx.close()
                    browser.close()
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(5, 10))
                        continue
                    return None

                # Check for "no flights" message
                body_lower = page.inner_text("body").lower()
                if "brak pasujących lotów" in body_lower:
                    ctx.close()
                    browser.close()
                    return None

                # Extract prices
                prices = extract_prices(page)

                ctx.close()
                browser.close()

                if prices:
                    return min(prices)

                # No prices found — might be blocked, retry
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 7))
                    continue

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(random.uniform(3, 7))
                continue

    return None


if __name__ == "__main__":
    url = sys.argv[1]
    price = scrape_kayak(url)
    print(json.dumps({"price": price, "url": url}))
