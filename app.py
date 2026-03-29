#!/usr/bin/env python3
"""Flight Finder — aggregates cheap flights from multiple sources."""

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import TimeoutError
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

POLISH_AIRPORTS = {
    "WAW": "Warszawa Chopin",
    "WMI": "Warszawa Modlin",
    "KRK": "Kraków",
    "GDN": "Gdańsk",
    "KTW": "Katowice",
    "POZ": "Poznań",
    "WRO": "Wrocław",
    "BER": "Berlin",
}

DEST_GROUPS = [
    {"name": "Wyspy Kanaryjskie", "keyword": "canary islands", "airports": [
        {"code": "FUE", "name": "Fuerteventura"},
        {"code": "TFS", "name": "Teneryfa Płd"},
        {"code": "TFN", "name": "Teneryfa Płn"},
        {"code": "LPA", "name": "Gran Canaria"},
        {"code": "ACE", "name": "Lanzarote"},
        {"code": "SPC", "name": "La Palma"},
    ]},
    {"name": "Baleary", "keyword": "balearic", "airports": [
        {"code": "PMI", "name": "Majorka"},
        {"code": "IBZ", "name": "Ibiza"},
        {"code": "MAH", "name": "Minorka"},
    ]},
    {"name": "Grecja", "keyword": "greece", "airports": [
        {"code": "ATH", "name": "Ateny"},
        {"code": "SKG", "name": "Saloniki"},
        {"code": "HER", "name": "Kreta Heraklion"},
        {"code": "CHQ", "name": "Kreta Chania"},
        {"code": "RHO", "name": "Rodos"},
        {"code": "CFU", "name": "Korfu"},
        {"code": "ZTH", "name": "Zakynthos"},
        {"code": "KGS", "name": "Kos"},
        {"code": "JMK", "name": "Mykonos"},
        {"code": "JTR", "name": "Santorini"},
    ]},
    {"name": "Turcja", "keyword": "turkey", "airports": [
        {"code": "AYT", "name": "Antalya"},
        {"code": "DLM", "name": "Dalaman"},
        {"code": "ADB", "name": "Izmir"},
        {"code": "SAW", "name": "Stambuł Sabiha"},
        {"code": "IST", "name": "Stambuł"},
    ]},
    {"name": "Hiszpania", "keyword": "spain", "airports": [
        {"code": "BCN", "name": "Barcelona"},
        {"code": "AGP", "name": "Malaga"},
        {"code": "ALC", "name": "Alicante"},
        {"code": "VLC", "name": "Walencja"},
        {"code": "MAD", "name": "Madryt"},
        {"code": "SVQ", "name": "Sewilla"},
    ]},
    {"name": "Portugalia", "keyword": "portugal", "airports": [
        {"code": "FAO", "name": "Faro (Algarve)"},
        {"code": "LIS", "name": "Lizbona"},
        {"code": "OPO", "name": "Porto"},
        {"code": "FNC", "name": "Madera"},
    ]},
    {"name": "Włochy", "keyword": "italy", "airports": [
        {"code": "FCO", "name": "Rzym"},
        {"code": "NAP", "name": "Neapol"},
        {"code": "BGY", "name": "Mediolan Bergamo"},
        {"code": "MXP", "name": "Mediolan Malpensa"},
        {"code": "PSA", "name": "Pisa"},
        {"code": "CTA", "name": "Katania (Sycylia)"},
        {"code": "PMO", "name": "Palermo"},
    ]},
    {"name": "Chorwacja", "keyword": "croatia", "airports": [
        {"code": "SPU", "name": "Split"},
        {"code": "DBV", "name": "Dubrownik"},
        {"code": "ZAG", "name": "Zagrzeb"},
    ]},
    {"name": "Egipt", "keyword": "egypt", "airports": [
        {"code": "HRG", "name": "Hurghada"},
        {"code": "SSH", "name": "Sharm el-Sheikh"},
    ]},
    {"name": "Maroko", "keyword": "morocco", "airports": [
        {"code": "RAK", "name": "Marrakesz"},
        {"code": "CMN", "name": "Casablanka"},
    ]},
    {"name": "Azja", "keyword": "asia", "airports": [
        {"code": "BKK", "name": "Bangkok"},
        {"code": "HKT", "name": "Phuket"},
        {"code": "DPS", "name": "Bali"},
        {"code": "KUL", "name": "Kuala Lumpur"},
        {"code": "SIN", "name": "Singapur"},
        {"code": "HND", "name": "Tokio"},
    ]},
    {"name": "Wielka Brytania", "keyword": "uk", "airports": [
        {"code": "STN", "name": "Londyn Stansted"},
        {"code": "LTN", "name": "Londyn Luton"},
        {"code": "DUB", "name": "Dublin"},
        {"code": "EDI", "name": "Edynburg"},
    ]},
    {"name": "Skandynawia", "keyword": "scandinavia", "airports": [
        {"code": "OSL", "name": "Oslo"},
        {"code": "CPH", "name": "Kopenhaga"},
        {"code": "ARN", "name": "Sztokholm"},
        {"code": "HEL", "name": "Helsinki"},
    ]},
    {"name": "Europa Śr.", "keyword": "central europe", "airports": [
        {"code": "VIE", "name": "Wiedeń"},
        {"code": "BUD", "name": "Budapeszt"},
        {"code": "PRG", "name": "Praga"},
        {"code": "BTS", "name": "Bratysława"},
        {"code": "OTP", "name": "Bukareszt"},
        {"code": "SOF", "name": "Sofia"},
    ]},
    {"name": "Ameryka", "keyword": "america", "airports": [
        {"code": "JFK", "name": "Nowy Jork"},
        {"code": "MIA", "name": "Miami"},
        {"code": "CUN", "name": "Cancun"},
    ]},
]

# ---------------------------------------------------------------------------
# SOURCE 1: Ryanair Fare Finder API
# ---------------------------------------------------------------------------
EUR_TO_PLN = 4.28  # approximate exchange rate

# ---------------------------------------------------------------------------
# REAL PRICE FETCHER via Playwright + Kayak
# ---------------------------------------------------------------------------
_playwright_instance = None
_browser_instance = None


def get_browser():
    """Lazy-init a shared Playwright browser instance."""
    global _playwright_instance, _browser_instance
    if _browser_instance is None:
        from playwright.sync_api import sync_playwright
        _playwright_instance = sync_playwright().start()
        _browser_instance = _playwright_instance.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )
    return _browser_instance


def fetch_kayak_price(origin, dest, date_out, date_ret, adults=1, max_stops=None):
    """Fetch cheapest RT price from Kayak for 1 adult. Returns price in PLN or None."""
    stops_param = ""
    if max_stops is not None:
        stops_param = f"&fs=stops={max_stops}"

    url = (
        f"https://www.kayak.pl/flights/{origin}-{dest}/{date_out}/{date_ret}"
        f"?sort=price_a&currency=PLN{stops_param}"
    )
    try:
        browser = get_browser()
        ctx = browser.new_context(
            locale='pl-PL',
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
        )
        page = ctx.new_page()
        page.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined})')
        page.goto(url, timeout=25000)
        page.wait_for_timeout(12000)

        # Use Kayak's price CSS selector for accurate prices
        parsed = []
        price_els = page.query_selector_all('[class*="price"]')
        for el in price_els:
            txt = el.inner_text().strip().replace('\xa0', ' ').replace('\u202f', ' ')
            match = re.search(r'(\d[\d\s,.]*\d)\s*zł', txt)
            if match:
                try:
                    val = int(match.group(1).replace(' ', '').replace(',', '').replace('.', ''))
                    if 200 <= val <= 50000:
                        parsed.append(val)
                except ValueError:
                    pass

        ctx.close()

        if parsed:
                cheapest = min(parsed)
                log.info(f"Kayak price {origin}→{dest}: {cheapest} PLN (found {len(parsed)} prices)")
                return cheapest, url
        log.warning(f"Kayak: No prices found for {origin}→{dest}")
        return None, url
    except Exception as e:
        log.error(f"Kayak fetch error {origin}→{dest}: {e}")
        return None, url


def search_ryanair(origin, dest, date_from, date_to, flex_days=3):
    """Query Ryanair's public fare-finder for one-way fares."""
    results = []
    url = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
    params = {
        "departureAirportIataCode": origin,
        "arrivalAirportIataCode": dest,
        "language": "pl",
        "market": "pl-pl",
        "outboundDepartureDateFrom": date_from,
        "outboundDepartureDateTo": date_to,
        "currency": "PLN",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for fare in data.get("fares", []):
                out = fare.get("outbound", {})
                price = out.get("price", {})
                dep_date = out.get("departureDate", "")[:10]
                results.append({
                    "source": "Ryanair",
                    "airline": "Ryanair",
                    "origin": origin,
                    "destination": dest,
                    "date": dep_date,
                    "price_per_person": price.get("value", 0),
                    "currency": price.get("currencyCode", "PLN"),
                    "direct": not out.get("connectedFlights"),
                    "direction": "outbound",
                    "link": f"https://www.ryanair.com/pl/pl/trip/flights/select?adults=2&teens=0&children=2&infants=0&dateOut={dep_date}&originIata={origin}&destinationIata={dest}",
                    "notes": "Cena w jedną stronę, bez bagażu",
                })
        else:
            log.warning(f"Ryanair {origin}->{dest}: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"Ryanair {origin}->{dest}: {e}")
    return results


def search_ryanair_return(origin, dest, date_ret_from, date_ret_to):
    """Query Ryanair return flights (dest -> origin)."""
    results = []
    url = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
    params = {
        "departureAirportIataCode": dest,
        "arrivalAirportIataCode": origin,
        "language": "pl",
        "market": "pl-pl",
        "outboundDepartureDateFrom": date_ret_from,
        "outboundDepartureDateTo": date_ret_to,
        "currency": "PLN",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for fare in data.get("fares", []):
                out = fare.get("outbound", {})
                price = out.get("price", {})
                dep_date = out.get("departureDate", "")[:10]
                results.append({
                    "source": "Ryanair",
                    "airline": "Ryanair",
                    "origin": dest,
                    "destination": origin,
                    "date": dep_date,
                    "price_per_person": price.get("value", 0),
                    "currency": price.get("currencyCode", "PLN"),
                    "direct": not out.get("connectedFlights"),
                    "direction": "return",
                    "link": f"https://www.ryanair.com/pl/pl/trip/flights/select?adults=2&teens=0&children=2&infants=0&dateOut={dep_date}&originIata={dest}&destinationIata={origin}",
                    "notes": "Powrót, cena w jedną stronę, bez bagażu",
                })
        else:
            log.warning(f"Ryanair return {dest}->{origin}: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"Ryanair return {dest}->{origin}: {e}")
    return results


# ---------------------------------------------------------------------------
# SOURCE 2: Wizz Air search
# ---------------------------------------------------------------------------
def search_wizzair(origin, dest, date_from, date_to):
    """Try Wizz Air API — often blocked, so we handle gracefully."""
    results = []
    try:
        # Get API URL from metadata
        meta_url = "https://wizzair.com/static_fe/metadata.json"
        meta = requests.get(meta_url, headers=HEADERS, timeout=10)
        if meta.status_code != 200:
            log.warning("Wizz Air metadata unavailable")
            return results
        api_url = meta.json().get("apiUrl", "")
        if not api_url:
            return results

        search_url = f"{api_url}/search/timetable"
        payload = {
            "flightList": [{
                "departureStation": origin,
                "arrivalStation": dest,
                "from": date_from,
                "to": date_to,
            }],
            "priceType": "regular",
            "adultCount": 2,
            "childCount": 2,
        }
        r = requests.post(search_url, json=payload, headers={
            **HEADERS,
            "Content-Type": "application/json",
        }, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for flight_list in data.get("outboundFlights", []):
                dep = flight_list.get("departureDateTime", "")[:10]
                price = flight_list.get("priceType", {}).get("regular", {}).get("amount", 0)
                results.append({
                    "source": "Wizz Air",
                    "airline": "Wizz Air",
                    "origin": origin,
                    "destination": dest,
                    "date": dep,
                    "price_per_person": price,
                    "currency": "PLN",
                    "direct": True,
                    "link": f"https://wizzair.com/pl-pl/booking/select-flight/search?departureDate={dep}&departureAirport={origin}&arrivalAirport={dest}&adults=2&children=2",
                    "notes": "Cena bez bagażu",
                })
        else:
            log.warning(f"Wizz Air {origin}->{dest}: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"Wizz Air {origin}->{dest}: {e}")
    return results


# ---------------------------------------------------------------------------
# SOURCE 3: Google Flights (scrape booking links from URL)
# ---------------------------------------------------------------------------
def build_google_flights_url(origin, dest, date_out, date_ret, adults=2, children=2):
    """Build a Google Flights search URL."""
    return (
        f"https://www.google.com/travel/flights?q=Flights+from+{origin}+to+{dest}"
        f"+on+{date_out}+through+{date_ret}"
        f"+for+{adults}+adults+{children}+children&curr=PLN&hl=pl"
    )


# ---------------------------------------------------------------------------
# SOURCE 4: SecretFlying error fares
# ---------------------------------------------------------------------------
def search_secretflying(destination_keyword="fuerteventura", origin_keyword="poland"):
    """Scrape SecretFlying for ACTIVE error fares / deals to a destination."""
    results = []
    search_url = f"https://www.secretflying.com/?s={destination_keyword}"
    cutoff = datetime.now() - timedelta(days=60)  # Only deals from last 60 days
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            articles = soup.select("article.post, div.deal, .entry-content article, .sfly-card, article")[:20]
            for art in articles:
                # Skip expired deals
                full_text = art.get_text(" ", strip=True).lower()
                if "expired" in full_text:
                    continue

                title_el = art.select_one("h2 a, h3 a, .entry-title a, a.sfly-card__link")
                if not title_el:
                    title_el = art.select_one("a[href]")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "")

                # Check publish date — skip old posts
                time_el = art.select_one("time[datetime], .entry-date, .post-date, .date")
                pub_date = None
                if time_el:
                    date_str = time_el.get("datetime") or time_el.get_text(strip=True)
                    try:
                        # Try ISO format first
                        pub_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except (ValueError, TypeError):
                        # Try common formats
                        for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d/%m/%Y"]:
                            try:
                                pub_date = datetime.strptime(date_str.strip(), fmt)
                                break
                            except ValueError:
                                continue

                if pub_date and pub_date < cutoff:
                    log.debug(f"SecretFlying: Skipping old deal from {pub_date}: {title[:50]}")
                    continue

                # Filter for relevant deals
                title_lower = title.lower()
                if destination_keyword.lower() not in title_lower and "fue" not in title_lower and "canary" not in title_lower and "kanar" not in title_lower and "fuerteventura" not in title_lower:
                    continue

                # Try to extract price from title
                price_match = re.search(r'[\$€£]\s*(\d+)', title)
                price_pln_match = re.search(r'(\d+)\s*(?:PLN|zł)', title)
                price = 0
                currency = "EUR"
                if price_pln_match:
                    price = int(price_pln_match.group(1))
                    currency = "PLN"
                elif price_match:
                    price = int(price_match.group(1))
                    currency = "EUR"

                date_label = pub_date.strftime("%Y-%m-%d") if pub_date else "See link"

                results.append({
                    "source": "SecretFlying",
                    "airline": "Error Fare / Deal",
                    "origin": "Various",
                    "destination": destination_keyword.upper()[:3] if len(destination_keyword) == 3 else "FUE",
                    "date": date_label,
                    "price_per_person": price,
                    "currency": currency,
                    "direct": None,
                    "link": link,
                    "notes": f"AKTYWNY: {title[:120]}" if not pub_date or pub_date > cutoff else title[:120],
                })

            if not results:
                log.info(f"SecretFlying: No active deals found for '{destination_keyword}'")
        else:
            log.warning(f"SecretFlying: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"SecretFlying: {e}")
    return results


# ---------------------------------------------------------------------------
# SOURCE 5: Kiwi.com (Tequila-like search via public page scraping)
# ---------------------------------------------------------------------------
def build_kiwi_url(origin_city, dest, date_out, date_ret, adults=2, children=2, max_stops=None):
    """Build Kiwi.com search URL."""
    stops_param = f"&stopNumber={max_stops}" if max_stops is not None else ""
    return (
        f"https://www.kiwi.com/pl/search/tiles/{origin_city}/fuerteventura-wyspy-kanaryjskie-hiszpania"
        f"/{date_out}/{date_ret}?adults={adults}&children={children}&sortBy=price{stops_param}"
    )


# ---------------------------------------------------------------------------
# SOURCE 6: Skyscanner URL builder
# ---------------------------------------------------------------------------
def build_skyscanner_url(origin, dest, date_out, date_ret, adults=2, children=2):
    """Build Skyscanner search URL."""
    date_out_fmt = date_out.replace("-", "")[:8]
    date_ret_fmt = date_ret.replace("-", "")[:8]
    return (
        f"https://www.skyscanner.pl/transport/flights/{origin.lower()}/{dest.lower()}"
        f"/{date_out_fmt}/{date_ret_fmt}/"
        f"?adults={adults}&children={children}&currency=PLN"
    )


# ---------------------------------------------------------------------------
# SOURCE 7: Rainbow Tours / r.pl charter scraping
# ---------------------------------------------------------------------------
def search_rainbow(destination="fuerteventura"):
    """Scrape Rainbow Tours for charter packages."""
    results = []
    url = f"https://r.pl/wyszukiwarka?destination={destination}&adults=2&children=2"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            offers = soup.select(".offer-card, .search-result-item, .offer, article")[:10]
            for offer in offers:
                title = offer.get_text(strip=True)[:200]
                price_match = re.search(r'(\d[\d\s]*)\s*(?:zł|PLN)', title.replace('\xa0', ' '))
                link_el = offer.select_one("a[href]")
                link = link_el["href"] if link_el else url
                if not link.startswith("http"):
                    link = "https://r.pl" + link
                if price_match:
                    price_str = price_match.group(1).replace(' ', '').replace('\xa0', '')
                    results.append({
                        "source": "Rainbow Tours",
                        "airline": "Charter",
                        "origin": "Various PL",
                        "destination": "FUE",
                        "date": "See link",
                        "price_per_person": int(price_str),
                        "currency": "PLN",
                        "direct": True,
                        "link": link,
                        "notes": "Pakiet czarterowy (lot + hotel)",
                    })
        else:
            log.warning(f"Rainbow: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"Rainbow: {e}")
    return results


# ---------------------------------------------------------------------------
# SOURCE 8: Flippo.pl URL builder
# ---------------------------------------------------------------------------
def build_flippo_url(origin, dest, date_out, date_ret, adults=2, children=2):
    return (
        f"https://www.flippo.pl/flights/{origin}-{dest}/{date_out}/{date_ret}"
        f"?adults={adults}&children={children}"
    )


# ---------------------------------------------------------------------------
# SOURCE 9: AZair — aggregator for low-cost carriers
# ---------------------------------------------------------------------------
AZAIR_AIRPORT_MAP = {
    "WAW": "WAW", "WMI": "WMI", "KRK": "KRK", "GDN": "GDN",
    "KTW": "KTW", "POZ": "POZ", "WRO": "WRO", "BER": "SXF",
}

def search_azair(origin, dest, date_from, date_to, date_ret_from, date_ret_to, adults=2, children=2):
    """Scrape AZair for cheap flights from low-cost carriers."""
    results = []
    az_origin = AZAIR_AIRPORT_MAP.get(origin, origin)
    # AZair date format: YYYY-MM-DD
    url = (
        f"https://www.azair.eu/azfin.php"
        f"?searchtype=flexi"
        f"&tp=0"
        f"&is498=true&ismark=true&iswizz=true&isryan=true&iseazy=true&isvueling=true&isjet2=true&isnorw=true&istransavia=true&ispegasus=true"
        f"&srcAirport={az_origin}"
        f"&dstAirport={dest}"
        f"&outDateFrom={date_from}"
        f"&outDateTo={date_to}"
        f"&inDateFrom={date_ret_from}"
        f"&inDateTo={date_ret_to}"
        f"&minDaysStay=12&maxDaysStay=14"
        f"&adults={adults}&children={children}&infants=0"
        f"&maxChng=1"
        f"&currency=PLN"
        f"&lang=pl"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            # AZair results are in div.result or similar containers
            result_divs = soup.select("div.result, div.res, tr.result")[:15]
            for div in result_divs:
                text = div.get_text(" ", strip=True)
                # Try to extract price
                price_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:PLN|zł|EUR|€)', text)
                # Extract dates
                date_match = re.search(r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})', text)
                # Extract airline
                airline = "Low-cost"
                for al in ["Ryanair", "Wizz", "easyJet", "Vueling", "Transavia", "Norwegian", "Jet2"]:
                    if al.lower() in text.lower():
                        airline = al
                        break
                link_el = div.select_one("a[href]")
                link = link_el["href"] if link_el else url
                if link and not link.startswith("http"):
                    link = "https://www.azair.eu/" + link.lstrip("/")

                if price_match:
                    price_str = price_match.group(1).replace(",", ".")
                    currency = "EUR" if ("EUR" in text or "€" in text) else "PLN"
                    results.append({
                        "source": "AZair",
                        "airline": airline,
                        "origin": origin,
                        "destination": dest,
                        "date": date_match.group(1) if date_match else "See link",
                        "price_per_person": float(price_str),
                        "currency": currency,
                        "direct": "direct" in text.lower() or "bezpośredni" in text.lower(),
                        "link": link,
                        "notes": "AZair aggregator; cena w obie strony/os" if "return" in text.lower() or "w obie" in text.lower() else "AZair aggregator",
                    })
            # If no structured results, try to parse the page text for any flight info
            if not results:
                # AZair sometimes returns results as plain text blocks
                all_text = soup.get_text()
                if "no flights" in all_text.lower() or "brak" in all_text.lower():
                    log.info(f"AZair {origin}->{dest}: No flights found")
                else:
                    log.info(f"AZair {origin}->{dest}: Page loaded but no parseable results")
        else:
            log.warning(f"AZair {origin}->{dest}: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"AZair {origin}->{dest}: {e}")
    return results


def build_azair_url(origin, dest, date_from, date_to, date_ret_from, date_ret_to, adults=2, children=2):
    """Build AZair search URL for manual opening."""
    az_origin = AZAIR_AIRPORT_MAP.get(origin, origin)
    return (
        f"https://www.azair.eu/azfin.php"
        f"?searchtype=flexi&tp=0"
        f"&ismark=true&iswizz=true&isryan=true&iseazy=true&isvueling=true&istransavia=true"
        f"&srcAirport={az_origin}&dstAirport={dest}"
        f"&outDateFrom={date_from}&outDateTo={date_to}"
        f"&inDateFrom={date_ret_from}&inDateTo={date_ret_to}"
        f"&minDaysStay=12&maxDaysStay=14"
        f"&adults={adults}&children={children}&infants=0"
        f"&maxChng=1&currency=PLN&lang=pl"
    )


# ---------------------------------------------------------------------------
# SOURCE 10: eSky.pl URL builder
# ---------------------------------------------------------------------------
def build_esky_url(origin, dest, date_out, date_ret, adults=2, children=2):
    """Build eSky.pl search URL."""
    return (
        f"https://www.esky.pl/flights/select/roundtrip/{origin}/{dest}/{date_out}/{date_ret}"
        f"/{adults}A{children}C?currency=PLN"
    )


# ---------------------------------------------------------------------------
# SOURCE 11: Itaka.pl charter URL builder
# ---------------------------------------------------------------------------
def build_itaka_url(destination_keyword="fuerteventura"):
    return f"https://www.itaka.pl/wyniki-wyszukiwania/all/{destination_keyword}/"


# ---------------------------------------------------------------------------
# SOURCE 12: Wakacje.pl URL builder
# ---------------------------------------------------------------------------
def build_wakacje_url(destination_keyword="fuerteventura"):
    return f"https://www.wakacje.pl/wczasy/{destination_keyword}/"


# ---------------------------------------------------------------------------
# SOURCE 13: TUI.pl charter URL builder
# ---------------------------------------------------------------------------
def build_tui_url(destination_keyword="fuerteventura"):
    return f"https://www.tui.pl/wypoczynek/wyniki-wyszukiwania?q={destination_keyword}"


# ---------------------------------------------------------------------------
# HELPER: Combine Ryanair outbound + return into round-trip pairs
# ---------------------------------------------------------------------------
def combine_ryanair_roundtrips(all_results, adults, children):
    """Find cheapest outbound+return combos for each origin from Ryanair."""
    pax = adults + children
    outbound = {}  # origin -> list of fares
    returns = {}   # destination (=origin) -> list of fares

    for r in all_results:
        if r.get("source") != "Ryanair":
            continue
        if r.get("direction") == "outbound":
            outbound.setdefault(r["origin"], []).append(r)
        elif r.get("direction") == "return":
            returns.setdefault(r["destination"], []).append(r)

    combos = []
    for origin, out_fares in outbound.items():
        ret_fares = returns.get(origin, [])
        if not ret_fares:
            continue
        # Find cheapest return for this origin
        cheapest_ret = min(ret_fares, key=lambda x: x["price_per_person"])
        for out in out_fares:
            roundtrip_pp = out["price_per_person"] + cheapest_ret["price_per_person"]
            combos.append({
                "source": "Ryanair RT",
                "airline": "Ryanair",
                "origin": origin,
                "destination": out["destination"],
                "date": f"{out['date']} → {cheapest_ret['date']}",
                "price_per_person": round(roundtrip_pp, 2),
                "currency": "PLN",
                "direct": out["direct"] and cheapest_ret["direct"],
                "direction": "roundtrip",
                "link": out["link"],
                "notes": f"W obie strony, bez bagażu. Powrót {cheapest_ret['date']} ({cheapest_ret['price_per_person']} PLN/os)",
            })
    return combos


# ---------------------------------------------------------------------------
# AGGREGATOR
# ---------------------------------------------------------------------------
def search_all(params):
    """Run all searches in parallel and aggregate results."""
    origins = params.get("origins", ["WAW"])
    dest = params.get("destination", "FUE")
    date_from = params.get("date_from", "2027-01-29")
    date_to = params.get("date_to", "2027-02-03")
    date_ret_from = params.get("date_ret_from", "2027-02-10")
    date_ret_to = params.get("date_ret_to", "2027-02-14")
    adults = params.get("adults", 2)
    children = params.get("children", 2)
    max_stops = params.get("max_stops")
    max_price = params.get("max_price")
    dest_keyword = params.get("dest_keyword", "fuerteventura")

    all_results = []
    errors = []
    links = []  # External search links to open manually

    threads = []
    results_lock = threading.Lock()

    def collect(fn, *args):
        try:
            res = fn(*args)
            with results_lock:
                all_results.extend(res)
        except Exception as e:
            with results_lock:
                errors.append(str(e))

    # Ryanair (outbound + return) + Wizz Air + AZair for each origin
    for origin in origins:
        t1 = threading.Thread(target=collect, args=(search_ryanair, origin, dest, date_from, date_to))
        t1r = threading.Thread(target=collect, args=(search_ryanair_return, origin, dest, date_ret_from, date_ret_to))
        t2 = threading.Thread(target=collect, args=(search_wizzair, origin, dest, date_from, date_to))
        t3 = threading.Thread(target=collect, args=(search_azair, origin, dest, date_from, date_to, date_ret_from, date_ret_to, adults, children))
        threads.extend([t1, t1r, t2, t3])
        t1.start()
        t1r.start()
        t2.start()
        t3.start()

        # Build manual search links
        links.append({
            "source": "Google Flights",
            "origin": origin,
            "url": build_google_flights_url(origin, dest, date_from, date_ret_from, adults, children),
        })
        links.append({
            "source": "Kiwi.com",
            "origin": origin,
            "url": build_kiwi_url(
                POLISH_AIRPORTS.get(origin, origin).lower().replace(" ", "-") + "-polska",
                dest, date_from, f"{date_ret_from}_{date_ret_to}", adults, children, max_stops
            ),
        })
        links.append({
            "source": "Skyscanner",
            "origin": origin,
            "url": build_skyscanner_url(origin, dest, date_from, date_ret_from, adults, children),
        })
        links.append({
            "source": "Flippo.pl",
            "origin": origin,
            "url": build_flippo_url(origin, dest, date_from, date_ret_from, adults, children),
        })
        links.append({
            "source": "AZair",
            "origin": origin,
            "url": build_azair_url(origin, dest, date_from, date_to, date_ret_from, date_ret_to, adults, children),
        })
        links.append({
            "source": "eSky.pl",
            "origin": origin,
            "url": build_esky_url(origin, dest, date_from, date_ret_from, adults, children),
        })

    # SecretFlying error fares
    t_sf = threading.Thread(target=collect, args=(search_secretflying, dest_keyword))
    threads.append(t_sf)
    t_sf.start()

    # Rainbow Tours
    t_rw = threading.Thread(target=collect, args=(search_rainbow, dest_keyword))
    threads.append(t_rw)
    t_rw.start()

    # Charter links (not per-origin)
    links.append({"source": "Itaka", "origin": "PL", "url": build_itaka_url(dest_keyword)})
    links.append({"source": "TUI.pl", "origin": "PL", "url": build_tui_url(dest_keyword)})
    links.append({"source": "Wakacje.pl", "origin": "PL", "url": build_wakacje_url(dest_keyword)})

    for t in threads:
        t.join(timeout=25)

    # Combine Ryanair outbound + return into round-trip combos
    roundtrips = combine_ryanair_roundtrips(all_results, adults, children)
    all_results.extend(roundtrips)

    # Convert EUR prices to PLN for comparison
    pax = adults + children
    for r in all_results:
        pp = r.get("price_per_person", 0)
        currency = r.get("currency", "PLN")
        if currency == "EUR" and pp > 0:
            r["price_per_person_pln"] = round(pp * EUR_TO_PLN, 2)
            r["total_price_pln"] = round(pp * EUR_TO_PLN * pax, 2)
        else:
            r["price_per_person_pln"] = pp
            r["total_price_pln"] = round(pp * pax, 2)
        r["total_price"] = round(pp * pax, 2)
        r["pax"] = pax

    # Filter by max_stops
    if max_stops is not None:
        filtered = []
        for r in all_results:
            if r.get("direct") is True and max_stops == 0:
                filtered.append(r)
            elif r.get("direct") is None:
                filtered.append(r)
            elif max_stops > 0:
                filtered.append(r)
        all_results = filtered

    # Filter by max_price (total in PLN)
    if max_price:
        all_results = [r for r in all_results if r.get("total_price_pln", 0) <= max_price or r.get("total_price_pln", 0) == 0]

    # Sort by total_price_pln
    all_results.sort(key=lambda x: (x.get("total_price_pln", 0) if x.get("total_price_pln", 0) > 0 else 999999))

    # Count sources that returned data
    sources_hit = set(r["source"] for r in all_results)

    return {
        "results": all_results,
        "links": links,
        "errors": errors,
        "sources_hit": list(sources_hit),
        "search_params": params,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# FLASK ROUTES
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", airports=POLISH_AIRPORTS, dest_groups=DEST_GROUPS)


@app.route("/search", methods=["POST"])
def search():
    data = request.json or {}
    params = {
        "origins": data.get("origins", ["WAW", "WMI", "KRK", "GDN", "KTW", "POZ", "WRO", "BER"]),
        "destination": data.get("destination", "FUE"),
        "dest_keyword": data.get("dest_keyword", "fuerteventura"),
        "date_from": data.get("date_from", "2027-01-29"),
        "date_to": data.get("date_to", "2027-02-03"),
        "date_ret_from": data.get("date_ret_from", "2027-02-10"),
        "date_ret_to": data.get("date_ret_to", "2027-02-14"),
        "adults": int(data.get("adults", 2)),
        "children": int(data.get("children", 2)),
        "max_stops": int(data.get("max_stops")) if data.get("max_stops") not in (None, "", "any") else None,
        "max_price": int(data.get("max_price")) if data.get("max_price") else None,
    }
    result = search_all(params)
    return jsonify(result)


# ---------------------------------------------------------------------------
# SMART TRIP PLANNER — auto-discover cheapest route to any destination
# ---------------------------------------------------------------------------
# Map: destination keyword → airports, hubs, estimated RT prices per person in PLN from each hub
# Estimates based on typical low-season prices (budget airlines, 1 stop via hub)
# Weather data: destination keyword → avg temp per month (Jan=1..Dec=12), emoji, description
# Only destinations with warm months included
WARM_DESTINATIONS = {
    # Format: keyword: {temps: {month: avg_celsius}, emoji, desc, water_temp}
    "tajlandia":      {"temps": {1:28,2:29,3:30,4:31,5:30,6:29,7:29,8:29,9:28,10:28,11:28,12:27}, "emoji": "🌴", "desc": "Tajlandia", "water": 28},
    "bali":           {"temps": {1:27,2:27,3:27,4:28,5:28,6:27,7:26,8:26,9:27,10:28,11:28,12:27}, "emoji": "🏝", "desc": "Bali, Indonezja", "water": 28},
    "wietnam":        {"temps": {1:26,2:27,3:29,4:31,5:32,6:32,7:32,8:31,9:30,10:29,11:27,12:26}, "emoji": "🌺", "desc": "Wietnam", "water": 27},
    "malediwy":       {"temps": {1:29,2:29,3:30,4:31,5:30,6:29,7:29,8:29,9:29,10:29,11:29,12:29}, "emoji": "🐠", "desc": "Malediwy", "water": 29},
    "sri lanka":      {"temps": {1:27,2:28,3:29,4:30,5:29,6:28,7:28,8:28,9:28,10:28,11:27,12:27}, "emoji": "🫖", "desc": "Sri Lanka", "water": 28},
    "singapur":       {"temps": {1:27,2:27,3:28,4:28,5:28,6:28,7:28,8:28,9:28,10:28,11:27,12:27}, "emoji": "🏙", "desc": "Singapur", "water": 29},
    "filipiny":       {"temps": {1:27,2:28,3:29,4:31,5:31,6:30,7:29,8:29,9:29,10:29,11:28,12:27}, "emoji": "🏖", "desc": "Filipiny", "water": 28},
    "dubaj":          {"temps": {1:21,2:22,3:25,4:29,5:34,6:36,7:38,8:38,9:35,10:31,11:26,12:22}, "emoji": "🏜", "desc": "Dubaj", "water": 24},
    "egipt":          {"temps": {1:20,2:21,3:24,4:28,5:32,6:34,7:35,8:35,9:33,10:29,11:25,12:21}, "emoji": "🐫", "desc": "Egipt (Hurghada/Sharm)", "water": 24},
    "maroko":         {"temps": {1:18,2:20,3:22,4:23,5:26,6:29,7:33,8:33,9:30,10:26,11:22,12:18}, "emoji": "🕌", "desc": "Maroko", "water": 18},
    "zanzibar":       {"temps": {1:29,2:30,3:30,4:28,5:27,6:26,7:25,8:25,9:26,10:27,11:28,12:29}, "emoji": "🌊", "desc": "Zanzibar", "water": 28},
    "kenia":          {"temps": {1:26,2:27,3:27,4:25,5:24,6:22,7:21,8:22,9:24,10:25,11:24,12:25}, "emoji": "🦁", "desc": "Kenia", "water": 27},
    "mauritius":      {"temps": {1:27,2:27,3:27,4:26,5:24,6:22,7:21,8:21,9:22,10:23,11:25,12:26}, "emoji": "🌺", "desc": "Mauritius", "water": 27},
    "seszele":        {"temps": {1:28,2:28,3:29,4:29,5:28,6:27,7:26,8:26,9:27,10:28,11:28,12:28}, "emoji": "🐢", "desc": "Seszele", "water": 28},
    "cancun":         {"temps": {1:26,2:27,3:28,4:29,5:30,6:30,7:31,8:31,9:30,10:29,11:27,12:26}, "emoji": "🌮", "desc": "Cancun, Meksyk", "water": 27},
    "miami":          {"temps": {1:20,2:21,3:23,4:25,5:27,6:29,7:30,8:30,9:29,10:27,11:24,12:21}, "emoji": "🌴", "desc": "Miami, USA", "water": 24},
    # Europa ciepła
    "fuerteventura":  {"temps": {1:20,2:20,3:21,4:22,5:23,6:25,7:27,8:28,9:27,10:25,11:23,12:21}, "emoji": "🏖", "desc": "Fuerteventura", "water": 20},
    "teneryfa":       {"temps": {1:18,2:18,3:19,4:20,5:22,6:24,7:27,8:28,9:26,10:24,11:21,12:19}, "emoji": "🌋", "desc": "Teneryfa", "water": 20},
    "gran canaria":   {"temps": {1:19,2:19,3:20,4:21,5:22,6:24,7:27,8:28,9:26,10:24,11:22,12:20}, "emoji": "☀", "desc": "Gran Canaria", "water": 21},
    "lanzarote":      {"temps": {1:19,2:19,3:20,4:21,5:22,6:24,7:27,8:28,9:27,10:24,11:22,12:20}, "emoji": "🌵", "desc": "Lanzarote", "water": 20},
    "kreta":          {"temps": {1:12,2:13,3:14,4:17,5:21,6:26,7:28,8:28,9:25,10:21,11:17,12:14}, "emoji": "🏛", "desc": "Kreta, Grecja", "water": 22},
    "rodos":          {"temps": {1:12,2:13,3:15,4:18,5:22,6:27,7:29,8:29,9:27,10:22,11:17,12:14}, "emoji": "🏛", "desc": "Rodos, Grecja", "water": 23},
    "korfu":          {"temps": {1:10,2:11,3:13,4:16,5:21,6:25,7:28,8:28,9:24,10:20,11:15,12:12}, "emoji": "🫒", "desc": "Korfu, Grecja", "water": 22},
    "majorka":        {"temps": {1:11,2:11,3:13,4:16,5:20,6:24,7:27,8:27,9:24,10:20,11:15,12:12}, "emoji": "🏖", "desc": "Majorka", "water": 21},
    "algarve":        {"temps": {1:13,2:14,3:16,4:17,5:20,6:23,7:26,8:26,9:24,10:20,11:16,12:13}, "emoji": "🏄", "desc": "Algarve, Portugalia", "water": 19},
    "malaga":         {"temps": {1:13,2:14,3:16,4:17,5:20,6:24,7:28,8:28,9:25,10:21,11:16,12:13}, "emoji": "💃", "desc": "Malaga, Hiszpania", "water": 18},
    "antalya":        {"temps": {1:10,2:11,3:14,4:18,5:22,6:27,7:30,8:30,9:27,10:22,11:16,12:12}, "emoji": "🕌", "desc": "Antalya, Turcja", "water": 22},
    "sycylia":        {"temps": {1:11,2:11,3:13,4:16,5:20,6:24,7:28,8:28,9:25,10:21,11:16,12:12}, "emoji": "🍕", "desc": "Sycylia", "water": 20},
    "split":          {"temps": {1:8,2:9,3:12,4:16,5:20,6:24,7:27,8:27,9:23,10:18,11:13,12:9}, "emoji": "⛵", "desc": "Split, Chorwacja", "water": 21},
}

DESTINATION_HUB_MAP = {
    # AZJA
    "tajlandia": {"airports": ["BKK", "HKT", "CNX"], "hubs": ["HEL", "IST", "DOH", "AUH", "OSL", "ARN", "STN", "LGW", "MXP", "FCO", "BER"],
                  "est_prices": {"HEL": 1800, "IST": 1600, "DOH": 2200, "AUH": 2200, "OSL": 2000, "ARN": 1900, "STN": 1700, "LGW": 1700, "MXP": 1900, "FCO": 2000, "BER": 2100}},
    "thailand": {"airports": ["BKK", "HKT", "CNX"], "hubs": ["HEL", "IST", "DOH", "AUH", "OSL", "ARN", "STN", "LGW", "MXP", "FCO", "BER"],
                  "est_prices": {"HEL": 1800, "IST": 1600, "DOH": 2200, "AUH": 2200, "OSL": 2000, "ARN": 1900, "STN": 1700, "LGW": 1700, "MXP": 1900, "FCO": 2000, "BER": 2100}},
    "bangkok": {"airports": ["BKK"], "hubs": ["HEL", "IST", "DOH", "AUH", "OSL", "ARN", "STN", "LGW"],
                "est_prices": {"HEL": 1700, "IST": 1500, "DOH": 2100, "AUH": 2100, "OSL": 1900, "ARN": 1800, "STN": 1600, "LGW": 1600}},
    "phuket": {"airports": ["HKT"], "hubs": ["HEL", "IST", "DOH", "AUH", "OSL"],
               "est_prices": {"HEL": 1900, "IST": 1700, "DOH": 2300, "AUH": 2300, "OSL": 2100}},
    "bali": {"airports": ["DPS"], "hubs": ["IST", "DOH", "AUH", "SIN", "KUL", "HEL", "STN", "LGW"], "region": "azja_daleka"},
    "indonezja": {"airports": ["DPS", "CGK"], "hubs": ["IST", "DOH", "AUH", "SIN", "HEL", "STN"], "region": "azja_daleka"},
    "wietnam": {"airports": ["SGN", "HAN", "DAD"], "hubs": ["IST", "DOH", "HEL", "STN", "LGW"], "region": "azja_pd"},
    "vietnam": {"airports": ["SGN", "HAN", "DAD"], "hubs": ["IST", "DOH", "HEL", "STN", "LGW"], "region": "azja_pd"},
    "japonia": {"airports": ["NRT", "KIX", "HND"], "hubs": ["HEL", "IST", "DOH", "AUH", "ARN"], "region": "azja_daleka"},
    "japan": {"airports": ["NRT", "KIX", "HND"], "hubs": ["HEL", "IST", "DOH", "AUH", "ARN"], "region": "azja_daleka"},
    "korea": {"airports": ["ICN"], "hubs": ["HEL", "IST", "DOH", "ARN"], "region": "azja_daleka"},
    "malezja": {"airports": ["KUL", "LGK", "PEN"], "hubs": ["IST", "DOH", "AUH", "HEL", "STN"], "region": "azja_pd"},
    "malaysia": {"airports": ["KUL", "LGK", "PEN"], "hubs": ["IST", "DOH", "AUH", "HEL", "STN"], "region": "azja_pd"},
    "singapur": {"airports": ["SIN"], "hubs": ["HEL", "IST", "DOH", "AUH", "STN", "LGW"], "region": "azja_pd"},
    "singapore": {"airports": ["SIN"], "hubs": ["HEL", "IST", "DOH", "AUH", "STN", "LGW"], "region": "azja_pd"},
    "filipiny": {"airports": ["MNL", "CEB"], "hubs": ["IST", "DOH", "AUH", "HEL"], "region": "azja_daleka"},
    "philippines": {"airports": ["MNL", "CEB"], "hubs": ["IST", "DOH", "AUH", "HEL"], "region": "azja_daleka"},
    "indie": {"airports": ["DEL", "BOM", "GOI"], "hubs": ["IST", "DOH", "AUH", "STN", "LGW", "HEL"], "region": "azja_pd"},
    "india": {"airports": ["DEL", "BOM", "GOI"], "hubs": ["IST", "DOH", "AUH", "STN", "LGW", "HEL"], "region": "azja_pd"},
    "sri lanka": {"airports": ["CMB"], "hubs": ["IST", "DOH", "AUH", "HEL"], "region": "azja_pd"},
    "maldives": {"airports": ["MLE"], "hubs": ["IST", "DOH", "AUH", "HEL", "STN"], "region": "ocean_indyjski"},
    "malediwy": {"airports": ["MLE"], "hubs": ["IST", "DOH", "AUH", "HEL", "STN"], "region": "ocean_indyjski"},
    # AMERYKA
    "usa": {"airports": ["JFK", "LAX", "MIA", "ORD"], "hubs": ["STN", "LGW", "DUB", "KEF", "OSL", "CPH", "BER", "FCO"], "region": "ameryka_pn"},
    "nowy jork": {"airports": ["JFK", "EWR"], "hubs": ["STN", "LGW", "DUB", "KEF", "OSL", "BER"], "region": "ameryka_pn"},
    "new york": {"airports": ["JFK", "EWR"], "hubs": ["STN", "LGW", "DUB", "KEF", "OSL", "BER"], "region": "ameryka_pn"},
    "miami": {"airports": ["MIA"], "hubs": ["STN", "LGW", "DUB", "MAD", "BCN"], "region": "ameryka_pn"},
    "meksyk": {"airports": ["CUN", "MEX"], "hubs": ["MAD", "BCN", "STN", "LGW", "DUB"], "region": "ameryka_lac"},
    "mexico": {"airports": ["CUN", "MEX"], "hubs": ["MAD", "BCN", "STN", "LGW", "DUB"], "region": "ameryka_lac"},
    "cancun": {"airports": ["CUN"], "hubs": ["MAD", "BCN", "STN", "LGW", "DUB", "BER"], "region": "ameryka_lac"},
    "brazylia": {"airports": ["GRU", "GIG"], "hubs": ["LIS", "MAD", "BCN", "FCO"], "region": "ameryka_lac"},
    "brazil": {"airports": ["GRU", "GIG"], "hubs": ["LIS", "MAD", "BCN", "FCO"], "region": "ameryka_lac"},
    "kolumbia": {"airports": ["BOG", "CTG"], "hubs": ["MAD", "BCN", "LIS"], "region": "ameryka_lac"},
    "peru": {"airports": ["LIM"], "hubs": ["MAD", "BCN", "AMS", "LIS"], "region": "ameryka_lac"},
    # AFRYKA
    "zanzibar": {"airports": ["ZNZ"], "hubs": ["IST", "DOH", "AUH", "NBO"], "region": "afryka_wsch"},
    "kenia": {"airports": ["NBO", "MBA"], "hubs": ["IST", "DOH", "AUH", "STN", "LGW", "AMS"], "region": "afryka_wsch"},
    "kenya": {"airports": ["NBO", "MBA"], "hubs": ["IST", "DOH", "AUH", "STN", "LGW", "AMS"], "region": "afryka_wsch"},
    "tanzania": {"airports": ["DAR", "ZNZ"], "hubs": ["IST", "DOH", "AUH"], "region": "afryka_wsch"},
    "rpa": {"airports": ["CPT", "JNB"], "hubs": ["IST", "DOH", "AUH", "STN", "LGW", "AMS"], "region": "afryka_wsch"},
    "south africa": {"airports": ["CPT", "JNB"], "hubs": ["IST", "DOH", "AUH", "STN", "LGW", "AMS"], "region": "afryka_wsch"},
    "egipt": {"airports": ["HRG", "SSH", "CAI"], "hubs": ["IST", "BUD", "VIE", "ATH", "BER", "MXP"], "region": "afryka_pn"},
    "egypt": {"airports": ["HRG", "SSH", "CAI"], "hubs": ["IST", "BUD", "VIE", "ATH", "BER", "MXP"], "region": "afryka_pn"},
    "maroko": {"airports": ["RAK", "CMN", "AGA"], "hubs": ["BCN", "MAD", "LGW", "STN", "BGY", "CRL"], "region": "afryka_pn"},
    "morocco": {"airports": ["RAK", "CMN", "AGA"], "hubs": ["BCN", "MAD", "LGW", "STN", "BGY", "CRL"], "region": "afryka_pn"},
    "tunezja": {"airports": ["TUN", "NBE"], "hubs": ["FCO", "MXP", "LYS", "MRS"], "region": "afryka_pn"},
    # BLISKI WSCHÓD
    "dubaj": {"airports": ["DXB"], "hubs": ["IST", "VIE", "BUD", "STN", "LGW", "BER", "MXP"], "region": "bliski_wschod"},
    "dubai": {"airports": ["DXB"], "hubs": ["IST", "VIE", "BUD", "STN", "LGW", "BER", "MXP"], "region": "bliski_wschod"},
    "oman": {"airports": ["MCT"], "hubs": ["IST", "DOH", "AUH", "VIE"], "region": "bliski_wschod"},
    "jordania": {"airports": ["AMM", "AQJ"], "hubs": ["IST", "VIE", "BUD", "ATH"], "region": "bliski_wschod"},
    "mauritius": {"airports": ["MRU"], "hubs": ["IST", "DOH", "CDG", "LGW"], "region": "ocean_indyjski"},
    "seszele": {"airports": ["SEZ"], "hubs": ["IST", "DOH", "AUH", "CDG"], "region": "ocean_indyjski"},
    "seychelles": {"airports": ["SEZ"], "hubs": ["IST", "DOH", "AUH", "CDG"], "region": "ocean_indyjski"},
    "reunion": {"airports": ["RUN"], "hubs": ["CDG", "MRS"], "region": "ocean_indyjski"},
    "islandia": {"airports": ["KEF"], "hubs": ["STN", "LGW", "EDI", "CPH", "OSL", "BER"], "region": "europa"},
    "iceland": {"airports": ["KEF"], "hubs": ["STN", "LGW", "EDI", "CPH", "OSL", "BER"], "region": "europa"},
    # WYSPY KANARYJSKIE
    "fuerteventura": {"airports": ["FUE"], "hubs": ["STN", "BGY", "CRL", "MAN", "LBA", "SVQ", "PSA", "VIE", "BER", "CGN", "NRN", "MXP", "FCO", "MAD", "EDI", "DUB"], "region": "kanary"},
    "teneryfa": {"airports": ["TFS", "TFN"], "hubs": ["STN", "BGY", "CRL", "MAN", "LBA", "SVQ", "BER", "MXP", "FCO", "MAD", "DUB", "EDI"], "region": "kanary"},
    "tenerife": {"airports": ["TFS", "TFN"], "hubs": ["STN", "BGY", "CRL", "MAN", "LBA", "SVQ", "BER", "MXP", "FCO", "MAD", "DUB", "EDI"], "region": "kanary"},
    "gran canaria": {"airports": ["LPA"], "hubs": ["STN", "BGY", "CRL", "MAN", "SVQ", "BER", "MXP", "MAD", "DUB"], "region": "kanary"},
    "lanzarote": {"airports": ["ACE"], "hubs": ["STN", "BGY", "CRL", "MAN", "DUB", "MAD"], "region": "kanary"},
    "kanary": {"airports": ["FUE", "TFS", "LPA", "ACE", "SPC"], "hubs": ["STN", "BGY", "CRL", "MAN", "LBA", "SVQ", "PSA", "VIE", "BER", "MXP", "FCO", "MAD", "DUB", "EDI"], "region": "kanary"},
    "wyspy kanaryjskie": {"airports": ["FUE", "TFS", "LPA", "ACE", "SPC"], "hubs": ["STN", "BGY", "CRL", "MAN", "LBA", "SVQ", "PSA", "VIE", "BER", "MXP", "FCO", "MAD", "DUB", "EDI"], "region": "kanary"},
    "canary islands": {"airports": ["FUE", "TFS", "LPA", "ACE", "SPC"], "hubs": ["STN", "BGY", "CRL", "MAN", "LBA", "SVQ", "PSA", "VIE", "BER", "MXP", "FCO", "MAD", "DUB", "EDI"], "region": "kanary"},
    # BALEARY
    "majorka": {"airports": ["PMI"], "hubs": ["STN", "BGY", "CRL", "BER", "MXP", "DUB", "EDI", "MAN"], "region": "baleary"},
    "mallorca": {"airports": ["PMI"], "hubs": ["STN", "BGY", "CRL", "BER", "MXP", "DUB", "EDI", "MAN"], "region": "baleary"},
    "ibiza": {"airports": ["IBZ"], "hubs": ["STN", "BGY", "CRL", "BER", "MXP", "DUB", "MAN"], "region": "baleary"},
    "baleary": {"airports": ["PMI", "IBZ", "MAH"], "hubs": ["STN", "BGY", "CRL", "BER", "MXP", "DUB", "MAN"], "region": "baleary"},
    # GRECJA
    "grecja": {"airports": ["ATH", "SKG", "HER", "CHQ", "RHO", "CFU", "ZTH", "KGS"], "hubs": ["BGY", "MXP", "CRL", "BER", "VIE", "BUD", "STN"], "region": "grecja"},
    "greece": {"airports": ["ATH", "SKG", "HER", "CHQ", "RHO", "CFU", "ZTH", "KGS"], "hubs": ["BGY", "MXP", "CRL", "BER", "VIE", "BUD", "STN"], "region": "grecja"},
    "kreta": {"airports": ["HER", "CHQ"], "hubs": ["BGY", "MXP", "CRL", "BER", "VIE", "BUD", "STN", "ATH"], "region": "grecja"},
    "crete": {"airports": ["HER", "CHQ"], "hubs": ["BGY", "MXP", "CRL", "BER", "VIE", "BUD", "STN", "ATH"], "region": "grecja"},
    "rodos": {"airports": ["RHO"], "hubs": ["BGY", "CRL", "BER", "STN", "ATH"], "region": "grecja"},
    "korfu": {"airports": ["CFU"], "hubs": ["BGY", "CRL", "BER", "STN", "VIE"], "region": "grecja"},
    "zakynthos": {"airports": ["ZTH"], "hubs": ["BGY", "CRL", "BER", "STN"], "region": "grecja"},
    "santorini": {"airports": ["JTR"], "hubs": ["ATH", "BGY", "STN"], "region": "grecja"},
    "ateny": {"airports": ["ATH"], "hubs": ["BGY", "MXP", "CRL", "BER", "VIE", "BUD", "STN", "FCO"], "region": "grecja"},
    # HISZPANIA
    "barcelona": {"airports": ["BCN"], "hubs": ["BGY", "CRL", "STN", "BER", "MXP", "FCO"], "region": "hiszpania"},
    "malaga": {"airports": ["AGP"], "hubs": ["STN", "BGY", "CRL", "BER", "MAN", "DUB", "MXP"], "region": "hiszpania"},
    "alicante": {"airports": ["ALC"], "hubs": ["STN", "BGY", "CRL", "BER", "MAN", "DUB"], "region": "hiszpania"},
    "hiszpania": {"airports": ["BCN", "AGP", "ALC", "VLC", "MAD", "SVQ"], "hubs": ["STN", "BGY", "CRL", "BER", "MXP", "DUB"], "region": "hiszpania"},
    # PORTUGALIA
    "portugalia": {"airports": ["LIS", "OPO", "FAO", "FNC"], "hubs": ["STN", "BGY", "CRL", "BER", "MAD", "BCN"], "region": "portugalia"},
    "portugal": {"airports": ["LIS", "OPO", "FAO", "FNC"], "hubs": ["STN", "BGY", "CRL", "BER", "MAD", "BCN"], "region": "portugalia"},
    "lizbona": {"airports": ["LIS"], "hubs": ["STN", "BGY", "CRL", "BER", "MAD", "BCN", "FCO"], "region": "portugalia"},
    "madera": {"airports": ["FNC"], "hubs": ["LIS", "OPO", "STN", "BGY"], "region": "portugalia"},
    "algarve": {"airports": ["FAO"], "hubs": ["STN", "BGY", "CRL", "BER", "DUB", "MAN"], "region": "portugalia"},
    # WŁOCHY
    "sycylia": {"airports": ["CTA", "PMO"], "hubs": ["BGY", "MXP", "FCO", "CRL", "BER", "STN"], "region": "wlochy"},
    "sardynia": {"airports": ["CAG", "AHO", "OLB"], "hubs": ["BGY", "MXP", "FCO", "CRL", "BER"], "region": "wlochy"},
    # CHORWACJA
    "chorwacja": {"airports": ["SPU", "DBV", "ZAG"], "hubs": ["BGY", "CRL", "BER", "STN", "MXP"], "region": "chorwacja"},
    "croatia": {"airports": ["SPU", "DBV", "ZAG"], "hubs": ["BGY", "CRL", "BER", "STN", "MXP"], "region": "chorwacja"},
    "split": {"airports": ["SPU"], "hubs": ["BGY", "CRL", "BER", "STN"], "region": "chorwacja"},
    "dubrownik": {"airports": ["DBV"], "hubs": ["BGY", "CRL", "BER", "STN"], "region": "chorwacja"},
    # TURCJA
    "turcja": {"airports": ["AYT", "DLM", "SAW", "IST"], "hubs": ["BGY", "CRL", "BER", "STN", "VIE", "BUD"], "region": "turcja"},
    "turkey": {"airports": ["AYT", "DLM", "SAW", "IST"], "hubs": ["BGY", "CRL", "BER", "STN", "VIE", "BUD"], "region": "turcja"},
    "antalya": {"airports": ["AYT"], "hubs": ["BGY", "CRL", "BER", "STN", "VIE", "BUD", "MXP"], "region": "turcja"},
}

# Estimated RT prices per person (PLN) from hub to destination REGION
# These are approximate based on typical budget airline / good deal prices
EST_HUB_PRICES = {
    "azja_pd": {"HEL": 1800, "IST": 1500, "DOH": 2000, "AUH": 2000, "OSL": 2000, "ARN": 1900, "STN": 1700, "LGW": 1700, "MXP": 1900, "FCO": 2000, "BER": 2100, "SIN": 800, "KUL": 800},
    "azja_daleka": {"HEL": 2200, "IST": 2000, "DOH": 2400, "AUH": 2400, "OSL": 2200, "ARN": 2100, "STN": 2000, "LGW": 2000, "MXP": 2200, "FCO": 2300, "BER": 2400},
    "ameryka_pn": {"STN": 1500, "LGW": 1500, "DUB": 1400, "KEF": 1200, "OSL": 1600, "CPH": 1600, "BER": 1800, "FCO": 1700, "MAD": 1600, "BCN": 1600},
    "ameryka_lac": {"MAD": 1800, "BCN": 1900, "LIS": 1700, "STN": 2000, "LGW": 2000, "DUB": 2100, "FCO": 2000},
    "afryka_wsch": {"IST": 1400, "DOH": 1600, "AUH": 1600, "STN": 1800, "LGW": 1800, "AMS": 1700, "NBO": 400},
    "afryka_pn": {"BCN": 400, "MAD": 500, "LGW": 600, "STN": 600, "BGY": 500, "CRL": 500, "IST": 500, "BUD": 600, "VIE": 600, "ATH": 500, "BER": 600, "MXP": 500, "FCO": 500, "MRS": 400, "LYS": 500},
    "bliski_wschod": {"IST": 600, "VIE": 800, "BUD": 900, "STN": 1000, "LGW": 1000, "BER": 1000, "MXP": 900, "DOH": 500, "AUH": 500, "ATH": 700},
    "ocean_indyjski": {"IST": 2200, "DOH": 2000, "AUH": 2000, "CDG": 2500, "HEL": 2500, "STN": 2400, "LGW": 2400},
    "europa": {"STN": 300, "LGW": 300, "EDI": 400, "CPH": 400, "OSL": 400, "BER": 350},
    "kanary": {"STN": 250, "BGY": 200, "CRL": 250, "MAN": 300, "LBA": 250, "SVQ": 150, "PSA": 200, "VIE": 300, "BER": 250, "CGN": 200, "NRN": 200, "MXP": 200, "FCO": 250, "MAD": 150, "DUB": 300, "EDI": 300},
    "baleary": {"STN": 200, "BGY": 150, "CRL": 200, "BER": 200, "MXP": 150, "DUB": 250, "EDI": 250, "MAN": 200},
    "grecja": {"BGY": 150, "MXP": 150, "CRL": 200, "BER": 200, "VIE": 150, "BUD": 120, "STN": 250, "ATH": 80, "FCO": 120},
    "hiszpania": {"STN": 150, "BGY": 120, "CRL": 150, "BER": 150, "MXP": 120, "DUB": 200, "FCO": 120, "MAN": 150},
    "portugalia": {"STN": 200, "BGY": 180, "CRL": 200, "BER": 200, "MAD": 100, "BCN": 120, "FCO": 180, "LIS": 80, "OPO": 80},
    "wlochy": {"BGY": 80, "MXP": 80, "FCO": 80, "CRL": 150, "BER": 150, "STN": 180},
    "chorwacja": {"BGY": 100, "CRL": 150, "BER": 120, "STN": 180, "MXP": 120, "VIE": 80},
    "turcja": {"BGY": 150, "CRL": 200, "BER": 180, "STN": 200, "VIE": 130, "BUD": 100, "MXP": 160},
}

# Default region for destinations without explicit region
DEFAULT_EST_PRICE = 2000  # PLN per person RT

# Polish airports to search FROM
POLISH_ORIGINS = ["WAW", "WMI", "KRK", "GDN", "KTW", "POZ", "WRO"]


def smart_search(params):
    """
    Smart Trip Planner: user enters destination keyword, system finds
    cheapest route from Poland via European hubs.
    """
    dest_keyword = params["destination"].lower().strip()
    date_out_from = params["date_out_from"]
    date_out_to = params["date_out_to"]
    date_ret_from = params["date_ret_from"]
    date_ret_to = params["date_ret_to"]
    adults = params.get("adults", 2)
    children = params.get("children", 2)
    pax = adults + children

    # Resolve destination to airports + hubs
    dest_info = DESTINATION_HUB_MAP.get(dest_keyword)
    if not dest_info:
        # Try partial match
        for key, val in DESTINATION_HUB_MAP.items():
            if dest_keyword in key or key in dest_keyword:
                dest_info = val
                break
    if not dest_info:
        return {"error": f"Nie znaleziono destynacji '{dest_keyword}'. Spróbuj po angielsku lub użyj kodu IATA.", "routes": [], "links": []}

    dest_airports = dest_info["airports"]
    best_hubs = dest_info["hubs"]
    max_stops_total = params.get("max_stops")
    max_budget = params.get("max_budget")

    log.info(f"Smart search: '{dest_keyword}' → airports={dest_airports}, hubs={best_hubs}, max_stops={max_stops_total}")

    # Special case: max_stops=0 means DIRECT from Poland — no hubs, just Kayak search
    if max_stops_total == 0:
        log.info("Smart search: Direct mode — searching Kayak for direct flights from PL")
        routes = []
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import subprocess, json as json_mod

        def fetch_direct(origin, dest_ap):
            price, url = fetch_kayak_price(origin, dest_ap, date_out_from, date_ret_from, 1, 0)
            return origin, dest_ap, price, url

        scraper_path_d = os.path.join(os.path.dirname(__file__), "kayak_scraper.py")
        def fetch_price_subprocess_direct(origin, dest_ap):
            url = f"https://www.kayak.pl/flights/{origin}-{dest_ap}/{date_out_from}/{date_ret_from}?sort=price_a&currency=PLN&fs=stops=0"
            try:
                result = subprocess.run(["python3", scraper_path_d, url], capture_output=True, text=True, timeout=45)
                if result.stdout.strip():
                    data = json_mod.loads(result.stdout.strip())
                    return data.get("price"), data.get("url")
            except Exception as e:
                log.error(f"Direct Kayak error {origin}→{dest_ap}: {e}")
            return None, url

        # Search top 5 Polish airports × first destination airport
        primary_dest = dest_airports[0]
        origins_to_check = POLISH_ORIGINS[:5]

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for origin in origins_to_check:
                f = executor.submit(fetch_price_subprocess_direct, origin, primary_dest)
                futures[f] = origin
            try:
              for future in as_completed(futures, timeout=60):
                origin = futures[future]
                try:
                    price, kayak_url = future.result(timeout=5)
                    if price:
                        total = price * pax
                        if not max_budget or total <= max_budget:
                            try:
                                trip_days = (datetime.strptime(date_ret_from, "%Y-%m-%d") - datetime.strptime(date_out_from, "%Y-%m-%d")).days
                            except:
                                trip_days = 0
                            for dest_ap in dest_airports:
                                routes.append({
                                    "hub": origin,
                                    "dest_airport": dest_ap,
                                    "pl_to_hub": {"origin": origin, "price_pp": 0, "date": date_out_from, "book_link": ""},
                                    "hub_to_dest": {"est_price_pp": price, "est_total": price * pax},
                                    "hub_to_pl": {"origin": origin, "dest": origin, "price_pp": 0, "date": date_ret_from, "book_link": ""},
                                    "date_out": date_out_from,
                                    "date_ret": date_ret_from,
                                    "trip_days": trip_days,
                                    "europe_total_pp": 0,
                                    "europe_total": 0,
                                    "longhaul_pp": price,
                                    "longhaul_total": price * pax,
                                    "price_source": "kayak",
                                    "grand_total_pp": price,
                                    "grand_total": price * pax,
                                    "search_links": {
                                        "google_flights": build_google_flights_url(origin, dest_ap, date_out_from, date_ret_from, adults, children),
                                        "kiwi": f"https://www.kiwi.com/pl/search/tiles/{origin.lower()}/{dest_ap.lower()}/{date_out_from}/{date_ret_from}?adults={adults}&children={children}&sortBy=price",
                                        "skyscanner": build_skyscanner_url(origin, dest_ap, date_out_from, date_ret_from, adults, children),
                                        "kiwi_full": "",
                                        "kayak": kayak_url,
                                    },
                                })
                        log.info(f"Direct price {origin}→{primary_dest}: {price} PLN/os")
                except Exception as e:
                    log.error(f"Direct future error {origin}: {e}")
            except TimeoutError:
                log.warning("Direct Kayak scraping timed out — using partial results")

        routes.sort(key=lambda x: x["grand_total"])
        return {
            "routes": routes[:50],
            "direct_links": [],
            "dest_airports": dest_airports,
            "hubs_searched": origins_to_check,
            "hub_fares_found": len(routes),
            "params": params,
            "timestamp": datetime.now().isoformat(),
        }

    # Normal hub-based search
    # Step 1: Find cheapest flights from Polish cities to each hub
    # Sources: Ryanair API + Wizz Air API + Kayak scraping (all airlines)
    results_lock = threading.Lock()
    hub_fares = []  # Combined from all sources
    threads = []

    # 1a: Ryanair API (fast, reliable)
    def fetch_ryanair_hub(origin, hub):
        fares = ryanair_cheapest_fares(origin, hub, date_out_from, date_out_to)
        ret_fares = ryanair_cheapest_fares(hub, origin, date_ret_from, date_ret_to)
        with results_lock:
            for f in fares:
                hub_fares.append({**f, "direction": "outbound", "pl_origin": origin, "airline": "Ryanair"})
            for f in ret_fares:
                hub_fares.append({**f, "direction": "return", "pl_origin": f["dest"], "airline": "Ryanair"})

    # 1b: Wizz Air API
    def fetch_wizzair_hub(origin, hub):
        try:
            meta_url = "https://wizzair.com/static_fe/metadata.json"
            meta = requests.get(meta_url, headers=HEADERS, timeout=8)
            if meta.status_code != 200:
                return
            api_url = meta.json().get("apiUrl", "")
            if not api_url:
                return
            # Outbound
            for direction, dep, arr, date_from, date_to in [
                ("outbound", origin, hub, date_out_from, date_out_to),
                ("return", hub, origin, date_ret_from, date_ret_to),
            ]:
                search_url = f"{api_url}/search/timetable"
                payload = {"flightList": [{"departureStation": dep, "arrivalStation": arr, "from": date_from, "to": date_to}], "priceType": "regular", "adultCount": 1, "childCount": 0}
                r = requests.post(search_url, json=payload, headers={**HEADERS, "Content-Type": "application/json"}, timeout=10)
                if r.status_code == 200:
                    for fl in r.json().get("outboundFlights", []):
                        dep_date = fl.get("departureDateTime", "")[:10]
                        price = fl.get("priceType", {}).get("regular", {}).get("amount", 0)
                        if price > 0:
                            with results_lock:
                                hub_fares.append({"origin": dep, "dest": arr, "date": dep_date, "price": price, "currency": "PLN", "direction": direction, "pl_origin": origin if direction == "outbound" else arr, "airline": "Wizz Air"})
        except Exception as e:
            log.debug(f"Wizz Air {origin}->{hub}: {e}")

    for origin in POLISH_ORIGINS:
        for hub in best_hubs:
            t1 = threading.Thread(target=fetch_ryanair_hub, args=(origin, hub))
            t2 = threading.Thread(target=fetch_wizzair_hub, args=(origin, hub))
            threads.extend([t1, t2])
            t1.start()
            t2.start()

    for t in threads:
        t.join(timeout=30)

    log.info(f"Smart search: Got {len(hub_fares)} hub fares from Ryanair+Wizz Air")

    # 1c: Kayak scraping for PL→Hub (top 3 Polish airports × top 5 hubs)
    # This catches LOT, easyJet, Norwegian, Lufthansa, Vueling, etc.
    import subprocess, json as json_mod
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Find which hubs DON'T have Ryanair/Wizz fares — scrape those from Kayak
    hubs_with_fares = set()
    for f in hub_fares:
        hub = f["dest"] if f["direction"] == "outbound" else f["origin"]
        hubs_with_fares.add(hub)
    hubs_without_fares = [h for h in best_hubs if h not in hubs_with_fares][:3]  # Max 3 hubs to limit scraping time

    # 1c: Also search full trips PL→Destination on Kayak (catches all airlines with optimal routing)
    # This adds direct PL→Dest routes that don't need a hub
    if hubs_without_fares:
        log.info(f"Smart search: Hubs without Ryanair/Wizz: {hubs_without_fares} — Kayak full-trip search will cover them")

    # Search WAW/WMI → primary_dest directly on Kayak (top 2 PL airports)
    import subprocess, json as json_mod
    from concurrent.futures import ThreadPoolExecutor, as_completed
    direct_links_kayak = []

    for pl_origin in POLISH_ORIGINS[:2]:
        for dest_ap in dest_airports[:1]:
            kayak_full_url = f"https://www.kayak.pl/flights/{pl_origin}-{dest_ap}/{date_out_from}/{date_ret_from}?sort=price_a&currency=PLN"
            direct_links_kayak.append({
                "source": "Kayak",
                "label": f"{pl_origin} → {dest_ap} (pełna trasa)",
                "url": kayak_full_url,
            })

    log.info(f"Smart search: Total {len(hub_fares)} hub fares")

    # Step 1d: Kayak full-trip PL→Dest (parallel subprocess scraping)
    # This finds the absolute cheapest way from Poland to destination on ALL airlines
    primary_dest = dest_airports[0]
    full_trip_prices = {}  # pl_origin -> {price, url}

    scraper_path_ft = os.path.join(os.path.dirname(__file__), "kayak_scraper.py")

    def fetch_full_trip_subprocess(origin, dest_ap, d_out, d_ret, max_st):
        stops = f"&fs=stops={max_st}" if max_st is not None else ""
        url = f"https://www.kayak.pl/flights/{origin}-{dest_ap}/{d_out}/{d_ret}?sort=price_a&currency=PLN{stops}"
        try:
            result = subprocess.run(["python3", scraper_path_ft, url], capture_output=True, text=True, timeout=45)
            if result.stdout.strip():
                return json_mod.loads(result.stdout.strip())
        except Exception as e:
            log.error(f"Full trip Kayak error {origin}→{dest_ap}: {e}")
        return {"price": None, "url": url}

    max_stops_total = params.get("max_stops")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for pl_origin in POLISH_ORIGINS[:3]:  # WAW, WMI, KRK
            f = executor.submit(fetch_full_trip_subprocess, pl_origin, primary_dest, date_out_from, date_ret_from, max_stops_total)
            futures[f] = pl_origin
        try:
            for future in as_completed(futures, timeout=60):
                pl_origin = futures[future]
                try:
                    data = future.result(timeout=5)
                    if data.get("price"):
                        full_trip_prices[pl_origin] = {"price_pp": data["price"], "url": data["url"]}
                        log.info(f"Kayak full trip {pl_origin}→{primary_dest}: {data['price']} PLN/os RT")
                except Exception as e:
                    log.error(f"Full trip future error {pl_origin}: {e}")
        except TimeoutError:
            log.warning("Full trip Kayak scraping timed out — using partial results")

    # Add full-trip routes (no hub, direct Kayak routing)
    for pl_origin, data in full_trip_prices.items():
        try:
            trip_days = (datetime.strptime(date_ret_from, "%Y-%m-%d") - datetime.strptime(date_out_from, "%Y-%m-%d")).days
        except:
            trip_days = 0
        for dest_ap in dest_airports:
            hub_fares.append({
                "origin": pl_origin, "dest": dest_ap,
                "date": date_out_from, "price": data["price_pp"],
                "currency": "PLN", "direction": "full_trip",
                "pl_origin": pl_origin, "airline": "Kayak (pełna trasa)",
            })

    log.info(f"Smart search: {len(full_trip_prices)} full trip prices from Kayak")

    # Step 1e: SecretFlying error fares
    secret_deals = search_secretflying(dest_keyword)
    log.info(f"Smart search: {len(secret_deals)} SecretFlying deals found")

    # Initialize routes and links
    routes = []
    direct_links = list(direct_links_kayak)  # Start with Kayak full-trip links

    # Step 2: Add full-trip Kayak results as direct routes
    for pl_origin, data in full_trip_prices.items():
        try:
            trip_days = (datetime.strptime(date_ret_from, "%Y-%m-%d") - datetime.strptime(date_out_from, "%Y-%m-%d")).days
        except:
            trip_days = 0
        for dest_ap in dest_airports:
            routes.append({
                "hub": pl_origin,
                "dest_airport": dest_ap,
                "pl_to_hub": {"origin": pl_origin, "price_pp": 0, "date": date_out_from, "airline": "Kayak (pełna trasa)", "book_link": data["url"]},
                "hub_to_dest": {"est_price_pp": data["price_pp"], "est_total": data["price_pp"] * pax},
                "hub_to_pl": {"origin": pl_origin, "dest": pl_origin, "price_pp": 0, "date": date_ret_from, "airline": "Kayak (pełna trasa)", "book_link": data["url"]},
                "date_out": date_out_from,
                "date_ret": date_ret_from,
                "trip_days": trip_days,
                "europe_total_pp": 0,
                "europe_total": 0,
                "longhaul_pp": data["price_pp"],
                "longhaul_total": data["price_pp"] * pax,
                "price_source": "kayak",
                "grand_total_pp": data["price_pp"],
                "grand_total": data["price_pp"] * pax,
                "search_links": {
                    "google_flights": build_google_flights_url(pl_origin, dest_ap, date_out_from, date_ret_from, adults, children),
                    "kiwi": f"https://www.kiwi.com/pl/search/tiles/{pl_origin.lower()}/{dest_ap.lower()}/{date_out_from}/{date_ret_from}?adults={adults}&children={children}&sortBy=price",
                    "skyscanner": build_skyscanner_url(pl_origin, dest_ap, date_out_from, date_ret_from, adults, children),
                    "kiwi_full": "",
                    "kayak": data["url"],
                },
            })

    # Step 3: Group hub-based fares
    hub_prices = {}
    for fare in hub_fares:
        if fare.get("direction") == "full_trip":
            continue  # Already handled above
        hub = fare["dest"] if fare["direction"] == "outbound" else fare["origin"]
        if hub not in hub_prices:
            hub_prices[hub] = {"out": [], "ret": []}
        if fare["direction"] == "outbound":
            hub_prices[hub]["out"].append(fare)
        else:
            hub_prices[hub]["ret"].append(fare)

    # Step 3: Get estimated long-haul prices (fallback)
    region = dest_info.get("region", "")
    est_prices_map = dest_info.get("est_prices", {})
    if not est_prices_map and region:
        est_prices_map = EST_HUB_PRICES.get(region, {})

    # Step 3b: Fetch REAL prices from Kayak for top hubs
    # max_stops is for the ENTIRE one-way journey (PL→hub = 1 segment, so longhaul gets max_stops - 1)
    max_stops_total = params.get("max_stops")  # e.g. 2 = max 2 stops total one-way
    if max_stops_total is not None:
        # PL→hub is 1 flight (0 stops), so longhaul can have max_stops_total - 0 stops
        # But the PL→hub IS a stop/connection, so longhaul gets max_stops_total - 1
        max_stops_longhaul = max(0, max_stops_total - 1)
    else:
        max_stops_longhaul = None
    # Sort hubs by cheapest Europe leg first
    hub_ranking = []
    for hub, data in hub_prices.items():
        if not data["out"] or not data["ret"]:
            continue
        cheapest_out = min(data["out"], key=lambda x: x["price"])
        cheapest_ret = min(data["ret"], key=lambda x: x["price"])
        hub_ranking.append((hub, cheapest_out["price"] + cheapest_ret["price"]))
    hub_ranking.sort(key=lambda x: x[1])

    # Fetch real prices for top 5 cheapest hubs (to limit scraping time)
    real_prices = {}
    top_hubs = [h[0] for h in hub_ranking[:5]]
    primary_dest = dest_airports[0]  # Use first destination airport

    log.info(f"Smart search: Fetching real Kayak prices for {top_hubs} → {primary_dest}")

    # Playwright doesn't support multi-threading well, so fetch sequentially
    # Use subprocess to avoid thread issues
    import subprocess, json as json_mod

    scraper_path = os.path.join(os.path.dirname(__file__), "kayak_scraper.py")

    def fetch_price_subprocess(hub, dest_ap, d_out, d_ret, max_st):
        """Run Kayak scraper in subprocess."""
        stops = f"&fs=stops={max_st}" if max_st is not None else ""
        url = f"https://www.kayak.pl/flights/{hub}-{dest_ap}/{d_out}/{d_ret}?sort=price_a&currency=PLN{stops}"
        try:
            result = subprocess.run(
                ["python3", scraper_path, url],
                capture_output=True, text=True, timeout=45
            )
            if result.stdout.strip():
                data = json_mod.loads(result.stdout.strip())
                return data.get("price"), data.get("url")
        except Exception as e:
            log.error(f"Kayak subprocess error {hub}→{dest_ap}: {e}")
        return None, f"https://www.kayak.pl/flights/{hub}-{dest_ap}/{d_out}/{d_ret}?sort=price_a&currency=PLN"

    # Fetch prices in parallel using subprocesses (each has own Playwright instance)
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for hub in top_hubs:
            f = executor.submit(fetch_price_subprocess, hub, primary_dest, date_out_from, date_ret_from, max_stops_longhaul)
            futures[f] = hub
        try:
            for future in as_completed(futures, timeout=60):
                hub = futures[future]
                try:
                    price, kayak_url = future.result(timeout=5)
                    if price:
                        real_prices[hub] = {"price_pp": price, "kayak_url": kayak_url}
                        log.info(f"Kayak price {hub}→{primary_dest}: {price} PLN")
                except Exception as e:
                    log.error(f"Kayak future error {hub}: {e}")
        except TimeoutError:
            log.warning("Kayak longhaul scraping timed out — using partial results")

    log.info(f"Smart search: Got real prices for {len(real_prices)} hubs: {real_prices}")

    # Step 4: Build route options with estimated total costs (add to existing routes from full-trip)
    for hub, data in hub_prices.items():
        if not data["out"] or not data["ret"]:
            continue
        cheapest_out = min(data["out"], key=lambda x: x["price"])
        cheapest_ret = min(data["ret"], key=lambda x: x["price"])
        europe_total_pp = cheapest_out["price"] + cheapest_ret["price"]
        europe_total = europe_total_pp * pax

        # Real or estimated long-haul price
        real = real_prices.get(hub)
        if real:
            est_longhaul_pp = real["price_pp"]
            price_source = "kayak"
            kayak_url = real["kayak_url"]
        else:
            est_longhaul_pp = est_prices_map.get(hub, DEFAULT_EST_PRICE)
            price_source = "estimate"
            kayak_url = None

        for dest_ap in dest_airports:
            # Total estimated cost
            est_total_pp = europe_total_pp + est_longhaul_pp
            est_total = est_total_pp * pax

            # Build booking/search links
            gf_link = build_google_flights_url(hub, dest_ap, date_out_from, date_ret_from, adults, children)
            kiwi_link = f"https://www.kiwi.com/pl/search/tiles/{hub.lower()}/{dest_ap.lower()}/{date_out_from}/{date_ret_from}_{date_ret_to}?adults={adults}&children={children}&sortBy=price"

            # Deep booking link — full multi-city trip via Kiwi
            pl_origin = cheapest_out.get("pl_origin", cheapest_out["origin"])
            pl_return = cheapest_ret.get("pl_origin", cheapest_ret["dest"])
            kiwi_full_link = (
                f"https://www.kiwi.com/pl/search/tiles/{pl_origin.lower()}/{dest_ap.lower()}"
                f"/{date_out_from}/{date_ret_from}_{date_ret_to}"
                f"?adults={adults}&children={children}&sortBy=price"
            )

            routes.append({
                "hub": hub,
                "dest_airport": dest_ap,
                "pl_to_hub": {
                    "origin": pl_origin,
                    "price_pp": cheapest_out["price"],
                    "date": cheapest_out["date"],
                    "airline": cheapest_out.get("airline", "Ryanair"),
                    "book_link": (
                        f"https://www.ryanair.com/pl/pl/trip/flights/select?adults={adults}&teens=0&children={children}&infants=0&dateOut={cheapest_out['date']}&originIata={pl_origin}&destinationIata={hub}"
                        if cheapest_out.get("airline") == "Ryanair"
                        else f"https://www.kayak.pl/flights/{pl_origin}-{hub}/{cheapest_out['date']}?sort=price_a&currency=PLN&adults={adults}&children={children}"
                    ),
                },
                "hub_to_dest": {
                    "est_price_pp": est_longhaul_pp,
                    "est_total": est_longhaul_pp * pax,
                },
                "hub_to_pl": {
                    "origin": hub,
                    "dest": pl_return,
                    "price_pp": cheapest_ret["price"],
                    "date": cheapest_ret["date"],
                    "airline": cheapest_ret.get("airline", "Ryanair"),
                    "book_link": (
                        f"https://www.ryanair.com/pl/pl/trip/flights/select?adults={adults}&teens=0&children={children}&infants=0&dateOut={cheapest_ret['date']}&originIata={hub}&destinationIata={pl_return}"
                        if cheapest_ret.get("airline") == "Ryanair"
                        else f"https://www.kayak.pl/flights/{hub}-{pl_return}/{cheapest_ret['date']}?sort=price_a&currency=PLN&adults={adults}&children={children}"
                    ),
                },
                "date_out": cheapest_out["date"],
                "date_ret": cheapest_ret["date"],
                "trip_days": (datetime.strptime(cheapest_ret["date"], "%Y-%m-%d") - datetime.strptime(cheapest_out["date"], "%Y-%m-%d")).days,
                "europe_total_pp": round(europe_total_pp, 2),
                "europe_total": round(europe_total, 2),
                "longhaul_pp": est_longhaul_pp,
                "longhaul_total": est_longhaul_pp * pax,
                "price_source": price_source,
                "grand_total_pp": round(est_total_pp, 2),
                "grand_total": round(est_total, 2),
                "search_links": {
                    "google_flights": gf_link,
                    "kiwi": kiwi_link,
                    "skyscanner": build_skyscanner_url(hub, dest_ap, date_out_from, date_ret_from, adults, children),
                    "kiwi_full": kiwi_full_link,
                    "kayak": kayak_url or f"https://www.kayak.pl/flights/{hub}-{dest_ap}/{date_out_from}/{date_ret_from}?sort=price_a&currency=PLN",
                },
            })

    # Filter by budget
    max_budget = params.get("max_budget")
    if max_budget:
        routes = [r for r in routes if r["grand_total"] <= max_budget]

    # Sort by grand total (real prices first, then estimates)
    routes.sort(key=lambda x: (0 if x["price_source"] == "kayak" else 1, x["grand_total"]))

    # Also build direct search links from Poland
    for origin in POLISH_ORIGINS:
        for dest_ap in dest_airports:
            direct_links.append({
                "source": "Google Flights",
                "label": f"{origin} → {dest_ap}",
                "url": build_google_flights_url(origin, dest_ap, date_out_from, date_ret_from, adults, children),
            })

    # Collect sources used
    sources_used = set()
    for f in hub_fares:
        sources_used.add(f.get("airline", "Unknown"))

    return {
        "routes": routes[:50],
        "direct_links": direct_links,
        "secret_deals": secret_deals,
        "dest_airports": dest_airports,
        "hubs_searched": best_hubs,
        "hub_fares_found": len(hub_fares),
        "sources_used": list(sources_used),
        "params": params,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# MULTI-CITY TRIP BUILDER
# ---------------------------------------------------------------------------
CHEAP_HUBS = [
    "STN", "LTN", "BGY", "MXP", "BCN", "GRO", "BUD", "VIE",
    "OSL", "TRF", "CPH", "BLL", "DUB", "EDI", "BRU", "CRL",
    "CGN", "NRN", "HAM", "FRA", "HHN", "MUC", "FMM", "DUS",
    "MAD", "AGP", "ALC", "VLC", "SVQ", "PMI", "LIS", "OPO",
    "FCO", "CIA", "NAP", "PSA", "BLQ", "TSF", "ATH", "SKG",
    "SOF", "OTP", "CLJ", "BTS", "PRG", "EIN", "RIX", "VNO",
    "TLL", "HEL", "ARN", "NYO", "GOT", "BVA", "ORY", "MRS",
]


def ryanair_get_routes(airport):
    """Get all Ryanair routes from an airport."""
    url = f"https://www.ryanair.com/api/views/locate/searchWidget/routes/pl/airport/{airport}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            routes = [route.get("arrivalAirport", {}).get("code") for route in data if route.get("arrivalAirport")]
            return [r for r in routes if r]  # filter None
        return []
    except Exception:
        return []


def ryanair_cheapest_fares(origin, dest, date_from, date_to):
    """Get cheapest Ryanair fare between two airports in date range."""
    url = "https://www.ryanair.com/api/farfnd/v4/oneWayFares"
    params = {
        "departureAirportIataCode": origin,
        "arrivalAirportIataCode": dest,
        "language": "pl",
        "market": "pl-pl",
        "outboundDepartureDateFrom": date_from,
        "outboundDepartureDateTo": date_to,
        "currency": "PLN",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            fares = []
            for fare in data.get("fares", []):
                out = fare.get("outbound", {})
                price = out.get("price", {})
                dep_date = out.get("departureDate", "")[:10]
                fares.append({
                    "origin": origin,
                    "dest": dest,
                    "date": dep_date,
                    "price": price.get("value", 9999),
                    "currency": price.get("currencyCode", "PLN"),
                })
            return fares
    except Exception:
        pass
    return []


def find_multi_city_trips(params):
    """
    Find cheapest multi-segment trips: Origin → Hub(s) → Destination,
    and Destination → Hub(s) → Origin.

    Builds a graph of cheap flights and finds optimal combos.
    """
    origin = params["origin"]  # e.g. "WAW"
    destination = params["destination"]  # e.g. "FUE"
    date_out_from = params["date_out_from"]
    date_out_to = params["date_out_to"]
    date_ret_from = params["date_ret_from"]
    date_ret_to = params["date_ret_to"]
    adults = params.get("adults", 2)
    children = params.get("children", 2)
    max_budget = params.get("max_budget")
    max_layover_days = params.get("max_layover_days", 2)
    pax = adults + children

    results_lock = threading.Lock()

    # Step 1: Get routes from origin and to destination
    log.info(f"Multi-city: Finding routes from {origin} and to {destination}")

    outbound_from_origin = []  # origin -> hub fares
    outbound_hub_to_dest = []  # hub -> destination fares
    return_from_dest = []      # destination -> hub fares
    return_hub_to_origin = []  # hub -> origin fares
    direct_outbound = []       # origin -> destination direct
    direct_return = []         # destination -> origin direct

    threads = []

    def fetch_and_store(fn, store, *args):
        result = fn(*args)
        with results_lock:
            store.extend(result)

    # Direct flights first
    t = threading.Thread(target=fetch_and_store, args=(ryanair_cheapest_fares, direct_outbound, origin, destination, date_out_from, date_out_to))
    threads.append(t); t.start()
    t = threading.Thread(target=fetch_and_store, args=(ryanair_cheapest_fares, direct_return, destination, origin, date_ret_from, date_ret_to))
    threads.append(t); t.start()

    # Get routes from origin (what hubs can we fly to?)
    origin_routes = ryanair_get_routes(origin)
    dest_routes = ryanair_get_routes(destination)

    origin_set = set(origin_routes)
    dest_set = set(dest_routes)

    log.info(f"Multi-city: WAW routes={origin_routes}, FUE routes={dest_routes}")

    # For outbound via hub: need hub reachable FROM origin AND with route TO destination
    # For return via hub: need hub reachable FROM destination AND with route TO origin
    outbound_hubs = origin_set & dest_set  # hub must be reachable from both
    # But also: origin can fly to hub, and hub can fly to dest (even if not in dest_routes)
    # Use ALL origin destinations as potential outbound hubs
    # Use ALL dest destinations as potential return hubs
    all_potential = origin_set | dest_set
    # Prioritize shared hubs, then popular cheap hubs
    shared_hubs = origin_set & dest_set
    origin_cheap = origin_set & set(CHEAP_HUBS)
    dest_cheap = dest_set & set(CHEAP_HUBS)
    potential_hubs = shared_hubs | origin_cheap | dest_cheap

    log.info(f"Multi-city: shared={shared_hubs}, origin_cheap={origin_cheap}, dest_cheap={dest_cheap}")
    log.info(f"Multi-city: {len(potential_hubs)} potential hubs: {potential_hubs}")

    # Limit to reasonable number
    hubs_to_check = list(potential_hubs)[:30]

    # Extend date ranges for hub connections (layover flexibility)
    from datetime import datetime as dt, timedelta as td
    out_start = dt.strptime(date_out_from, "%Y-%m-%d")
    out_end = dt.strptime(date_out_to, "%Y-%m-%d") + td(days=max_layover_days)
    ret_start = dt.strptime(date_ret_from, "%Y-%m-%d")
    ret_end = dt.strptime(date_ret_to, "%Y-%m-%d") + td(days=max_layover_days)
    ext_out_to = out_end.strftime("%Y-%m-%d")
    ext_ret_to = ret_end.strftime("%Y-%m-%d")

    # For outbound: origin -> hub, hub -> destination
    # For return: dest -> hub, hub -> origin
    for hub in hubs_to_check:
        # Outbound leg 1: origin -> hub
        if hub in origin_set:
            t = threading.Thread(target=fetch_and_store, args=(
                ryanair_cheapest_fares, outbound_from_origin, origin, hub, date_out_from, date_out_to))
            threads.append(t); t.start()
        # Outbound leg 2: hub -> destination (extended dates for layover)
        if hub in dest_set:
            t = threading.Thread(target=fetch_and_store, args=(
                ryanair_cheapest_fares, outbound_hub_to_dest, hub, destination, date_out_from, ext_out_to))
            threads.append(t); t.start()
        # Return leg 1: destination -> hub
        if hub in dest_set:
            t = threading.Thread(target=fetch_and_store, args=(
                ryanair_cheapest_fares, return_from_dest, destination, hub, date_ret_from, date_ret_to))
            threads.append(t); t.start()
        # Return leg 2: hub -> origin (extended dates for layover)
        # Check both directions — Ryanair routes are usually bidirectional
        t = threading.Thread(target=fetch_and_store, args=(
            ryanair_cheapest_fares, return_hub_to_origin, hub, origin, date_ret_from, ext_ret_to))
        threads.append(t); t.start()

    # Wait for all threads
    for t in threads:
        t.join(timeout=30)

    log.info(f"Multi-city: Collected fares - direct_out={len(direct_outbound)}, direct_ret={len(direct_return)}, "
             f"out_origin_hub={len(outbound_from_origin)}, out_hub_dest={len(outbound_hub_to_dest)}, "
             f"ret_dest_hub={len(return_from_dest)}, ret_hub_origin={len(return_hub_to_origin)}")

    # Step 2: Build trip combinations
    trips = []

    # Type A: Direct outbound + Direct return
    for out in direct_outbound:
        for ret in direct_return:
            out_date = datetime.strptime(out["date"], "%Y-%m-%d")
            ret_date = datetime.strptime(ret["date"], "%Y-%m-%d")
            stay = (ret_date - out_date).days
            if stay < 1:
                continue
            total_pp = out["price"] + ret["price"]
            total = total_pp * pax
            trips.append({
                "type": "Direct Round-trip",
                "segments": [
                    {"from": origin, "to": destination, "date": out["date"], "price_pp": out["price"]},
                    {"from": destination, "to": origin, "date": ret["date"], "price_pp": ret["price"]},
                ],
                "total_pp": round(total_pp, 2),
                "total": round(total, 2),
                "stay_days": stay,
                "hubs": [],
                "num_flights": 2,
            })

    # Type B: Origin→Hub→Dest (outbound via hub) + Direct return
    for leg1 in outbound_from_origin:
        hub = leg1["dest"]
        leg1_date = datetime.strptime(leg1["date"], "%Y-%m-%d")
        for leg2 in outbound_hub_to_dest:
            if leg2["origin"] != hub:
                continue
            leg2_date = datetime.strptime(leg2["date"], "%Y-%m-%d")
            layover = (leg2_date - leg1_date).days
            if layover < 0 or layover > max_layover_days:
                continue
            # Pair with direct or hub return
            for ret in direct_return:
                ret_date = datetime.strptime(ret["date"], "%Y-%m-%d")
                stay = (ret_date - leg2_date).days
                if stay < 1:
                    continue
                total_pp = leg1["price"] + leg2["price"] + ret["price"]
                total = total_pp * pax
                trips.append({
                    "type": f"Via {hub} (outbound)",
                    "segments": [
                        {"from": origin, "to": hub, "date": leg1["date"], "price_pp": leg1["price"]},
                        {"from": hub, "to": destination, "date": leg2["date"], "price_pp": leg2["price"]},
                        {"from": destination, "to": origin, "date": ret["date"], "price_pp": ret["price"]},
                    ],
                    "total_pp": round(total_pp, 2),
                    "total": round(total, 2),
                    "stay_days": stay,
                    "hubs": [hub],
                    "num_flights": 3,
                })

    # Type C: Direct outbound + Dest→Hub→Origin (return via hub)
    for out in direct_outbound:
        out_date = datetime.strptime(out["date"], "%Y-%m-%d")
        for ret1 in return_from_dest:
            hub = ret1["dest"]
            ret1_date = datetime.strptime(ret1["date"], "%Y-%m-%d")
            stay = (ret1_date - out_date).days
            if stay < 1:
                continue
            for ret2 in return_hub_to_origin:
                if ret2["origin"] != hub:
                    continue
                ret2_date = datetime.strptime(ret2["date"], "%Y-%m-%d")
                layover = (ret2_date - ret1_date).days
                if layover < 0 or layover > max_layover_days:
                    continue
                total_pp = out["price"] + ret1["price"] + ret2["price"]
                total = total_pp * pax
                trips.append({
                    "type": f"Via {hub} (return)",
                    "segments": [
                        {"from": origin, "to": destination, "date": out["date"], "price_pp": out["price"]},
                        {"from": destination, "to": hub, "date": ret1["date"], "price_pp": ret1["price"]},
                        {"from": hub, "to": origin, "date": ret2["date"], "price_pp": ret2["price"]},
                    ],
                    "total_pp": round(total_pp, 2),
                    "total": round(total, 2),
                    "stay_days": stay,
                    "hubs": [hub],
                    "num_flights": 3,
                })

    # Type D: Origin→Hub1→Dest + Dest→Hub2→Origin (both via hubs)
    for leg1 in outbound_from_origin:
        hub1 = leg1["dest"]
        leg1_date = datetime.strptime(leg1["date"], "%Y-%m-%d")
        for leg2 in outbound_hub_to_dest:
            if leg2["origin"] != hub1:
                continue
            leg2_date = datetime.strptime(leg2["date"], "%Y-%m-%d")
            layover1 = (leg2_date - leg1_date).days
            if layover1 < 0 or layover1 > max_layover_days:
                continue
            for ret1 in return_from_dest:
                hub2 = ret1["dest"]
                ret1_date = datetime.strptime(ret1["date"], "%Y-%m-%d")
                stay = (ret1_date - leg2_date).days
                if stay < 1:
                    continue
                for ret2 in return_hub_to_origin:
                    if ret2["origin"] != hub2:
                        continue
                    ret2_date = datetime.strptime(ret2["date"], "%Y-%m-%d")
                    layover2 = (ret2_date - ret1_date).days
                    if layover2 < 0 or layover2 > max_layover_days:
                        continue
                    total_pp = leg1["price"] + leg2["price"] + ret1["price"] + ret2["price"]
                    total = total_pp * pax
                    trips.append({
                        "type": f"Via {hub1}+{hub2}",
                        "segments": [
                            {"from": origin, "to": hub1, "date": leg1["date"], "price_pp": leg1["price"]},
                            {"from": hub1, "to": destination, "date": leg2["date"], "price_pp": leg2["price"]},
                            {"from": destination, "to": hub2, "date": ret1["date"], "price_pp": ret1["price"]},
                            {"from": hub2, "to": origin, "date": ret2["date"], "price_pp": ret2["price"]},
                        ],
                        "total_pp": round(total_pp, 2),
                        "total": round(total, 2),
                        "stay_days": stay,
                        "hubs": [hub1, hub2],
                        "num_flights": 4,
                    })

    # Filter by budget
    if max_budget:
        trips = [t for t in trips if t["total"] <= max_budget]

    # Sort by total price, deduplicate top results
    trips.sort(key=lambda x: x["total"])

    # Keep top 100
    trips = trips[:100]

    return {
        "trips": trips,
        "stats": {
            "total_combinations": len(trips),
            "hubs_checked": len(hubs_to_check),
            "origin_routes": len(origin_routes),
            "dest_routes": len(dest_routes),
        },
        "params": params,
        "timestamp": datetime.now().isoformat(),
    }


@app.route("/warm-destinations", methods=["POST"])
def warm_destinations():
    """Return destinations with warm weather for given dates."""
    data = request.json or {}
    date_str = data.get("date", "2026-06-15")
    min_temp = int(data.get("min_temp", 25))
    try:
        month = int(date_str.split("-")[1])
    except:
        month = 6

    results = []
    for key, info in WARM_DESTINATIONS.items():
        temp = info["temps"].get(month, 0)
        if temp >= min_temp and key in DESTINATION_HUB_MAP:
            results.append({
                "keyword": key,
                "desc": info["desc"],
                "emoji": info["emoji"],
                "temp": temp,
                "water_temp": info.get("water", 0),
                "month": month,
            })

    results.sort(key=lambda x: -x["temp"])
    return jsonify({"destinations": results, "month": month, "min_temp": min_temp})


@app.route("/smart")
def smart_page():
    return render_template("smart.html", dest_map=list(DESTINATION_HUB_MAP.keys()))


@app.route("/search-smart", methods=["POST"])
def search_smart():
    data = request.json or {}
    params = {
        "destination": data.get("destination", "tajlandia"),
        "date_out_from": data.get("date_out_from", "2026-06-15"),
        "date_out_to": data.get("date_out_to", "2026-06-22"),
        "date_ret_from": data.get("date_ret_from", "2026-06-28"),
        "date_ret_to": data.get("date_ret_to", "2026-07-05"),
        "adults": int(data.get("adults", 2)),
        "children": int(data.get("children", 2)),
        "max_stops": int(data.get("max_stops")) if data.get("max_stops") not in (None, "", "any") else None,
        "max_budget": int(data.get("max_budget")) if data.get("max_budget") else None,
    }
    result = smart_search(params)
    return jsonify(result)


@app.route("/multi")
def multi_city():
    return render_template("multi.html", airports=POLISH_AIRPORTS, dest_groups=DEST_GROUPS)


@app.route("/search-multi", methods=["POST"])
def search_multi():
    data = request.json or {}
    params = {
        "origin": data.get("origin", "WAW"),
        "destination": data.get("destination", "FUE"),
        "date_out_from": data.get("date_out_from", "2027-01-29"),
        "date_out_to": data.get("date_out_to", "2027-02-03"),
        "date_ret_from": data.get("date_ret_from", "2027-02-10"),
        "date_ret_to": data.get("date_ret_to", "2027-02-14"),
        "adults": int(data.get("adults", 2)),
        "children": int(data.get("children", 2)),
        "max_budget": int(data.get("max_budget")) if data.get("max_budget") else None,
        "max_layover_days": int(data.get("max_layover_days", 2)),
    }
    result = find_multi_city_trips(params)
    return jsonify(result)


@app.route("/fetch-price", methods=["POST"])
def fetch_price():
    """Fetch real price from Google Flights by scraping the page via Chrome.
    Called by frontend one route at a time."""
    data = request.json or {}
    hub = data.get("hub", "STN")
    dest = data.get("dest", "BKK")
    date_out = data.get("date_out", "2026-06-15")
    date_ret = data.get("date_ret", "2026-06-28")
    adults = int(data.get("adults", 2))
    children = int(data.get("children", 2))
    max_stops = data.get("max_stops")  # None = any, 0 = direct only, 1 = max 1

    # Build Google Flights URL
    gf_url = build_google_flights_url(hub, dest, date_out, date_ret, adults, children)

    # We return the URL — the frontend will open it in Chrome and read the price
    # This endpoint just provides the properly formatted URL and params
    return jsonify({
        "hub": hub,
        "dest": dest,
        "google_flights_url": gf_url,
        "kiwi_url": f"https://www.kiwi.com/pl/search/tiles/{hub.lower()}/{dest.lower()}/{date_out}/{date_ret}?adults={adults}&children={children}&sortBy=price",
    })


@app.route("/export-csv", methods=["POST"])
def export_csv():
    """Export results as CSV file download."""
    import csv
    import io
    data = request.json or {}
    results = data.get("results", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "source", "airline", "origin", "destination", "date", "direct",
        "price_per_person", "currency", "price_per_person_pln",
        "total_price_pln", "pax", "link", "notes"
    ])
    for r in results:
        writer.writerow([
            r.get("source"), r.get("airline"), r.get("origin"),
            r.get("destination"), r.get("date"),
            "Yes" if r.get("direct") else "No" if r.get("direct") is False else "?",
            r.get("price_per_person"), r.get("currency"),
            r.get("price_per_person_pln"), r.get("total_price_pln"),
            r.get("pax"), r.get("link"), r.get("notes"),
        ])
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=flights_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5555))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
