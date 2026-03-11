"""Scraper for General Auction Company (gacbids.com).

JavaScript SPA — requires Selenium to render auction cards.

DOM Structure (discovered 2026-03-11):
    div.auction-card                     -> card container
    div.auction-card__name a             -> title + URL (/auctions/XXXXX/lots)
    div.auction-card__location-info      -> "Online Bidding" or location
    div.auction-card__timeline           -> "First lot closing on Mar 13, 2026 at 9:00AM PDT"
    span with "Running"/"Upcoming"/etc   -> status
    "LOTS" + number                      -> lot count
"""

import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, AuctionListing


class GACScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "GAC"

    @property
    def base_url(self) -> str:
        return "https://gacbids.com/auctions"

    def _scrape_impl(self) -> list[AuctionListing]:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        try:
            driver.get(self.base_url)
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.auction-card"))
                )
            except Exception:
                self.logger.warning("Timeout waiting for auction cards")
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, "lxml")
            return self._parse_cards(soup)
        finally:
            driver.quit()

    def _parse_cards(self, soup: BeautifulSoup) -> list[AuctionListing]:
        listings = []
        cards = soup.select("div.auction-card")
        self.logger.info(f"Found {len(cards)} auction cards")

        for card in cards:
            try:
                listing = self._parse_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                self.logger.warning(f"Failed to parse card: {e}")

        return listings

    def _parse_card(self, card) -> AuctionListing | None:
        # Title + URL
        title_el = card.select_one("div.auction-card__name a")
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        url = f"https://gacbids.com{href}" if href.startswith("/") else href

        # Date from timeline text like "First lot closing on Mar 13, 2026 at 9:00AM PDT"
        timeline_el = card.select_one("div.auction-card__timeline")
        raw_timeline = timeline_el.get_text(strip=True) if timeline_el else ""

        iso_date = "2099-12-31"
        display_date = "Date TBD"

        date_match = re.search(
            r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})',
            raw_timeline
        )
        if date_match:
            month, day, year = date_match.group(1), date_match.group(2), date_match.group(3)
            try:
                iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
            except ValueError:
                pass

        # Also try parsing date from the title itself (e.g., "MARCH 13TH, 2026 PUBLIC AUCTION...")
        if iso_date == "2099-12-31":
            title_date = re.search(
                r'([A-Za-z]+)\s+(\d{1,2})(?:ST|ND|RD|TH)?,?\s+(\d{4})',
                title, re.IGNORECASE
            )
            if title_date:
                month, day, year = title_date.group(1), title_date.group(2), title_date.group(3)
                try:
                    iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
                except ValueError:
                    pass

        # Location
        loc_el = card.select_one("div.auction-card__location-info")
        location = loc_el.get_text(strip=True) if loc_el else "Redlands, CA"
        if location == "Online Bidding":
            location = "Online - Redlands, CA"

        # Lot count
        card_text = card.get_text(" ", strip=True)
        item_count = None
        lot_match = re.search(r'LOTS\s*(\d+)', card_text)
        if lot_match:
            item_count = int(lot_match.group(1))

        # Auction type
        auction_type = "Online"
        if "Timed" in card_text:
            auction_type = "Timed Online"

        return self._create_listing(
            title=title,
            date=iso_date,
            date_display=display_date,
            location=location,
            url=url,
            auction_type=auction_type,
            item_count=item_count,
        )
