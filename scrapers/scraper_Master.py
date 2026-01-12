import sys
import os
from datetime import datetime
import re
import json
import threading
import time
from queue import Queue

# Add scrapers folder to path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scrapers'))

# Import all scraper functions
from scraper_AuctionCompany import scrape_auction_company
from scraper_BarNone import scrape_barnone
from scraper_RitchieBros import scrape_ritchie_bros
from scraper_Vantage import scrape_vantage
from scraper_WCA import scrape_wca

def parse_date(auction):
    """
    Try to parse the date string from an auction into a datetime object
    """
    date_str = auction.get('date', '')
    
    if not date_str or date_str in ['Date not found', 'Date TBD']:
        return datetime.max
    
    # Clean up the date string
    date_str_clean = date_str.strip()
    
    # Remove day of week if present (e.g., "Friday, " or "Monday, ")
    date_str_clean = re.sub(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+', '', date_str_clean, flags=re.IGNORECASE)
    
    # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
    date_str_clean = re.sub(r'(\d)(st|nd|rd|th)', r'\1', date_str_clean)
    
    # Handle date ranges - just use the first date
    if '-' in date_str_clean or '–' in date_str_clean:
        # Split on dash and take first date
        first_part = re.split(r'[-–]', date_str_clean)[0].strip()
        date_str_clean = first_part
    
    # Try to parse with different formats
    formats = [
        "%B %d, %Y",           # January 10, 2026
        "%b %d, %Y",           # Jan 10, 2026
        "%m/%d/%Y %I:%M %p",   # 02/21/2026 09:00 AM (ignore timezone)
        "%m/%d/%Y",            # 02/21/2026
        "%b %d",               # Jan 21 (assume current year)
        "%B %d",               # January 21 (assume current year)
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str_clean.split(' PST')[0].split(' EST')[0].strip(), fmt)
            # If year is missing, assume current year or next year
            if parsed.year == 1900:  # Default year when not specified
                current_year = datetime.now().year
                parsed = parsed.replace(year=current_year)
                # If the date has already passed this year, assume next year
                if parsed < datetime.now():
                    parsed = parsed.replace(year=current_year + 1)
            return parsed
        except:
            continue
    
    # Special handling for short month formats that might not have parsed
    # Try adding current year
    try:
        current_year = datetime.now().year
        test_str = f"{date_str_clean} {current_year}"
        parsed = datetime.strptime(test_str, "%b %d %Y")
        # If date has passed, try next year
        if parsed < datetime.now():
            parsed = parsed.replace(year=current_year + 1)
        return parsed
    except:
        pass
    
    # If all parsing fails, return far future date so it sorts to end
    print(f"Warning: Could not parse date '{date_str}' - sorting to end")
    return datetime.max

def run_scraper_thread(name, scraper_func, results_queue, position):
    """
    Run a scraper in a separate thread with cascading window position
    """
    print(f"[Thread {position}] Starting {name} scraper...")
    
    try:
        # Calculate cascade position (offset each window)
        x_offset = (position - 1) * 120
        y_offset = (position - 1) * 100
        
        # Pass window position to scraper and get driver back
        results, driver = scraper_func(window_position=(x_offset, y_offset), return_driver=True)
        results_queue.put((name, results, driver, None))
        print(f"[Thread {position}] ✓ {name} complete - found {len(results)} auctions")
        
    except Exception as e:
        print(f"[Thread {position}] ✗ {name} error: {e}")
        results_queue.put((name, [], None, str(e)))

def push_to_github():
    """Push updated auctions.json to GitHub"""
    import subprocess
    import webbrowser
    
    print("\n" + "="*80)
    print("Pushing updates to GitHub...")
    print("="*80)
    
    try:
        subprocess.run(["git", "add", "auctions.json"], check=True, cwd=".")
        subprocess.run(["git", "commit", "-m", "Update auction data"], check=True, cwd=".")
        subprocess.run(["git", "push"], check=True, cwd=".")
        print("✓ Successfully pushed to GitHub!")
        print("✓ Website will update in 1-2 minutes")
        print(f"✓ View at: https://brockplaysfortnite.github.io/auction_tracker/")
        
        # Open the website automatically
        webbrowser.open("https://brockplaysfortnite.github.io/auction_tracker/")

    except subprocess.CalledProcessError as e:
        print(f"✗ GitHub push failed: {e}")
        print("  (This is okay - you can push manually later)")


def run_all_scrapers():
    """
    Run all auction scrapers simultaneously and combine results
    """
    print("=" * 80)
    print("MASTER AUCTION SCRAPER - PARALLEL MODE")
    print("Running all scrapers simultaneously...")
    print("=" * 80)
    print()
    
    # List of scrapers with their names
    scrapers = [
        ("The Auction Company", scrape_auction_company),
        ("Bar None Auction", scrape_barnone),
        ("Ritchie Bros", scrape_ritchie_bros),
        ("Vantage Auctions", scrape_vantage),
        ("Western Construction Auctions", scrape_wca),
    ]
    
    # Create a queue to collect results
    results_queue = Queue()
    
    # Create and start threads
    threads = []
    print("🚀 Launching all scrapers in parallel...\n")
    
    for i, (name, scraper_func) in enumerate(scrapers, 1):
        thread = threading.Thread(
            target=run_scraper_thread, 
            args=(name, scraper_func, results_queue, i)
        )
        thread.daemon = True
        threads.append(thread)
        thread.start()
        print(f"   [{i}] {name} launched")
    
    print(f"\n{'=' * 80}")
    print("All scrapers running... Watch the browser windows cascade! 🎬")
    print('=' * 80)
    print()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Collect results from queue
    all_auctions = []
    scraper_results = {}
    errors = []
    drivers = []
    
    while not results_queue.empty():
        name, results, driver, error = results_queue.get()
        scraper_results[name] = len(results)
        all_auctions.extend(results)
        if driver:
            drivers.append(driver)
        if error:
            errors.append(f"{name}: {error}")
    
    # Close all browsers with cascade effect
    if drivers:
        print(f"\n{'=' * 80}")
        print(f"🎬 Closing all {len(drivers)} browser windows...")
        print('=' * 80)
        
        # Minimize all windows first (instant visual effect)
        for driver in drivers:
            try:
                driver.minimize_window()
            except:
                pass
        
        time.sleep(0.3)  # Brief pause
        
        # Now close them with cascade
        for i, driver in enumerate(drivers):
            try:
                driver.quit()
                if i < len(drivers) - 1:
                    time.sleep(0.25)  # Staggered delay for cascade effect
            except:
                pass
        
        print("✓ All browsers closed!")
    
    # Sort all auctions by date
    print(f"\n{'=' * 80}")
    print("Sorting all auctions by date...")
    print('=' * 80)
    
    all_auctions.sort(key=parse_date)
    
    # Display summary
    print(f"\n{'=' * 80}")
    print("SCRAPING COMPLETE - SUMMARY")
    print('=' * 80)
    print()
    
    for name in [s[0] for s in scrapers]:
        count = scraper_results.get(name, 0)
        status = "✓" if count > 0 else "✗"
        print(f"{status} {name}: {count} auctions")
    
    if errors:
        print("\n⚠ Errors encountered:")
        for error in errors:
            print(f"  - {error}")
    
    print(f"\n📊 Total auctions found: {len(all_auctions)}")
    
    # Display all auctions sorted by date
    print(f"\n{'=' * 80}")
    print("ALL UPCOMING AUCTIONS (SORTED BY DATE)")
    print('=' * 80)
    
    if all_auctions:
        for i, auction in enumerate(all_auctions, 1):
            print(f"\n{i}. {auction.get('title', 'No title')}")
            print(f"   Source: {auction.get('source', 'Unknown')}")
            print(f"   Date: {auction.get('date', 'Date not found')}")
            print(f"   Location: {auction.get('location', 'Location not found')}")
            if 'items' in auction:
                print(f"   Items: {auction['items']}")
            if 'type' in auction:
                print(f"   Type: {auction['type']}")
            print(f"   Link: {auction.get('link', 'No link')}")
    else:
        print("\nNo auctions found.")
    
    print(f"\n{'=' * 80}")
    print("DONE!")
    print('=' * 80)
    
    # Save to JSON file
    print("\n💾 Saving results to auctions.json...")
    output_data = {
        'last_updated': datetime.now().strftime("%Y-%m-%d %I:%M %p"),
        'total_auctions': len(all_auctions),
        'sources': scraper_results,
        'auctions': all_auctions
    }
    
    with open('auctions.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print("✓ Saved to auctions.json")
    print("\n🌐 Open index.html in your browser to view the results!")
    
    return all_auctions

if __name__ == "__main__":
    try:
        auctions = run_all_scrapers()
        push_to_github()
    except KeyboardInterrupt:
        print("\n\n⚠ Scraping interrupted by user")
        print("Run again to get complete results")



