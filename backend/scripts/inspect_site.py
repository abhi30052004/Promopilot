import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.parser_config import ParserConfig

def inspect(url: str):
    print(f"Inspecting {url} ...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        print(f"Status: {r.status_code}")
        if r.status_code != 200:
            return
            
        html = r.text
        print(f"Content length: {len(html)} bytes")
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Discover URLs
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        links = set()
        for a in soup.select(ParserConfig.NAV_LINKS_SELECTOR):
            href = a.get("href")
            if href:
                full_url = urljoin(base_url, href)
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    links.add(full_url)
                    
        print(f"\nDiscovered {len(links)} internal links.")
        print("Sample links:")
        for l in list(links)[:10]:
            print("  -", l)
            
        print("\nChecking property selectors on this page:")
        
        # Name
        print(f"\nName Selector ({ParserConfig.NAME_SELECTOR}):")
        name = soup.select_one(ParserConfig.NAME_SELECTOR)
        if name:
            print(f"  Matched: True, Value: '{name.get_text(strip=True)}'")
        else:
            print("  No match")
            
        # Description
        print(f"\nDescription Selector ({ParserConfig.DESCRIPTION_SELECTOR}):")
        desc = soup.select(ParserConfig.DESCRIPTION_SELECTOR)
        if desc:
            desc_text = " ".join([d.get_text(strip=True) for d in desc])
            preview = (desc_text[:100] + '...') if len(desc_text) > 100 else desc_text
            print(f"  Matched: {len(desc)} elements, Value preview: '{preview}'")
        else:
            print("  No match")
            
        # Location
        print(f"\nLocation Selector ({ParserConfig.LOCATION_SELECTOR}):")
        loc = soup.select_one(ParserConfig.LOCATION_SELECTOR)
        if loc:
            print(f"  Matched: True, Value: '{loc.get_text(strip=True)}'")
        else:
            print("  No match")

        # Type
        print(f"\nType Selector ({ParserConfig.TYPE_SELECTOR}):")
        ptype = soup.select_one(ParserConfig.TYPE_SELECTOR)
        if ptype:
            print(f"  Matched: True, Value: '{ptype.get_text(strip=True)}'")
        else:
            print("  No match")
            
        # Amenities
        print(f"\nAmenities Selector ({ParserConfig.AMENITIES_SELECTOR}):")
        amenities = soup.select(ParserConfig.AMENITIES_SELECTOR)
        if amenities:
            amenity_texts = [a.get_text(strip=True) for a in amenities]
            print(f"  Matched: {len(amenities)} elements")
            print(f"  Values: {amenity_texts[:5]}...")
        else:
            print("  No match")
            
        # Images
        print(f"\nImages Selector ({ParserConfig.IMAGES_SELECTOR}):")
        imgs = soup.select(ParserConfig.IMAGES_SELECTOR)
        if imgs:
            print(f"  Matched: {len(imgs)} elements")
            img_urls = []
            for img in imgs[:5]:
                src = img.get("src") or img.get("data-src")
                if src:
                    img_urls.append(urljoin(base_url, src))
            print("  Candidate Image URLs:")
            for img_url in img_urls:
                print(f"    - {img_url}")
        else:
            print("  No match")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://tzelahahar.co.il/"
    inspect(url)
