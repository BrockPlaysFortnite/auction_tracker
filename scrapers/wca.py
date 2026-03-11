"""Scraper for Western Construction Auctions (wca-online.com).

Static WordPress site (WPBakery page builder). Shows one upcoming auction
at the top with detail, plus a list of future auction dates as plain text.

Structure:
    - "Next Auction: Friday April 10th, 2026 - 8:30am"
    - "14900 Concordia Ranch Road, Lake Elsinore, CA 92530"
    - "Future Public Auctions 2026: June 12th | August 14th | October 9th | December 4th"
"""

import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, AuctionListing


class WCAScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "WCA"

    @property
    def base_url(self) -> str:
        return "https://wca-online.com/auction-preview/"

    # WCA is always at this address
    DEFAULT_LOCATION = "Lake Elsinore, CA"

    def _scrape_impl(self) -> list[AuctionListing]:
        resp = requests.get(self.base_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        page_text = soup.get_text("\n", strip=True)
        listings = []

        # --- Parse the next upcoming auction ---
        next_auction = self._parse_next_auction(page_text)
        if next_auction:
            listings.append(next_auction)

        # --- Parse future auction dates ---
        future_auctions = self._parse_future_dates(page_text)
        listings.extend(future_auctions)

        self.logger.info(f"Parsed {len(listings)} auction listings")
        return listings

    def _parse_next_auction(self, text: str) -> AuctionListing | None:
        """Parse the primary 'Next Auction' block."""
        # Pattern: "Next Auction: Friday April 10th, 2026 - 8:30am"
        match = re.search(
            r'Next\s+Auction:\s*'
            r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+'
            r'([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
            text, re.IGNORECASE
        )
        if not match:
            self.logger.warning("Could not find 'Next Auction' date")
            return None

        month, day, year = match.group(1), match.group(2), match.group(3)
        try:
            iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
        except ValueError:
            return None

        # Check for preview dates
        notes = ""
        preview_match = re.search(
            r'Preview\s+Dates?:\s*(.+?)(?:\n|Online|Ring)',
            text, re.IGNORECASE
        )
        if preview_match:
            notes = f"Preview: {preview_match.group(1).strip()}"

        # Check for online bidding note
        if re.search(r'Online\s*&?\s*Absentee\s+Bidding', text, re.IGNORECASE):
            auction_type = "Live & Online"
        else:
            auction_type = "Live"

        return self._create_listing(
            title="WCA Public Auction",
            date=iso_date,
            date_display=display_date,
            location=self.DEFAULT_LOCATION,
            url=self.base_url,
            auction_type=auction_type,
            notes=notes,
        )

    def _parse_future_dates(self, text: str) -> list[AuctionListing]:
        """Parse the 'Future Public Auctions' date list."""
        # Pattern: "Future Public Auctions 2026" followed by dates
        # Dates may be separated by pipes, newlines, or spaces
        match = re.search(
            r'Future\s+Public\s+Auctions\s+(\d{4})\s*:?\s*(.+?)(?:Western|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        if not match:
            return []

        year = match.group(1)
        dates_text = match.group(2)

        listings = []
        # Split on pipe, newline, or multiple spaces
        for part in re.split(r'\s*[\|\n]+\s*', dates_text):
            part = part.strip()
            if not part:
                continue

            # Parse "June 12th" or "August 14th"
            date_match = re.match(r'([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?', part)
            if not date_match:
                continue

            month, day = date_match.group(1), date_match.group(2)
            try:
                iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
            except ValueError:
                continue

            listings.append(self._create_listing(
                title="WCA Public Auction",
                date=iso_date,
                date_display=display_date,
                location=self.DEFAULT_LOCATION,
                url=self.base_url,
                auction_type="Live & Online",
            ))

        return listings
