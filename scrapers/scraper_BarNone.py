from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime

def scrape_barnone(window_position=None, return_driver=False):
    """
    Scrape Bar None Auctions - CA locations only
    """
    url = "https://barnoneauction.com/auctions/"
    
    print(f"Opening browser and fetching Bar None Auctions...")
    
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
        print("Waiting for auctions to load...")
        time.sleep(5)
        
        # Get page source
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Save for debugging
        with open('debug/barnone_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("Saved page to barnone_debug.html")
        
        auctions = []
        
        # Find all post cards (each auction is in a div with class elementskit-post-card)
        post_cards = soup.find_all('div', class_='elementskit-post-card')
        
        print(f"Found {len(post_cards)} auction cards")
        
        for card in post_cards:
            try:
                # Find the date in the entry-title
                title_elem = card.find('h2', class_='entry-title')
                if not title_elem:
                    continue
                
                date_link = title_elem.find('a')
                if not date_link:
                    continue
                
                date_text = date_link.get_text(strip=True)
                auction_url = date_link.get('href', '')
                
                # Find the location in post-cat span
                location_span = card.find('span', class_='post-cat')
                location = "Location not found"
                
                if location_span:
                    location_link = location_span.find('a')
                    if location_link:
                        location = location_link.get_text(strip=True)
                
                # Only include California locations
                if 'California' not in location:
                    continue
                
                # Parse the date to check if it's upcoming
                try:
                    auction_date = datetime.strptime(date_text, "%B %d, %Y")
                    now = datetime.now()
    
                    # Calculate days until auction
                    days_until = (auction_date - now).days
                    
                    # Only include auctions within the next 60 days
                    if days_until < 0 or days_until > 60:
                        continue
                except:
                    pass  # If we can't parse, include it anyway
                
                auction = {
                    'title': f'Bar None Auction - {location}',
                    'date': date_text,
                    'location': location,
                    'link': auction_url,
                    'source': 'Bar None Auction'
                }
                
                auctions.append(auction)
                
            except Exception as e:
                print(f"Error parsing auction: {e}")
                continue
        
            if return_driver:
                return auctions, driver
            else:
                driver.quit()
                return auctions
        
        # Remove duplicates (same date and location)
        seen = set()
        unique_auctions = []
        for auction in auctions:
            key = (auction['date'], auction['location'])
            if key not in seen:
                seen.add(key)
                unique_auctions.append(auction)
        
        # Sort by date
        def parse_date(auction):
            try:
                return datetime.strptime(auction['date'], "%B %d, %Y")
            except:
                return datetime.max
        
        unique_auctions.sort(key=parse_date)
        
        # Display results
        if unique_auctions:
            print(f"\n{'='*80}")
            print(f"FOUND {len(unique_auctions)} BAR NONE AUCTIONS (CA ONLY)")
            print('='*80)
            
            for i, auction in enumerate(unique_auctions, 1):
                print(f"\n{i}. {auction['title']}")
                print(f"   Date: {auction['date']}")
                print(f"   Location: {auction['location']}")
                print(f"   Link: {auction['link']}")
            
            return unique_auctions
        else:
            print("\nNo California auctions found.")
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
    print("BAR NONE AUCTION SCRAPER")
    print("="*80)
    print()
    
    auctions = scrape_barnone()
    
    print(f"\n{'='*80}")
    print(f"Scraping complete! Found {len(auctions)} CA auctions.")
    print('='*80)