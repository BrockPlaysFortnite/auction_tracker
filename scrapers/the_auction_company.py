"""Scraper for The Auction Company (bid.theauctioncompany.net).

This site uses the Bidpath auction platform and blocks simple HTTP requests (403).
Requires Selenium to render the JavaScript-loaded auction listings.

DOM Structure (discovered 2026-03-11):
    Each auction is a <ul class="auclting yura"> containing:
    - li.aucdes h6 a         -> title (includes sale#, day, ring, location, description)
    - li.aucdes span.sale-no  -> sale number (e.g. "263")
    - li.aucdes span.auction_list_start_date -> "04/25/2026 09:00 AM PDT"
    - li.aucdes p a[id^=sale] -> auction type ("Live" or "Timed")
    - li.aucdes p             -> "Lots: 43"
    - a[href*=/auctions/catalog/id/] -> catalog link
"""

import re
import time
from bs4 import BeautifulSoup, Tag

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from scrapers.base_scraper import BaseScraper, AuctionListing


class TheAuctionCompanyScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "The Auction Company"

    @property
    def base_url(self) -> str:
        return "https://bid.theauctioncompany.net"

    def _init_driver(self) -> webdriver.Chrome:
        """Initialize headless Chrome with realistic browser fingerprint."""
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

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        return driver

    def _scrape_impl(self) -> list[AuctionListing]:
        """Scrape auction listings from bid.theauctioncompany.net."""
        driver = self._init_driver()
        try:
            driver.get(self.base_url)

            # Wait for the auction cards to render
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "ul.auclting"))
                )
            except Exception:
                self.logger.warning("Timeout waiting for auction cards")

            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, "lxml")
            return self._parse_listings(soup)
        finally:
            driver.quit()

    def _parse_listings(self, soup: BeautifulSoup) -> list[AuctionListing]:
        """Parse auction cards from the Bidpath platform HTML."""
        listings = []
        cards = soup.select("ul.auclting")
        self.logger.info(f"Found {len(cards)} auction cards")

        for card in cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                self.logger.warning(f"Failed to parse card: {e}")

        return listings

    def _parse_card(self, card: Tag) -> AuctionListing | None:
        """Parse a single <ul class='auclting'> element."""
        # --- Title & catalog link ---
        title_el = card.select_one("li.aucdes h6 a")
        if not title_el:
            return None

        raw_title = title_el.get_text(strip=True)
        catalog_url = title_el.get("href", "")
        if catalog_url and not catalog_url.startswith("http"):
            catalog_url = f"{self.base_url.rstrip('/')}/{catalog_url.lstrip('/')}"

        # Strip the sale number prefix from the title display
        sale_no_el = card.select_one("li.aucdes h6 span.sale-no")
        sale_no = sale_no_el.get_text(strip=True) if sale_no_el else ""
        title = raw_title
        if sale_no and title.startswith(sale_no):
            title = title[len(sale_no):]
        title = title.strip()

        # --- Date ---
        # For timed/online auctions, prefer the "Starts Ending" date (closing date)
        # over the start date, since the start date is when bidding opened (possibly weeks ago)
        ending_el = card.select_one("span.auc-starts-ending-date")
        start_el = card.select_one("span.auction_list_start_date")

        raw_date = ""
        if ending_el:
            raw_date = ending_el.get_text(strip=True)
            # Text is like "Starts Ending 04/27/2026 12:00 PM PDT"
            raw_date = re.sub(r"^Starts\s+Ending\s+", "", raw_date, flags=re.IGNORECASE)
        elif start_el:
            raw_date = start_el.get_text(strip=True)

        iso_date, display_date = self._parse_auction_date(raw_date, title)

        # --- Auction type ---
        type_el = card.select_one("li.aucdes p a[id^='sale']")
        auction_type = "Live"
        if type_el:
            type_text = type_el.get_text(strip=True).lower()
            if "timed" in type_text:
                auction_type = "Online"

        if "ONLINE ONLY" in title.upper():
            auction_type = "Online"

        # --- Lot count ---
        item_count = None
        for p in card.select("li.aucdes p"):
            text = p.get_text(strip=True)
            lots_match = re.match(r"Lots:\s*(\d+)", text)
            if lots_match:
                item_count = int(lots_match.group(1))
                break

        # --- Location ---
        location = "CA"
        loc_match = re.search(r"Ring\s+\d+\s+([A-Za-z\s]+?):", title)
        if loc_match:
            city = loc_match.group(1).strip().title()
            location = f"{city}, CA"

        return self._create_listing(
            title=title,
            date=iso_date,
            date_display=display_date,
            location=location,
            url=catalog_url or self.base_url,
            auction_type=auction_type,
            item_count=item_count,
        )

    def _parse_auction_date(self, raw_date: str, title: str) -> tuple[str, str]:
        """Extract date from the date span or fall back to title text.

        Handles formats like:
            "04/25/2026 09:00 AM PDT"
            "01/12/2026 11:45 AM PST-04/27/2026 12:00 PM PDT" (timed range)
        """
        if raw_date:
            # For timed auctions with a date range, use the end date
            if "-" in raw_date and raw_date.count("/") >= 4:
                date_part = raw_date.split("-")[-1].strip()
            else:
                date_part = raw_date

            date_match = re.match(r"(\d{2}/\d{2}/\d{4})", date_part)
            if date_match:
                try:
                    return self.parse_date(date_match.group(1))
                except ValueError:
                    pass

        # Fallback: parse from title (e.g., "SATURDAY, APRIL 25TH-Ring 1...")
        title_date_match = re.search(
            r"(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+"
            r"([A-Z]+)\s+(\d+)",
            title, re.IGNORECASE
        )
        if title_date_match:
            month_str = title_date_match.group(1)
            day_str = title_date_match.group(2)
            try:
                return self.parse_date(f"{month_str} {day_str}, 2026")
            except ValueError:
                pass

        return "2099-12-31", "Date TBD"
