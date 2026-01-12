from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re

def scrape_auction_company(window_position=None, return_driver=False):
    """
    Scrape auctions from theauctioncompany.net
    """
    url = "https://bid.theauctioncompany.net/auctions/"
    
    print(f"Fetching auctions from {url}...")
    
    # Set headers to look like a real browser
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set window position if provided
        if window_position:
            driver.set_window_position(window_position[0], window_position[1])
            driver.set_window_size(1000, 800)
        
        # Make the request
        driver.get(url)
        
        # Wait for content to load
        time.sleep(10)
        
        # Parse the HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Save debug file
        with open('debug/TheAuctionCO_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("Saved page to debug/TheAuctionCO_debug.html")
        
        # Find all auction listings
        auction_headings = soup.find_all('h6')
        
        auctions = []
        
        for heading in auction_headings:
            link_tag = heading.find('a')
            if link_tag and link_tag.get('href'):
                try:
                    # Get the parent div that contains all auction info
                    parent_div = heading.find_parent('div')
                    
                    # Extract sale number
                    sale_no_tag = link_tag.find('span', class_='sale-no')
                    sale_no = sale_no_tag.text.strip() if sale_no_tag else "N/A"
                    
                    # Get raw title text
                    raw_title = link_tag.get_text(separator=' ', strip=True)
                    
                    # Remove the sale number from the beginning
                    if sale_no != "N/A" and raw_title.startswith(sale_no):
                        raw_title = raw_title[len(sale_no):].strip()
                    
                    # Extract location from title (look for city names)
                    location = "Location TBD"
                    location_match = re.search(r'(Colton|Corona|Riverside|San Bernardino|Los Angeles|Fontana|Perris)', raw_title, re.IGNORECASE)
                    if location_match:
                        location = f"{location_match.group(1)}, CA"
                    
                    # Extract ring number if present
                    ring_match = re.search(r'Ring\s+(\d+)', raw_title, re.IGNORECASE)
                    ring_num = f"Ring {ring_match.group(1)}" if ring_match else ""
                    
                    # Create clean title
                    if location != "Location TBD":
                        city = location.split(',')[0]
                        if ring_num:
                            title = f"{city} Equipment Auction ({ring_num})"
                        else:
                            title = f"{city} Equipment Auction"
                    else:
                        title = "Equipment Auction"
                        if ring_num:
                            title += f" ({ring_num})"
                    
                    # Extract link
                    link = link_tag['href']
                    if not link.startswith('http'):
                        link = f"https://bid.theauctioncompany.net{link}"
                    
                    # Extract date from the span with class 'auction_list_start_date'
                    date_span = parent_div.find('span', class_='auction_list_start_date')
                    auction_date = date_span.text.strip() if date_span else "Date not found"
                    
                    # Check if date is in the past - if so, try to parse from title
                    if auction_date != "Date not found":
                        try:
                            date_obj = datetime.strptime(auction_date.split(' PST')[0].split(' EST')[0].strip(), "%m/%d/%Y %I:%M %p")
                            # If date is in the past, it's probably wrong - parse from title instead
                            if date_obj < datetime.now():
                                print(f"Warning: Date {auction_date} is in the past, parsing from title...")
                                # Try to extract date from title (e.g., "SATURDAY, FEBRUARY 21ST")
                                date_match = re.search(r'(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),?\s+(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d+)(ST|ND|RD|TH)?', raw_title, re.IGNORECASE)
                                if date_match:
                                    month = date_match.group(2)
                                    day = date_match.group(3)
                                    current_year = datetime.now().year
                                    # Try to parse the date
                                    try:
                                        parsed_date = datetime.strptime(f"{month} {day} {current_year}", "%B %d %Y")
                                        # If this date is also in the past, try next year
                                        if parsed_date < datetime.now():
                                            parsed_date = datetime.strptime(f"{month} {day} {current_year + 1}", "%B %d %Y")
                                        auction_date = parsed_date.strftime("%m/%d/%Y 09:00 AM PST")
                                        print(f"  -> Parsed as: {auction_date}")
                                    except:
                                        pass  # Keep original date if parsing fails
                        except:
                            pass  # Keep original date if parsing fails
                    
                    # Extract status
                    status_span = parent_div.find('span', class_='auction-upcoming')
                    if not status_span:
                        status_span = parent_div.find('span', class_='auction-live')
                    status = status_span.text.strip() if status_span else "N/A"
                    
                    # Extract number of lots
                    lots_text = parent_div.get_text()
                    lots = "N/A"
                    if "Lots:" in lots_text:
                        lots_start = lots_text.find("Lots:") + 5
                        lots_end = lots_text.find("\n", lots_start)
                        lots = lots_text[lots_start:lots_end].strip()
                    
                    auction = {
                        'sale_no': sale_no,
                        'title': title,
                        'date': auction_date,
                        'location': location,
                        'status': status,
                        'lots': lots,
                        'link': link,
                        'source': 'The Auction Company'
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
            print(f"\nFound {len(auctions)} upcoming auctions")
            for i, auction in enumerate(auctions, 1):
                print(f"{i}. Sale #{auction['sale_no']}: {auction['title']}")
                print(f"   Date: {auction['date']}")
                print(f"   Location: {auction['location']}")
            
            return auctions
        else:
            print("\nNo auctions found.")
            return []
        
    except Exception as e:
        print(f"\nError: {e}")
        if 'driver' in locals():
            driver.quit()
        return []

if __name__ == "__main__":
    print("="*80)
    print("AUCTION SCRAPER - THE AUCTION COMPANY")
    print("="*80)
    print()
    
    auctions = scrape_auction_company()
    
    print(f"\n{'='*80}")
    print(f"Scraping complete! Found {len(auctions)} auctions.")
    print('='*80)