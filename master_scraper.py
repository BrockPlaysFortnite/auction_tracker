"""Master scraper orchestrator.

Runs all auction scrapers, combines results, sorts by date,
filters out past auctions, and writes to docs/data/auctions.json.
"""

import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta

from scrapers.base_scraper import AuctionListing
from scrapers.the_auction_company import TheAuctionCompanyScraper
from scrapers.bar_none import BarNoneScraper
from scrapers.ritchie_bros import RitchieBrosScraper
from scrapers.vantage import VantageScraper
from scrapers.wca import WCAScraper
from scrapers.gac import GACScraper
from scrapers.jjkane import JJKaneScraper

SCRAPERS = [
    TheAuctionCompanyScraper,
    BarNoneScraper,
    RitchieBrosScraper,
    VantageScraper,
    WCAScraper,
    GACScraper,
    JJKaneScraper,
]

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "docs", "data", "auctions.json")
WEBSITE_OUTPUT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "SealcoatSAS Website",
    "sealcoatsas-website", "public", "data", "auctions.json"
)


def run_all_scrapers() -> list[AuctionListing]:
    """Run every registered scraper and collect results."""
    all_auctions = []
    succeeded = 0
    failed = 0

    for scraper_cls in SCRAPERS:
        scraper = scraper_cls()
        try:
            results = scraper.scrape()
            all_auctions.extend(results)
            succeeded += 1
        except Exception as e:
            logging.error(f"{scraper.source_name} FAILED: {e}")
            failed += 1

    logging.info(f"Scraping complete: {succeeded}/{succeeded + failed} scrapers succeeded, "
                 f"{len(all_auctions)} total auctions found")
    return all_auctions


def deduplicate(auctions: list[AuctionListing]) -> list[AuctionListing]:
    """Remove duplicate auctions based on URL."""
    seen = set()
    unique = []
    for a in auctions:
        key = a.url.rstrip("/")
        if key not in seen:
            seen.add(key)
            unique.append(a)
    removed = len(auctions) - len(unique)
    if removed:
        logging.info(f"Removed {removed} duplicate auctions")
    return unique


def filter_and_sort(auctions: list[AuctionListing]) -> list[AuctionListing]:
    """Remove past auctions, deduplicate, and sort by date ascending."""
    grace = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    cutoff = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    upcoming = [a for a in auctions if grace <= a.date <= cutoff]
    upcoming = deduplicate(upcoming)
    upcoming.sort(key=lambda a: a.date)

    removed = len(auctions) - len(upcoming)
    if removed:
        logging.info(f"Filtered out {removed} past/duplicate auctions")

    return upcoming


def write_json(auctions: list[AuctionListing]) -> None:
    """Write auction data to the JSON file consumed by the frontend."""
    output = {
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "total_count": len(auctions),
        "auctions": [asdict(a) for a in auctions],
    }

    for path in [OUTPUT_PATH, WEBSITE_OUTPUT_PATH]:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            logging.info(f"Wrote {len(auctions)} auctions to {path}")
        except OSError as e:
            logging.warning(f"Could not write to {path}: {e}")


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    logging.info("=" * 50)
    logging.info("Auction Tracker - Starting scrape run")
    logging.info("=" * 50)

    all_auctions = run_all_scrapers()
    upcoming = filter_and_sort(all_auctions)
    write_json(upcoming)

    logging.info("=" * 50)
    logging.info(f"Done! {len(upcoming)} upcoming auctions saved.")
    logging.info("=" * 50)


if __name__ == "__main__":
    main()
