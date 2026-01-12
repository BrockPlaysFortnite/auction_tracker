from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re

def scrape_wca(window_position=None, return_driver=False):
    """
    Scrape Western Construction Auctions
    """
    url = "https://wca-online.com/"
    
    print(f"Opening browser and fetching WCA auction...")
    
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
        with open('debug/wca_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("Saved page to wca_debug.html")
        
        auctions = []
        
        # Get all the text from the page
        page_text = soup.get_text()
        
        # Look for "NEXT AUCTION:" in the navigation
        nav_links = soup.find_all('a')
        next_auction_link = None
        for link in nav_links:
            link_text = link.get_text()
            if 'NEXT AUCTION:' in link_text:
                next_auction_link = link
                break
        
        if next_auction_link:
            # Extract date from the link text (e.g., "NEXT AUCTION: Friday, February 6th, 2026")
            link_text = next_auction_link.get_text()
            date_match = re.search(r'NEXT AUCTION:\s*(.+)', link_text)
            auction_date = date_match.group(1).strip() if date_match else "Date not found"
        else:
            auction_date = "Date not found"
        
        # Look for the main auction info in the page content
        # Find lines that contain date and location info
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        title = "Western Construction Auctions Public Auction"
        location = "Lake Elsinore, CA"
        preview_dates = "Preview dates not found"
        
        # Search for location and preview info
        for i, line in enumerate(lines):
            # Look for the full date line
            if re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+[a-z]*,?\s+\d{4}.*Lake Elsinore', line, re.IGNORECASE):
                location_match = re.search(r'–\s*(.+)', line)
                if location_match:
                    location = location_match.group(1).strip()
            
            # Look for preview dates
            if 'Preview Dates:' in line or 'Preview Date:' in line:
                # Get the next line which should have the actual dates
                if i + 1 < len(lines):
                    preview_dates = lines[i + 1]
        
        # Get the auction preview link
        auction_link = "https://wca-online.com/auction-preview/"
        
        auction = {
            'title': title,
            'date': auction_date,
            'location': location,
            'preview': preview_dates,
            'link': auction_link,
            'source': 'Western Construction Auctions'
        }
        
        auctions.append(auction)
        
        if return_driver:
            return auctions, driver
        else:
            driver.quit()
            return auctions
        
        # Display results
        if auctions:
            print(f"\n{'='*80}")
            print(f"FOUND WCA AUCTION")
            print('='*80)
            
            for auction in auctions:
                print(f"\nTitle: {auction['title']}")
                print(f"Date: {auction['date']}")
                print(f"Location: {auction['location']}")
                print(f"Preview: {auction['preview']}")
                print(f"Link: {auction['link']}")
            
            return auctions
        else:
            print("\nNo auction found.")
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
    print("WESTERN CONSTRUCTION AUCTIONS SCRAPER")
    print("="*80)
    print()
    
    auctions = scrape_wca()
    
    print(f"\n{'='*80}")
    print(f"Scraping complete! Found {len(auctions)} auction.")
    print('='*80)