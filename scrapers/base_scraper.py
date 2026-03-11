"""Base scraper class and shared data model for all auction scrapers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
import logging
import time


@dataclass
class AuctionListing:
    """Unified auction listing data model used by all scrapers."""
    title: str
    date: str                       # ISO 8601: "2026-04-10"
    date_display: str               # Human-readable: "Saturday, April 10, 2026"
    location: str                   # "Sacramento, CA"
    source: str                     # "Bar None", "Ritchie Bros", etc.
    url: str                        # Direct link to auction page
    auction_type: str = "Live"      # "Live", "Online", "Live & Online"
    item_count: Optional[int] = None
    notes: str = ""


# Common date format patterns found across auction sites
DATE_FORMATS = [
    "%B %d, %Y",           # March 14, 2026
    "%b %d, %Y",           # Mar 14, 2026
    "%m/%d/%Y",            # 03/14/2026
    "%Y-%m-%d",            # 2026-03-14
    "%A, %B %d, %Y",       # Saturday, March 14, 2026
    "%B %dst, %Y",         # March 1st, 2026
    "%B %dnd, %Y",         # March 2nd, 2026
    "%B %drd, %Y",         # March 3rd, 2026
    "%B %dth, %Y",         # March 14th, 2026
]


class BaseScraper(ABC):
    """Abstract base class that all auction scrapers inherit from.

    Subclasses must implement:
        - source_name (property): Short display name
        - base_url (property): URL to scrape
        - scrape(): Returns list of AuctionListing
    """

    MAX_RETRIES = 2
    RETRY_DELAY = 5  # seconds

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.results: list[AuctionListing] = []

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Short name for this source, e.g. 'Bar None'."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Primary URL to scrape."""

    @abstractmethod
    def _scrape_impl(self) -> list[AuctionListing]:
        """Internal scrape logic. Subclasses implement this instead of scrape()."""

    def scrape(self) -> list[AuctionListing]:
        """Execute the scrape with retry logic. Returns listings or empty list on failure."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self.logger.info(f"Scraping {self.source_name} (attempt {attempt})...")
                results = self._scrape_impl()
                self.logger.info(f"Found {len(results)} auctions from {self.source_name}")
                return results
            except Exception as e:
                self.logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
                else:
                    self.logger.error(f"All {self.MAX_RETRIES} attempts failed for {self.source_name}")
                    return []

    def parse_date(self, raw: str) -> tuple[str, str]:
        """Parse a raw date string into (iso_date, display_date).

        Tries multiple common formats. Strips ordinal suffixes (st, nd, rd, th)
        before parsing.

        Returns:
            Tuple of (ISO date string "YYYY-MM-DD", display string "Weekday, Month Day, Year")

        Raises:
            ValueError: If no format matches
        """
        # Strip ordinal suffixes: "14th" -> "14", "1st" -> "1"
        import re
        cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', raw.strip())

        for fmt in DATE_FORMATS:
            # Also try the cleaned version against formats without ordinals
            clean_fmt = fmt.replace('st,', ',').replace('nd,', ',').replace('rd,', ',').replace('th,', ',')
            for date_str, date_fmt in [(raw.strip(), fmt), (cleaned, clean_fmt), (cleaned, fmt)]:
                try:
                    dt = datetime.strptime(date_str, date_fmt)
                    iso = dt.strftime("%Y-%m-%d")
                    display = dt.strftime("%A, %B %d, %Y")
                    return iso, display
                except ValueError:
                    continue

        raise ValueError(f"Could not parse date: '{raw}'")

    def _create_listing(self, **kwargs) -> AuctionListing:
        """Factory that auto-fills the source field."""
        kwargs.setdefault("source", self.source_name)
        return AuctionListing(**kwargs)

    @staticmethod
    def to_dict(listing: AuctionListing) -> dict:
        """Convert a listing to a JSON-serializable dict."""
        return asdict(listing)
