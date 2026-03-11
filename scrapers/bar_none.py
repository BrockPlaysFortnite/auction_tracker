"""Scraper for Bar None Auction (barnoneauction.com).

Static WordPress site using Elementor + ElementsKit post cards.
Simple requests + BeautifulSoup — no Selenium needed.

DOM Structure (discovered 2026-03-11):
    div.elementskit-post-card        -> auction card
    h2.entry-title a                 -> date text (e.g. "MARCH 14, 2026") + auction URL
    span.post-cat a                  -> location (e.g. "Sacramento, California")
    a.elementskit-btn                -> "VIEW AUCTION" link (same URL)
    URL slug pattern                 -> /sacramento-equipment-auction-march-2026/
"""

import re
import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, AuctionListing


class BarNoneScraper(BaseScraper):

    @property
    def source_name(self) -> str:
        return "Bar None"

    @property
    def base_url(self) -> str:
        return "https://www.barnoneauction.com/auctions"

    def _scrape_impl(self) -> list[AuctionListing]:
        resp = requests.get(self.base_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        listings = []

        cards = soup.select("div.elementskit-post-card")
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
        # URL from the title link
        title_el = card.select_one(".entry-title a")
        if not title_el:
            return None
        url = title_el.get("href", "")

        # The h2.entry-title text is actually the DATE (e.g., "MARCH 14, 2026")
        raw_date = title_el.get_text(strip=True)

        try:
            iso_date, display_date = self.parse_date(raw_date)
        except ValueError:
            self.logger.warning(f"Could not parse date '{raw_date}'")
            iso_date = "2099-12-31"
            display_date = raw_date or "Date TBD"

        # Location from the category span
        loc_el = card.select_one("span.post-cat a")
        location = loc_el.get_text(strip=True) if loc_el else "See auction details"

        # Build a proper title from the URL slug
        # e.g., /sacramento-equipment-auction-march-2026/ -> "Sacramento Equipment Auction"
        title = self._title_from_url(url, location)

        return self._create_listing(
            title=title,
            date=iso_date,
            date_display=display_date,
            location=location,
            url=url,
            auction_type="Live",
        )

    def _title_from_url(self, url: str, location: str) -> str:
        """Extract a readable title from the URL slug."""
        # Get the slug from URL path
        slug_match = re.search(r'/([^/]+)/?$', url.rstrip('/'))
        if not slug_match:
            return f"Bar None Equipment Auction - {location}"

        slug = slug_match.group(1)
        # Remove date parts (month-year) from slug
        slug = re.sub(r'-(?:january|february|march|april|may|june|july|august|'
                       r'september|october|november|december)-\d{4}$', '', slug)
        # Convert hyphens to spaces and title-case
        title = slug.replace('-', ' ').title()
        return title
