from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re

def scrape_vantage(window_position=None, return_driver=False):
    """
    Scrape Vantage Auctions
    """
    url = "https://vantageauctions.com/"
    
    print(f"Opening browser and fetching Vantage Auctions...")
    
    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        # Initialize driver
        print("Setting up Chrome driver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        if window_position:
            driver.set_window_position(window_position[0], window_position[1])
            driver.set_window_size(1000, 800)
        
        # Go to page
        driver.get(url)
        
        # Wait for content to load
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Get page source
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Save for debugging
        with open('debug/vantage_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("Saved page to vantage_debug.html")
        
        auctions = []
        
        # Get all the text from the page
        page_text = soup.get_text()
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        # Look for "Upcoming Auction:" text
        upcoming_date = "Date not found"
        for i, line in enumerate(lines):
            if 'Upcoming Auction:' in line:
                # The date should be in the same line or next line
                date_match = re.search(r'Upcoming Auction:\s*(.+)', line)
                if date_match:
                    upcoming_date = date_match.group(1).strip()
                elif i + 1 < len(lines):
                    upcoming_date = lines[i + 1]
                break
        
        # Look for any other auction info (like the Land Auction)
        land_auction_date = None
        for i, line in enumerate(lines):
            if 'Land Auction' in line:
                # Try to extract date from the same or next line
                date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+[-–]\d+,?\s+\d{4}', line)
                if date_match:
                    land_auction_date = date_match.group(0)
                elif i + 1 < len(lines):
                    date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+[-–]\d+,?\s+\d{4}', lines[i + 1])
                    if date_match:
                        land_auction_date = date_match.group(0)
                break
        
        # Get location from address
        location = "Lake Elsinore, CA"
        
        # Main auction
        if upcoming_date != "Date not found":
            auction = {
                'title': 'Vantage Auctions - Equipment Auction',
                'date': upcoming_date,
                'location': location,
                'link': 'https://vantageauctions.com/auctions/',
                'source': 'Vantage Auctions'
            }
            auctions.append(auction)
        
        # Land auction if found
        if land_auction_date:
            land_auction = {
                'title': 'Vantage Auctions - Land Auction',
                'date': land_auction_date,
                'location': location,
                'link': 'https://www.proxibid.com/Vantage-Auctions/auction-house/10681',
                'source': 'Vantage Auctions'
            }
            auctions.append(land_auction)
        
            if return_driver:
                return auctions, driver
            else:
                driver.quit()
                return auctions
        
        # Display results
        if auctions:
            print(f"\n{'='*80}")
            print(f"FOUND {len(auctions)} VANTAGE AUCTION(S)")
            print('='*80)
            
            for i, auction in enumerate(auctions, 1):
                print(f"\n{i}. {auction['title']}")
                print(f"   Date: {auction['date']}")
                print(f"   Location: {auction['location']}")
                print(f"   Link: {auction['link']}")
            
            return auctions
        else:
            print("\nNo auctions found.")
            return []
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        if 'driver' in locals():
            driver.quit()
        return []

if __name__ == "__main__":
    print("="*80)
    print("VANTAGE AUCTIONS SCRAPER")
    print("="*80)
    print()
    
    auctions = scrape_vantage()
    
    print(f"\n{'='*80}")
    print(f"Scraping complete! Found {len(auctions)} auction(s).")
    print('='*80)