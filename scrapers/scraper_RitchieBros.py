from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re

def scrape_ritchie_bros(window_position=None, return_driver=False):
    """
    Scrape auctions from Ritchie Bros for CA, AZ, NV
    """
    url = "https://www.rbauction.com/heavy-equipment-auctions?rbaLocationLevelThree=US-CA%2CUS-AZ%2CUS-NV"
    
    print(f"Opening browser and fetching Ritchie Bros auctions...")
    
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
        
        # Wait for auction cards to load
        print("Waiting for auctions to load...")
        time.sleep(8)
        
        # Scroll down to load more auctions
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Get page source
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Save for debugging
        with open('debug/ritchie_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("Saved page to ritchie_debug.html")
        
        auctions = []
        
        # Find all h5 tags with MUI classes (these contain the auction titles)
        auction_titles = soup.find_all('h5', class_=lambda x: x and 'MuiTypography-h5' in x)
        
        print(f"Found {len(auction_titles)} auction title elements")
        
        for title_elem in auction_titles:
            try:
                title = title_elem.get_text(strip=True)
                
                # Find the parent card container
                card = title_elem.find_parent('a')
                if not card:
                    continue
                
                # Get the link
                link = card.get('href', '')
                if link and not link.startswith('http'):
                    link = f"https://www.rbauction.com{link}"
                
                # Find all text within this card
                card_text = card.get_text(separator='|', strip=True)
                parts = [p.strip() for p in card_text.split('|') if p.strip()]
                
                # Extract date - look for month names at start of parts
                date = "Date not found"
                for part in parts:
                    if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+', part):
                        date = part
                        break
                
                # Extract location - look for parts with state abbreviations
                location = "Location not found"
                for part in parts:
                    if re.search(r',\s*(CA|AZ|NV)(\s|$)', part):
                        location = part
                        break
                
                # Extract item count - look for "Items" or "Item"
                items = "N/A"
                for part in parts:
                    if 'Item' in part and ('coming soon' in part.lower() or 'so far' in part.lower() or any(c.isdigit() for c in part)):
                        items = part
                        break
                
                # Extract auction type
                auction_type = "N/A"
                if 'Timed auction' in card_text:
                    auction_type = "Timed"
                elif 'Live auction' in card_text:
                    auction_type = "Live"
                
                # Only add if we have a valid link and title
                if link and title and 'heavy-equipment-auctions' in link:
                    auction = {
                        'title': title,
                        'date': date,
                        'location': location,
                        'items': items,
                        'type': auction_type,
                        'link': link,
                        'source': 'Ritchie Bros'
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
        
        # Display results
        if auctions:
            print(f"\n{'='*80}")
            print(f"FOUND {len(auctions)} RITCHIE BROS AUCTIONS")
            print('='*80)
            
            for i, auction in enumerate(auctions, 1):
                print(f"\n{i}. {auction['title']}")
                print(f"   Date: {auction['date']}")
                print(f"   Location: {auction['location']}")
                print(f"   Items: {auction['items']}")
                print(f"   Type: {auction['type']}")
                print(f"   Link: {auction['link']}")
            
            return auctions
        else:
            print("\nNo auctions found. Check ritchie_debug.html to see page structure.")
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
    print("RITCHIE BROS AUCTION SCRAPER")
    print("="*80)
    print()
    
    auctions = scrape_ritchie_bros()
    
    print(f"\n{'='*80}")
    print(f"Scraping complete! Found {len(auctions)} auctions.")
    print('='*80)