"""Scraper for Ritchie Bros (rbauction.com).

This site aggressively blocks non-browser requests (403 on everything).
Uses Selenium to load the page, then attempts to discover and use their
internal API via network interception. Falls back to DOM parsing.
"""

import re
import json
import time
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from scrapers.base_scraper import BaseScraper, AuctionListing

# States we care about
TARGET_STATES = {"CA", "AZ", "NV", "California", "Arizona", "Nevada"}


class RitchieBrosScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "Ritchie Bros"

    @property
    def base_url(self) -> str:
        return "https://www.rbauction.com/heavy-equipment-auctions"

    def _init_driver(self) -> webdriver.Chrome:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # Enable network logging to capture API calls
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        return driver

    def _scrape_impl(self) -> list[AuctionListing]:
        driver = self._init_driver()
        try:
            driver.get(self.base_url)

            # Wait for content to load
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "main"))
                )
            except Exception:
                self.logger.warning("Page load timeout")

            time.sleep(5)  # Extra time for SPA rendering

            # Strategy 1: Try to find auction data in network logs (JSON API responses)
            listings = self._extract_from_network(driver)
            if listings:
                return listings

            # Strategy 2: Parse the rendered DOM
            soup = BeautifulSoup(driver.page_source, "lxml")
            return self._parse_dom(soup)
        finally:
            driver.quit()

    def _extract_from_network(self, driver) -> list[AuctionListing]:
        """Try to extract auction data from intercepted network API responses."""
        listings = []
        try:
            logs = driver.get_log("performance")
            for entry in logs:
                try:
                    message = json.loads(entry["message"])["message"]
                    if message["method"] != "Network.responseReceived":
                        continue
                    url = message["params"]["response"]["url"]
                    # Look for API responses that might contain auction data
                    if any(kw in url.lower() for kw in ["auction", "event", "sale", "catalog"]):
                        if "json" in message["params"]["response"].get("mimeType", ""):
                            request_id = message["params"]["requestId"]
                            try:
                                body = driver.execute_cdp_cmd(
                                    "Network.getResponseBody",
                                    {"requestId": request_id}
                                )
                                data = json.loads(body.get("body", "{}"))
                                api_listings = self._parse_api_response(data)
                                if api_listings:
                                    self.logger.info(
                                        f"Found {len(api_listings)} auctions from API: {url[:80]}"
                                    )
                                    listings.extend(api_listings)
                            except Exception:
                                pass
                except (KeyError, json.JSONDecodeError):
                    continue
        except Exception as e:
            self.logger.debug(f"Network log extraction failed: {e}")

        return listings

    def _parse_api_response(self, data) -> list[AuctionListing]:
        """Try to parse auction data from a JSON API response."""
        listings = []
        # Handle various possible response shapes
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ["auctions", "events", "results", "data", "items"]:
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break

        for item in items:
            if not isinstance(item, dict):
                continue
            listing = self._parse_api_item(item)
            if listing:
                listings.append(listing)

        return listings

    def _parse_api_item(self, item: dict) -> AuctionListing | None:
        """Parse a single auction from API JSON."""
        # Try to find location and filter for target states
        location = ""
        for key in ["location", "city", "venue", "address", "region"]:
            if key in item and isinstance(item[key], str):
                location = item[key]
                break
            elif key in item and isinstance(item[key], dict):
                loc_dict = item[key]
                parts = []
                for sub in ["city", "state", "stateProvince", "country"]:
                    if sub in loc_dict:
                        parts.append(str(loc_dict[sub]))
                location = ", ".join(parts)
                break

        if not self._is_target_state(location):
            return None

        # Title
        title = ""
        for key in ["title", "name", "eventTitle", "auctionTitle", "description"]:
            if key in item and isinstance(item[key], str):
                title = item[key]
                break
        if not title:
            title = f"Ritchie Bros Auction - {location}"

        # Date
        raw_date = ""
        for key in ["date", "startDate", "auctionDate", "eventDate", "start_date"]:
            if key in item:
                raw_date = str(item[key])
                break

        iso_date = "2099-12-31"
        display_date = "Date TBD"
        if raw_date:
            # Try ISO format first
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", raw_date)
            if date_match:
                try:
                    iso_date, display_date = self.parse_date(date_match.group(1))
                except ValueError:
                    pass

        # URL
        url = ""
        for key in ["url", "link", "href", "detailUrl"]:
            if key in item and isinstance(item[key], str):
                url = item[key]
                break
        if url and not url.startswith("http"):
            url = f"https://www.rbauction.com{url}"
        if not url:
            url = self.base_url

        # Auction type
        auction_type = "Live & Online"
        for key in ["type", "auctionType", "eventType", "saleType"]:
            if key in item:
                type_val = str(item[key]).lower()
                if "online" in type_val and "live" not in type_val:
                    auction_type = "Online"
                elif "live" in type_val:
                    auction_type = "Live"
                break

        # Item count
        item_count = None
        for key in ["lotCount", "itemCount", "totalLots", "numberOfLots"]:
            if key in item:
                try:
                    item_count = int(item[key])
                except (ValueError, TypeError):
                    pass
                break

        return self._create_listing(
            title=title,
            date=iso_date,
            date_display=display_date,
            location=location,
            url=url,
            auction_type=auction_type,
            item_count=item_count,
        )

    def _parse_dom(self, soup: BeautifulSoup) -> list[AuctionListing]:
        """Parse auction cards from the rendered MUI DOM.

        Card structure (Material UI):
            div[data-testid="auction-card-XXXXXXX"]  -> card container
            [data-testid="auction-card-date-range-X"] -> "Mar 25 - Mar 27"
            h5.MuiCardHeader-subheader                -> "California Regional Auction, USA"
            Card text contains: item count, auction type, location
        """
        listings = []

        # Select only top-level auction cards (not nested sub-elements)
        cards = soup.find_all("div", attrs={
            "data-testid": re.compile(r"^auction-card-\d+$")
        })
        self.logger.info(f"DOM: Found {len(cards)} auction cards")

        current_year = time.strftime("%Y")

        for card in cards:
            text = card.get_text(" ", strip=True)
            if not self._is_target_state(text):
                continue

            # Auction ID from data-testid
            testid = card.get("data-testid", "")
            auction_id = testid.replace("auction-card-", "")

            # Title from subheader
            title_el = card.select_one(".MuiCardHeader-subheader")
            title = title_el.get_text(strip=True) if title_el else "Ritchie Bros Auction"

            # Date from date-range element (e.g., "Mar 25 - Mar 27" or "Apr 8")
            date_el = card.select_one(f'[data-testid="auction-card-date-range-{auction_id}"]')
            raw_date = date_el.get_text(strip=True) if date_el else ""

            iso_date, display_date = self._parse_rb_date(raw_date, current_year)

            # Location from card text
            location = self._extract_location(text)

            # Item count from text (e.g., "6,897 Items" or "95 Items")
            item_count = None
            count_match = re.search(r'([\d,]+)\s+Items?', text)
            if count_match:
                try:
                    item_count = int(count_match.group(1).replace(",", ""))
                except ValueError:
                    pass

            # Auction type
            auction_type = "Timed" if "Timed auction" in text else "Live & Online"

            # Build URL from auction ID
            slug = title.lower().replace(",", "").replace(" ", "-").replace(".", "")
            slug = re.sub(r'-+', '-', slug).strip("-")
            url = f"https://www.rbauction.com/heavy-equipment-auctions/{slug}-{auction_id}"

            listings.append(self._create_listing(
                title=title,
                date=iso_date,
                date_display=display_date,
                location=location,
                url=url,
                auction_type=auction_type,
                item_count=item_count,
            ))

        return listings

    def _parse_rb_date(self, raw: str, year: str) -> tuple[str, str]:
        """Parse Ritchie Bros date format like 'Mar 25 - Mar 27' or 'Apr 8'.

        Returns (iso_date, display_date). Uses the start date for sorting.
        """
        if not raw:
            return "2099-12-31", "Date TBD"

        # Take the first date (start date) for multi-day events
        first_date = raw.split("-")[0].strip()

        # Parse "Mar 25" or "Apr 8"
        match = re.match(r"([A-Za-z]{3})\s+(\d{1,2})", first_date)
        if not match:
            return "2099-12-31", raw

        month_str, day = match.group(1), match.group(2)
        try:
            iso_date, _ = self.parse_date(f"{month_str} {day}, {year}")
        except ValueError:
            return "2099-12-31", raw

        # Use the original string as display (e.g., "Mar 25 - Mar 27, 2026")
        display = f"{raw}, {year}"
        return iso_date, display

    def _is_target_state(self, text: str) -> bool:
        """Check if text mentions CA, AZ, or NV."""
        text_upper = text.upper()
        # Check state abbreviations (with word boundaries via common delimiters)
        for abbr in ["CA", "AZ", "NV"]:
            if re.search(rf'(?:^|[\s,]){abbr}(?:[\s,\d]|$)', text_upper):
                return True
        # Check full state names
        for name in ["CALIFORNIA", "ARIZONA", "NEVADA"]:
            if name in text_upper:
                return True
        return False

    def _extract_location(self, text: str) -> str:
        """Try to extract a city, state from text."""
        # Look for "City, ST" pattern
        match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*(CA|AZ|NV)\b', text)
        if match:
            return f"{match.group(1)}, {match.group(2)}"
        return "CA/AZ/NV"
