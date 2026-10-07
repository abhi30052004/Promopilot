"""
Configuration for parsing tzelahahar.co.il.
Adjust these selectors if the website structure changes.
"""

class ParserConfig:
    # URL patterns to identify property listing pages
    # These match common slugs for properties on the site
    PROPERTY_URL_PATTERNS = [
        "/zimmer/",
        "/cabins/",
        "/villas/",
        "/rooms/",
        "/property/",
        "/item/",
    ]
    
    # CSS Selectors for property details
    NAME_SELECTOR = "h1"
    
    # Selectors for description parts, combined with newlines
    DESCRIPTION_SELECTOR = ".description, .content, article p, .about-text"
    
    # Location usually indicated by specific classes or data attributes
    LOCATION_SELECTOR = ".location, .address, [data-location], .city"
    
    # Amenities lists
    AMENITIES_SELECTOR = ".amenities li, .facilities li, ul.features li, .features-list li"
    
    # Property type like cabin or villa
    TYPE_SELECTOR = ".property-type, .category, .type-label"
    
    # All images on the page
    IMAGES_SELECTOR = "img"
    
    # Navigation links for discovery
    NAV_LINKS_SELECTOR = "a[href]"
    
    # Fallback/validation constraints
    MIN_CONTENT_LENGTH = 500  # If HTML body is shorter than this, fallback to Playwright (e.g. heavily JS rendered)
