"""Scraper for JJ Kane Auctions (jjkane.com) — Southern California only.

Static HTML with Bootstrap grid. Simple requests + BeautifulSoup.

DOM Structure (discovered 2026-03-11):
    div.row.border.shadow-sm             -> auction card
    div.col-md-2.all-auctions-list       -> date block ("12Mar202612:00 AM")
    h2.h3                                -> region name ("Southern California")
    h4                                   -> auction type ("Online Timed Auction")
    div.col-md-8 p                       -> description text
    a[href*='/auctions/']                -> "Auction Items" link
"""

import re
import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, AuctionListing


class JJKaneScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "JJ Kane"

    @property
    def base_url(self) -> str:
        return "https://www.jjkane.com/auctions"

    def _scrape_impl(self) -> list[AuctionListing]:
        resp = requests.get(self.base_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=30)
        resp.encoding = "utf-8"
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        listings = []

        # Each auction is a div.row.border.shadow-sm
        cards = soup.select("div.row.border.shadow-sm")
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
        # Region name from h2
        region_el = card.select_one("h2.h3")
        region = region_el.get_text(strip=True) if region_el else ""

        # Only keep Southern California
        if "Southern California" not in region:
            return None

        # Auction type from h4
        type_el = card.select_one("h4")
        auction_type = type_el.get_text(strip=True) if type_el else "Online"

        # URL from "Auction Items" link
        url = self.base_url
        for link in card.find_all("a", href=True):
            if "/auctions/" in link["href"] and "terms" not in link["href"]:
                href = link["href"]
                url = f"https://www.jjkane.com{href}" if href.startswith("/") else href
                break

        # Date from the date block or description text
        card_text = card.get_text(" ", strip=True)

        # Try "M/DD/YYYY" or "MM/DD/YYYY" format from description
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', card_text)
        iso_date = "2099-12-31"
        display_date = "Date TBD"

        if date_match:
            try:
                iso_date, display_date = self.parse_date(date_match.group(1))
            except ValueError:
                pass

        # Fallback: parse the compressed date format like "12Mar2026"
        if iso_date == "2099-12-31":
            compressed = re.search(r'(\d{1,2})([A-Za-z]{3})(\d{4})', card_text)
            if compressed:
                day, month, year = compressed.group(1), compressed.group(2), compressed.group(3)
                try:
                    iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
                except ValueError:
                    pass

        # For multi-day, check for range like "3/10/2026 to 3/11/2026"
        range_match = re.search(
            r'(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})',
            card_text
        )
        if range_match:
            try:
                end_iso, end_display = self.parse_date(range_match.group(2))
                # Use end date for display
                display_date = f"{display_date} - {end_display}"
            except ValueError:
                pass

        title = f"JJ Kane - {region}"

        return self._create_listing(
            title=title,
            date=iso_date,
            date_display=display_date,
            location="Southern California",
            url=url,
            auction_type=auction_type,
        )
