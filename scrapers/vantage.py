"""Scraper for Vantage Auctions (vantageauctions.com).

Static WordPress site. Auction listings are plain linked text blocks
under an "Auction Schedule" section — no card containers or CSS hooks.

Each listing is an <a> tag whose text contains the auction type, date, and time
run together. Two auction types:
    - "Heavy Construction Equipment\nSaturday, March 21, 2026 9:00 am"
    - "Timed Land Auction\nBidding Starts: ...\nBidding Ends: ..."
"""

import re
import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, AuctionListing


class VantageScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "Vantage"

    @property
    def base_url(self) -> str:
        return "https://www.vantageauctions.com/auctions/"

    def _scrape_impl(self) -> list[AuctionListing]:
        resp = requests.get(self.base_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        listings = []

        # Find all links that contain auction-related text
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]

            # Skip navigation/footer links — only process links with date-like content
            if not re.search(r'\d{4}', text):
                continue

            # Heavy Construction Equipment auctions
            if "Heavy Construction Equipment" in text:
                listing = self._parse_equipment_auction(text, href)
                if listing:
                    listings.append(listing)

            # Timed Land Auctions
            elif "Timed Land Auction" in text:
                listing = self._parse_timed_auction(text, href)
                if listing:
                    listings.append(listing)

        self.logger.info(f"Parsed {len(listings)} auction listings")
        return listings

    def _parse_equipment_auction(self, text: str, href: str) -> AuctionListing | None:
        """Parse 'Heavy Construction Equipment' live auction.

        Text format: "Heavy Construction EquipmentSaturday, March 21, 2026 9:00 am"
        """
        # Extract date — look for "Day, Month DD, YYYY"
        date_match = re.search(
            r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
            r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})',
            text
        )
        if not date_match:
            return None

        month, day, year = date_match.group(1), date_match.group(2), date_match.group(3)
        try:
            iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
        except ValueError:
            return None

        return self._create_listing(
            title="Heavy Construction Equipment Auction",
            date=iso_date,
            date_display=display_date,
            location="Perris, CA",  # Vantage is based in Perris, CA
            url=href,
            auction_type="Live",
        )

    def _parse_timed_auction(self, text: str, href: str) -> AuctionListing | None:
        """Parse 'Timed Land Auction' online auction.

        Text format: "Timed Land AuctionBidding Starts: Tuesday, March 10, 2026...
                      Bidding Ends: Tuesday, March 24, 2026..."
        """
        # Use the "Bidding Ends" date as the auction date
        ends_match = re.search(
            r'Bidding\s+Ends:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
            r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})',
            text
        )
        if not ends_match:
            # Fall back to "Bidding Starts" date
            starts_match = re.search(
                r'Bidding\s+Starts:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
                r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})',
                text
            )
            if not starts_match:
                return None
            month, day, year = starts_match.group(1), starts_match.group(2), starts_match.group(3)
        else:
            month, day, year = ends_match.group(1), ends_match.group(2), ends_match.group(3)

        try:
            iso_date, display_date = self.parse_date(f"{month} {day}, {year}")
        except ValueError:
            return None

        return self._create_listing(
            title="Timed Land Auction",
            date=iso_date,
            date_display=display_date,
            location="Perris, CA",
            url=href,
            auction_type="Online",
            notes="Online via Proxibid",
        )
