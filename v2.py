#!/usr/bin/env python3

import random
import time
import re
import threading
import requests
import urllib3
import queue
import asyncio
import os
import tempfile
import argparse
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ⚠️ SET TO False TO DISABLE CURL_CFFI AND USE STANDARD REQUESTS
USE_CURL_CFFI = False  # DISABLED - causes connection issues

# 🧦 SOCKS PROXY SUPPORT - requires PySocks
# Install with: pip install PySocks requests[socks]
try:
    import socks
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False
    print("⚠️ PySocks not installed. SOCKS proxies won't work.")
    print("💡 Install with: pip install PySocks requests[socks]")

# Proxyless mode toggle (can be changed via /toggle command in bot)
USE_PROXYLESS_IN_DUAL_MODE = True  # ON by default, use /toggle to turn off if IP is blocked

# Try to import curl_cffi for browser impersonation (MUCH better for bypassing detection)
try:
    from curl_cffi import requests as curl_requests
    if USE_CURL_CFFI:
        CURL_CFFI_AVAILABLE = True
        print("✅ curl_cffi loaded - browser impersonation enabled!")
    else:
        CURL_CFFI_AVAILABLE = False
        print("⚠️ curl_cffi DISABLED - using standard requests (more stable)")
except ImportError:
    curl_requests = None
    CURL_CFFI_AVAILABLE = False
    print("⚠️ curl_cffi not found - using standard requests")
    print("💡 Install with: pip install curl_cffi")

# Browser impersonation options for curl_cffi
BROWSER_IMPERSONATE = ["chrome110", "chrome116", "chrome120", "edge101", "safari15_5"]

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("python-telegram-bot not found")
    print("💡 Install with: pip install python-telegram-bot nigga")

urllib3.disable_warnings()

BOT_TOKEN = "8759590862:AAGX-5dclsJluO55YS-lXA95p_OdUPg2Lu0"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/121.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) Chrome/121.0.0.0",
]

SEARCH_ENGINES = [
    {
        'name': 'Yahoo',
        'url': 'https://search.yahoo.com/search',
        'param': 'p',
        'weight': 0.35
    },
    {
        'name': 'DuckDuckGo',
        'url': 'https://html.duckduckgo.com/html/',
        'param': 'q',
        'weight': 0.25
    },
    {
        'name': 'Brave',
        'url': 'https://search.brave.com/search',
        'param': 'q',
        'weight': 0.20
    },
    {
        'name': 'SearX-1',
        'url': 'https://searx.be/search',
        'param': 'q',
        'weight': 0.10
    },
    {
        'name': 'SearX-2',
        'url': 'https://search.sapti.me/search',
        'param': 'q',
        'weight': 0.10
    }
]

# Proxyless search engines - CLEANED UP (removed dead/broken ones)
PROXYLESS_ENGINES = [
    # Yahoo FIRST - most reliable!
    {
        'name': 'Yahoo',
        'url': 'https://search.yahoo.com/search',
        'param': 'p',
    },
    # Brave Search - EXCELLENT for Shopify stores
    {
        'name': 'Brave',
        'url': 'https://search.brave.com/search',
        'param': 'q',
        'headers': {'Accept-Encoding': 'gzip, deflate'},  # No brotli
    },
    # SearX instances - ONLY working ones
    {
        'name': 'SearX-1',
        'url': 'https://searx.be/search',
        'param': 'q',
    },
    {
        'name': 'SearX-2', 
        'url': 'https://search.sapti.me/search',
        'param': 'q',
    },
    {
        'name': 'SearX-3',
        'url': 'https://searx.tiekoetter.com/search',
        'param': 'q',
    },
    {
        'name': 'SearX-6',
        'url': 'https://search.ononoki.org/search',
        'param': 'q',
    },
    {
        'name': 'SearX-7',
        'url': 'https://searx.nixnet.services/search',
        'param': 'q',
    },
    {
        'name': 'SearX-9',
        'url': 'https://search.mdosch.de/search',
        'param': 'q',
    },
    {
        'name': 'SearX-13',
        'url': 'https://priv.au/search',
        'param': 'q',
    },
    {
        'name': 'SearX-15',
        'url': 'https://etsi.me/search',
        'param': 'q',
    },
    # Alternative search engines
    {
        'name': 'Yandex',
        'url': 'https://yandex.com/search/',
        'param': 'text',
    },
    {
        'name': 'Qwant',
        'url': 'https://www.qwant.com/',
        'param': 'q',
    },
]

# Mode constants
MODE_PROXY_ONLY = 'proxy'
MODE_PROXYLESS = 'proxyless'
MODE_BOTH = 'both'

# Store user's selected mode
user_modes = {}

# ============================================================
# FILTER: Search for products under $5
# ============================================================
CHEAP_PRODUCT_QUERIES = [
    # Direct price searches
    'under 5 dollars',
    'under $5',
    'less than 5 dollars',
    'less than $5',
    '5 dollar',
    '5 dollars',
    '5$',
    '$5',
    '5.00',
    'under 5.00',
    'under 5$',
    'price 5',
    'price $5',
    'cheap 5',
    '5 dollar item',
    '5 dollar product',
    '5 dollar store',
    'under 5 dollar',
    'under 5 dollars',
    '5 and under',
    '5 or less',
    '5 dollars or less',
    '$5 and under',
    '$5 or less',
    '5 dollar deals',
    '5 dollar bargains',
    '5 dollar discount',
    'budget 5',
    'affordable 5',
    '5 dollar cheap',
    '5 dollar budget',
    '5 dollar low price',
    '5 dollar sale',
    '5 dollar clearance',
    '5 dollar value',
    '5 dollar special',
    '5 dollar offer',
    '5 dollar promo',
    '5 dollar deal',
    '5 dollar steal',
    '5 dollar find',
    '5 dollar gem',
    '5 dollar treasure',
    '5 dollar surprise',
    '5 dollar fun',
    '5 dollar gift',
    '5 dollar treat',
    '5 dollar splurge',
    '5 dollar buy',
    '5 dollar shop',
    '5 dollar store',
    '5 dollar market',
    '5 dollar mart',
    '5 dollar bazaar',
    '5 dollar emporium',
    '5 dollar outlet',
    '5 dollar warehouse',
    '5 dollar superstore',
    '5 dollar megastore',
    '5 dollar hypermarket',
    '5 dollar department store',
    '5 dollar chain',
    '5 dollar retail',
    '5 dollar ecommerce',
    '5 dollar online store',
    '5 dollar web store',
    '5 dollar virtual store',
    '5 dollar cyber store',
    '5 dollar digital store',
    '5 dollar mobile store',
    '5 dollar app store',
    '5 dollar marketplace',
    '5 dollar platform',
    '5 dollar site',
    '5 dollar website',
    '5 dollar portal',
    '5 dollar hub',
    '5 dollar center',
    '5 dollar square',
    '5 dollar place',
    '5 dollar spot',
    '5 dollar corner',
    '5 dollar nook',
    '5 dollar haven',
    '5 dollar paradise',
    '5 dollar heaven',
    '5 dollar wonderland',
    '5 dollar world',
    '5 dollar universe',
    '5 dollar galaxy',
    '5 dollar cosmos',
    '5 dollar planet',
    '5 dollar star',
    '5 dollar sun',
    '5 dollar moon',
    '5 dollar earth',
    '5 dollar land',
    '5 dollar island',
    '5 dollar oasis',
    '5 dollar retreat',
    '5 dollar escape',
    '5 dollar hideaway',
    '5 dollar sanctuary',
    '5 dollar haven',
    '5 dollar refuge',
    '5 dollar shelter',
    '5 dollar harbor',
    '5 dollar port',
    '5 dollar dock',
    '5 dollar pier',
    '5 dollar wharf',
    '5 dollar marina',
    '5 dollar bay',
    '5 dollar cove',
    '5 dollar inlet',
    '5 dollar fjord',
    '5 dollar strait',
    '5 dollar channel',
    '5 dollar sound',
    '5 dollar passage',
    '5 dollar way',
    '5 dollar path',
    '5 dollar trail',
    '5 dollar route',
    '5 dollar road',
    '5 dollar street',
    '5 dollar avenue',
    '5 dollar boulevard',
    '5 dollar drive',
    '5 dollar lane',
    '5 dollar court',
    '5 dollar place',
    '5 dollar square',
    '5 dollar circle',
    '5 dollar loop',
    '5 dollar terrace',
    '5 dollar way',
    '5 dollar park',
    '5 dollar garden',
    '5 dollar grove',
    '5 dollar wood',
    '5 dollar forest',
    '5 dollar mountain',
    '5 dollar hill',
    '5 dollar valley',
    '5 dollar plain',
    '5 dollar field',
    '5 dollar meadow',
    '5 dollar prairie',
    '5 dollar savanna',
    '5 dollar desert',
    '5 dollar mesa',
    '5 dollar canyon',
    '5 dollar ridge',
    '5 dollar peak',
    '5 dollar summit',
    '5 dollar crest',
    '5 dollar point',
    '5 dollar cape',
    '5 dollar shore',
    '5 dollar beach',
    '5 dollar coast',
    '5 dollar tide',
    '5 dollar wave',
    '5 dollar surf',
    '5 dollar sand',
    '5 dollar stone',
    '5 dollar rock',
    '5 dollar gem',
    '5 dollar crystal',
    '5 dollar jewel',
    '5 dollar treasure',
    '5 dollar gold',
    '5 dollar silver',
    '5 dollar platinum',
    '5 dollar diamond',
    '5 dollar ruby',
    '5 dollar sapphire',
    '5 dollar emerald',
    '5 dollar pearl',
    '5 dollar opal',
    '5 dollar topaz',
    '5 dollar amethyst',
    '5 dollar turquoise',
    '5 dollar jade',
    '5 dollar coral',
    '5 dollar amber',
    '5 dollar ivory',
    '5 dollar bone',
    '5 dollar horn',
    '5 dollar shell',
    '5 dollar feather',
    '5 dollar fur',
    '5 dollar leather',
    '5 dollar silk',
    '5 dollar wool',
    '5 dollar cotton',
    '5 dollar linen',
    '5 dollar hemp',
    '5 dollar bamboo',
    '5 dollar wood',
    '5 dollar metal',
    '5 dollar steel',
    '5 dollar iron',
    '5 dollar copper',
    '5 dollar brass',
    '5 dollar bronze',
    '5 dollar tin',
    '5 dollar lead',
    '5 dollar zinc',
    '5 dollar nickel',
    '5 dollar chrome',
    '5 dollar titanium',
    '5 dollar aluminum',
    '5 dollar glass',
    '5 dollar plastic',
    '5 dollar rubber',
    '5 dollar foam',
    '5 dollar paper',
    '5 dollar cardboard',
    '5 dollar cardstock',
    '5 dollar craft',
    '5 dollar art',
    '5 dollar paint',
    '5 dollar brush',
    '5 dollar pencil',
    '5 dollar pen',
    '5 dollar marker',
    '5 dollar crayon',
    '5 dollar chalk',
    '5 dollar pastel',
    '5 dollar charcoal',
    '5 dollar ink',
    '5 dollar dye',
    '5 dollar pigment',
    '5 dollar color',
    '5 dollar hue',
    '5 dollar tint',
    '5 dollar shade',
    '5 dollar tone',
    '5 dollar glow',
    '5 dollar shine',
    '5 dollar sparkle',
    '5 dollar glitter',
    '5 dollar shimmer',
    '5 dollar sheen',
    '5 dollar luster',
    '5 dollar gleam',
    '5 dollar radiance',
    '5 dollar brilliance',
    '5 dollar effulgence',
    '5 dollar refulgence',
    '5 dollar luminosity',
    '5 dollar incandescence',
    '5 dollar phosphorescence',
    '5 dollar fluorescence',
    '5 dollar luminescence',
    '5 dollar iridescence',
    '5 dollar opalescence',
    '5 dollar pearlescence',
    '5 dollar chatoyance',
    '5 dollar aventurescence',
    '5 dollar labradorescence',
    '5 dollar adularescence',
    '5 dollar play of color',
    '5 dollar color play',
    '5 dollar fire',
    '5 dollar flash',
    '5 dollar spark',
    '5 dollar glint',
    '5 dollar twinkle',
    '5 dollar shimmer',
    '5 dollar glimmer',
    '5 dollar glisten',
    '5 dollar glitter',
    '5 dollar sparkle',
    '5 dollar shine',
    '5 dollar sheen',
    '5 dollar luster',
    '5 dollar gleam',
    '5 dollar glow',
    '5 dollar radiance',
    '5 dollar brilliance',
    '5 dollar effulgence',
    '5 dollar refulgence',
    '5 dollar luminosity',
    '5 dollar incandescence',
    '5 dollar phosphorescence',
    '5 dollar fluorescence',
    '5 dollar luminescence',
    '5 dollar iridescence',
    '5 dollar opalescence',
    '5 dollar pearlescence',
    '5 dollar chatoyance',
    '5 dollar aventurescence',
    '5 dollar labradorescence',
    '5 dollar adularescence',
    '5 dollar play of color',
    '5 dollar color play',
    '5 dollar fire',
    '5 dollar flash',
    '5 dollar spark',
    '5 dollar glint',
    '5 dollar twinkle',
    
    # With site:myshopify.com
    'site:myshopify.com under 5',
    'site:myshopify.com under $5',
    'site:myshopify.com less than 5',
    'site:myshopify.com less than $5',
    'site:myshopify.com 5 dollar',
    'site:myshopify.com 5 dollars',
    'site:myshopify.com 5$',
    'site:myshopify.com $5',
    'site:myshopify.com 5.00',
    'site:myshopify.com cheap',
    'site:myshopify.com budget',
    'site:myshopify.com affordable',
    'site:myshopify.com low price',
    'site:myshopify.com clearance',
    'site:myshopify.com sale',
    'site:myshopify.com discount',
    'site:myshopify.com bargain',
    'site:myshopify.com value',
    'site:myshopify.com deals',
    'site:myshopify.com dollar store',
    'site:myshopify.com under 5 dollars',
    'site:myshopify.com 5 and under',
    'site:myshopify.com 5 or less',
    'site:myshopify.com budget friendly',
    'site:myshopify.com cheap items',
    'site:myshopify.com affordable items',
    'site:myshopify.com low cost',
    'site:myshopify.com economical',
    'site:myshopify.com wallet friendly',
    'site:myshopify.com pocket friendly',
    'site:myshopify.com penny',
    'site:myshopify.com cents',
    'site:myshopify.com bargain bin',
    'site:myshopify.com clearance sale',
    'site:myshopify.com closeout',
    'site:myshopify.com liquidation',
    'site:myshopify.com overstock',
    'site:myshopify.com reduced price',
    'site:myshopify.com marked down',
    'site:myshopify.com price drop',
    'site:myshopify.com super cheap',
    'site:myshopify.com mega cheap',
    'site:myshopify.com ultra cheap',
    'site:myshopify.com incredibly cheap',
    'site:myshopify.com ridiculously cheap',
    'site:myshopify.com amazingly cheap',
    'site:myshopify.com dirt cheap',
    'site:myshopify.com rock bottom',
    'site:myshopify.com best price',
    'site:myshopify.com lowest price',
    'site:myshopify.com unbeatable price',
    'site:myshopify.com exceptional value',
    'site:myshopify.com great value',
    'site:myshopify.com excellent value',
]

# ============================================================
# FILTER: Site validation and price checking
# ============================================================

# Cache for validated sites (working, has cheap products)
_validated_sites_cache = {}
_validated_sites_lock = threading.Lock()
# Cache for sites that failed validation
_failed_sites_cache = set()
_failed_sites_lock = threading.Lock()

# Price check patterns (looking for prices under $5)
PRICE_PATTERNS = [
    # Dollar amounts under 5
    r'\$[0-4]\.\d{2}',  # $0.00 to $4.99
    r'\$[0-4]\.\d{2}',
    r'\$[0-4]\.[0-9]{2}',
    r'\$[0-4]\.[0-9]{2}',
    r'\$[0-4]\.\d+',
    r'\$[0-4]\s*\.\s*\d+',
    r'USD\s*[0-4]\.\d{2}',
    r'USD\s*[0-4]\.[0-9]{2}',
    r'US\s*\$\s*[0-4]\.\d{2}',
    r'US\s*\$\s*[0-4]\.[0-9]{2}',
    r'price\s*[0-4]\.\d{2}',
    r'price\s*[0-4]\.[0-9]{2}',
    r'only\s*[0-4]\.\d{2}',
    r'only\s*[0-4]\.[0-9]{2}',
    r'just\s*[0-4]\.\d{2}',
    r'just\s*[0-4]\.[0-9]{2}',
    r'for\s*[0-4]\.\d{2}',
    r'for\s*[0-4]\.[0-9]{2}',
    r'[0-4]\.\d{2}\s*USD',
    r'[0-4]\.[0-9]{2}\s*USD',
    r'[0-4]\.\d{2}\s*\$',
    r'[0-4]\.[0-9]{2}\s*\$',
    r'[0-4]\.\d{2}\s*dollars',
    r'[0-4]\.[0-9]{2}\s*dollars',
    r'[0-4]\.\d{2}\s*usd',
    r'[0-4]\.[0-9]{2}\s*usd',
    # Also look for "under 5" or "under $5" phrases
    r'under\s*[0-4]\.\d{2}',
    r'under\s*[0-4]\.[0-9]{2}',
    r'under\s*\$\s*[0-4]\.\d{2}',
    r'under\s*\$\s*[0-4]\.[0-9]{2}',
    r'less\s*than\s*[0-4]\.\d{2}',
    r'less\s*than\s*[0-4]\.[0-9]{2}',
    r'less\s*than\s*\$\s*[0-4]\.\d{2}',
    r'less\s*than\s*\$\s*[0-4]\.[0-9]{2}',
    # Also look for prices like 4.99, 4.95, 4.50, 3.99, etc.
    r'[0-4]\.[0-9]{2}',
    r'[0-4]\.[0-9]{2}',
    r'[0-4]\.[0-9]{2}',
]

def check_site_working(site_url, timeout=15):
    """Check if a Shopify site is working (returns 200 OK)"""
    try:
        # Parse domain from URL
        parsed = urllib.parse.urlparse(site_url)
        domain = parsed.netloc
        
        # Try to get the main page
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(
            site_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            verify=False
        )
        
        # Check if the site is accessible
        if response.status_code == 200:
            return True, response.text
        elif 300 <= response.status_code < 400:
            # Redirect - follow it
            try:
                redirect_url = response.headers.get('Location', '')
                if redirect_url:
                    response2 = requests.get(
                        redirect_url,
                        headers=headers,
                        timeout=timeout,
                        allow_redirects=True,
                        verify=False
                    )
                    if response2.status_code == 200:
                        return True, response2.text
            except:
                pass
            return False, None
        else:
            return False, None
            
    except Exception as e:
        return False, None

def check_has_cheap_products(html, site_url):
    """Check if the site has products under $5"""
    if not html:
        return False
    
    # First check: Look for price patterns in the HTML
    price_patterns_found = []
    
    for pattern in PRICE_PATTERNS:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches:
            price_patterns_found.extend(matches)
    
    # If we found price patterns, check if any are under $5
    if price_patterns_found:
        # Check if there are any product prices under $5
        # Look for product containers with prices
        product_containers = re.findall(r'(?:product|item|price|sale)[^<]*?<.*?>[^<]*?\$[0-4]\.\d{2}', html, re.IGNORECASE)
        if product_containers:
            return True
    
    # Second check: Look for "under $5" or similar phrases
    cheap_phrases = [
        r'under\s*\$?\s*5',
        r'under\s*\$?\s*5\.\d{2}',
        r'less\s*than\s*\$?\s*5',
        r'less\s*than\s*\$?\s*5\.\d{2}',
        r'for\s*\$?\s*[0-4]\.\d{2}',
        r'just\s*\$?\s*[0-4]\.\d{2}',
        r'only\s*\$?\s*[0-4]\.\d{2}',
        r'\$[0-4]\.\d{2}',
        r'[0-4]\.\d{2}\s*\$',
        r'[0-4]\.\d{2}\s*USD',
        r'USD\s*[0-4]\.\d{2}',
    ]
    
    for phrase in cheap_phrases:
        if re.search(phrase, html, re.IGNORECASE):
            return True
    
    # Third check: Look for Shopify's product JSON or structured data
    # Check for product JSON with prices
    product_json_patterns = [
        r'"price"\s*:\s*"[0-4]\.\d{2}"',
        r'"price"\s*:\s*[0-4]\.\d{2}',
        r'"price"\s*:\s*"[0-4]\.[0-9]{2}"',
        r'"price"\s*:\s*[0-4]\.[0-9]{2}',
        r'"price"\s*:\s*"USD\s*[0-4]\.\d{2}"',
        r'"price"\s*:\s*"USD\s*[0-4]\.[0-9]{2}"',
    ]
    
    for pattern in product_json_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return True
    
    # Fourth check: Look for "from $X" where X < 5
    from_price_patterns = [
        r'from\s*\$?[0-4]\.\d{2}',
        r'from\s*\$?[0-4]\.[0-9]{2}',
        r'starting\s*at\s*\$?[0-4]\.\d{2}',
        r'starting\s*at\s*\$?[0-4]\.[0-9]{2}',
    ]
    
    for pattern in from_price_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return True
    
    return False

def validate_site(site_url, timeout=15, check_products=True):
    """Validate a site: check if working and has products under $5"""
    
    # Check cache first
    with _validated_sites_lock:
        if site_url in _validated_sites_cache:
            return _validated_sites_cache[site_url]
    
    with _failed_sites_lock:
        if site_url in _failed_sites_cache:
            return False
    
    # Check if site is working
    working, html = check_site_working(site_url, timeout)
    
    if not working:
        with _failed_sites_lock:
            _failed_sites_cache.add(site_url)
        return False
    
    # Check for cheap products
    if check_products:
        has_cheap = check_has_cheap_products(html, site_url)
        if has_cheap:
            with _validated_sites_lock:
                _validated_sites_cache[site_url] = True
            return True
        else:
            with _failed_sites_lock:
                _failed_sites_cache.add(site_url)
            return False
    else:
        # If not checking products, just verify it's working
        with _validated_sites_lock:
            _validated_sites_cache[site_url] = True
        return True

def filter_sites(sites, max_workers=20, timeout=15, check_products=True, proxies=None):
    """Filter a list of sites to only include working sites with products under $5
    Uses proxy rotation to avoid rate limiting and blocking
    """
    if not sites:
        print("⚠️ No sites to filter")
        return []
    
    valid_sites = set()
    lock = threading.Lock()
    processed = 0
    total = len(sites)
    
    # Prepare proxy pool
    proxy_pool = []
    if proxies:
        proxy_pool = list(proxies)
        random.shuffle(proxy_pool)
        print(f"🌐 Using {len(proxy_pool)} proxies for filtering rotation")
    else:
        print("⚠️ No proxies provided - using direct connections (may get blocked)")
    
    proxy_index = 0
    failed_proxies = set()
    
    def get_next_proxy():
        """Get next working proxy with rotation"""
        nonlocal proxy_index
        
        if not proxy_pool:
            return None
        
        # Try to find a working proxy
        attempts = 0
        max_attempts = len(proxy_pool) * 2
        
        while attempts < max_attempts:
            proxy = proxy_pool[proxy_index % len(proxy_pool)]
            proxy_index += 1
            
            # Skip failed proxies
            if proxy in failed_proxies:
                attempts += 1
                continue
            
            return proxy
        
        # If all proxies failed, reset and try again
        if len(failed_proxies) == len(proxy_pool):
            print("⚠️ All proxies failed in filtering - resetting")
            failed_proxies.clear()
            return proxy_pool[0] if proxy_pool else None
        
        return None
    
    def validate_site_with_proxy(site_url, timeout=15):
        """Validate site using proxy rotation"""
        
        # Check cache first
        with _validated_sites_lock:
            if site_url in _validated_sites_cache:
                return _validated_sites_cache[site_url]
        
        with _failed_sites_lock:
            if site_url in _failed_sites_cache:
                return False
        
        # Try with proxy rotation
        max_retries = 5
        last_error = None
        
        for attempt in range(max_retries):
            proxy = get_next_proxy() if proxy_pool else None
            
            try:
                # Parse domain
                parsed = urllib.parse.urlparse(site_url)
                domain = parsed.netloc
                
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                }
                
                # Use proxy if available
                proxies_dict = None
                if proxy:
                    proxies_dict = {"http": proxy, "https": proxy}
                
                # Make request with timeout
                response = requests.get(
                    site_url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True,
                    verify=False,
                    proxies=proxies_dict
                )
                
                # Check if working
                if response.status_code == 200:
                    # Check for cheap products if enabled
                    if check_products:
                        has_cheap = check_has_cheap_products(response.text, site_url)
                        if has_cheap:
                            with _validated_sites_lock:
                                _validated_sites_cache[site_url] = True
                            return True
                        else:
                            with _failed_sites_lock:
                                _failed_sites_cache.add(site_url)
                            return False
                    else:
                        # Not checking products, just verify working
                        with _validated_sites_lock:
                            _validated_sites_cache[site_url] = True
                        return True
                        
                elif response.status_code in [429, 403, 503]:
                    # Rate limited - mark proxy as failed and retry
                    if proxy:
                        failed_proxies.add(proxy)
                    time.sleep(random.uniform(0.5, 2.0))
                    continue
                    
                else:
                    # Other error - maybe site is down
                    with _failed_sites_lock:
                        _failed_sites_cache.add(site_url)
                    return False
                    
            except requests.exceptions.Timeout:
                last_error = "Timeout"
                if proxy:
                    failed_proxies.add(proxy)
                time.sleep(random.uniform(0.1, 0.5))
                continue
                
            except requests.exceptions.ConnectionError:
                last_error = "Connection Error"
                if proxy:
                    failed_proxies.add(proxy)
                time.sleep(random.uniform(0.1, 0.5))
                continue
                
            except Exception as e:
                last_error = str(e)
                if proxy:
                    failed_proxies.add(proxy)
                time.sleep(random.uniform(0.1, 0.5))
                continue
        
        # All retries failed
        with _failed_sites_lock:
            _failed_sites_cache.add(site_url)
        return False
    
    print(f"\n🔍 **FILTERING {total:,} SITES**")
    print(f"⏱️  Checking if sites are working and have products under $5...")
    print(f"🌐 Proxies available: {len(proxy_pool)}")
    
    def worker(site):
        nonlocal processed
        try:
            if validate_site_with_proxy(site, timeout):
                with lock:
                    valid_sites.add(site)
                    print(f"✅ [{len(valid_sites)}] {site} - Valid (working + cheap products)")
            else:
                with lock:
                    processed += 1
                    if processed % 10 == 0:
                        print(f"📊 Processed: {processed}/{total} | Valid: {len(valid_sites)} | Proxies left: {len(proxy_pool) - len(failed_proxies)}")
        except Exception as e:
            with lock:
                processed += 1
                if processed % 10 == 0:
                    print(f"📊 Processed: {processed}/{total} | Valid: {len(valid_sites)}")
    
    # Use ThreadPoolExecutor to parallelize
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for site in sites:
            futures.append(executor.submit(worker, site))
        
        # Wait for all futures to complete with progress tracking
        completed = 0
        while completed < len(futures):
            # Check if any futures are done
            for i, future in enumerate(futures):
                if future.done():
                    completed += 1
            
            # Update progress every 5 seconds
            if completed % 10 == 0:
                with lock:
                    print(f"📊 Progress: {processed}/{total} checked | Valid: {len(valid_sites)}")
            
            time.sleep(0.5)
            
            # If we're stuck, check if all proxies failed
            if len(failed_proxies) >= len(proxy_pool) * 0.8 and proxy_pool:
                print(f"⚠️ {len(failed_proxies)}/{len(proxy_pool)} proxies failed - retrying with fresh proxies")
                failed_proxies.clear()
    
    print(f"\n✅ **FILTERING COMPLETE**")
    print(f"🎯 Valid sites: {len(valid_sites)}/{total} ({len(valid_sites)/max(1,total)*100:.1f}%)")
    print(f"❌ Failed sites: {total - len(valid_sites)}")
    
    return list(valid_sites)
# ============================================================
# Modified DORKS - Now includes cheap product searches
# ============================================================
DORKS = CHEAP_PRODUCT_QUERIES + [
    # These are the original dorks but filtered for cheap products
    'site:myshopify.com under 5 dollars',
    'site:myshopify.com under $5',
    'site:myshopify.com cheap products',
    'site:myshopify.com budget items',
    'site:myshopify.com affordable gifts',
    'site:myshopify.com low price',
    'site:myshopify.com clearance sale',
    'site:myshopify.com dollar items',
    'site:myshopify.com bargain bin',
    'site:myshopify.com value deals',
    'site:myshopify.com discount store',
    'site:myshopify.com cheap store',
    'site:myshopify.com budget store',
    'site:myshopify.com under 5 store',
    'site:myshopify.com 5 dollar store',
    'site:myshopify.com 5 and under',
    'site:myshopify.com 5 dollar deals',
    'site:myshopify.com cheap shop',
    'site:myshopify.com budget shop',
    'site:myshopify.com affordable shop',
]

MYSHOPIFY_RE = re.compile(r"https?://([a-z0-9\-]+)\.myshopify\.com", re.IGNORECASE)
MYSHOPIFY_RE_ALT1 = re.compile(r"([a-z0-9\-]+)\.myshopify\.com", re.IGNORECASE)
MYSHOPIFY_RE_ALT2 = re.compile(r"myshopify\.com/([a-z0-9\-]+)", re.IGNORECASE)
MYSHOPIFY_RE_FULL = re.compile(r"https?://([a-z0-9\-]+)\.myshopify\.com[^\s<>\"']*", re.IGNORECASE)

user_data = {}
stop_flags = {}
MAX_PROXY_WORKERS = 800   # Max for Railway Hobby (8GB) - dedicated
MAX_SCRAPE_WORKERS = 500  # Max for Railway Hobby (8GB) - dedicated
MAX_FILTER_WORKERS = 50   # For filtering sites

_session_cache = {}
_session_lock = threading.Lock()

# File saving for sites.txt
_sites_file_lock = threading.Lock()
# Use /data for Railway volume (persistent) or current dir for local
_sites_file_path = "/data/sites.txt" if os.path.exists("/data") else "sites.txt"
_saved_sites = set()  # Track what we've already saved to avoid duplicates

def get_session(proxy=None):
    key = proxy or 'no_proxy'
    if key not in _session_cache:
        with _session_lock:
            if key not in _session_cache:
                session = requests.Session()
                session.headers.update({
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1'
                })
                _session_cache[key] = session
    return _session_cache[key]

def get_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1'
    }

def parse_proxy(line, proxy_type="http"):
    """Parse proxy line with support for http, socks4, socks5, mix"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    
    # For MIX type - keep existing scheme or default to http://
    if proxy_type == "mix":
        # Check if line already has a scheme
        has_scheme = False
        for scheme in ['http://', 'https://', 'socks4://', 'socks5://', 'socks4a://', 'socks5h://']:
            if line.lower().startswith(scheme):
                has_scheme = True
                break
        
        if has_scheme:
            # Already has scheme, return as-is (just validate format)
            try:
                if ':' in line:
                    return line
            except:
                pass
            return None
        else:
            # No scheme, treat as HTTP
            proxy_type = "http"
    
    # Remove any existing scheme for non-mix types
    for scheme in ['http://', 'https://', 'socks4://', 'socks5://', 'socks4a://', 'socks5h://']:
        if line.lower().startswith(scheme):
            line = line[len(scheme):]
            break
    
    try:
        if '@' in line:
            return f"{proxy_type}://{line}"
        elif ':' in line:
            parts = line.split(':')
            if len(parts) == 4:
                return f"{proxy_type}://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            return f"{proxy_type}://{line}"
    except:
        pass
    return None

def save_site_to_file(site):
    """Save a single site to sites.txt immediately (thread-safe)"""
    global _saved_sites
    if not site or site in _saved_sites:
        return
    
    with _sites_file_lock:
        # Double-check after acquiring lock
        if site in _saved_sites:
            return
        
        try:
            # Append mode - creates file if it doesn't exist
            with open(_sites_file_path, 'a', encoding='utf-8', errors='replace') as f:
                f.write(f"{site}\n")
                f.flush()  # Ensure it's written immediately
                os.fsync(f.fileno())  # Force write to disk (important for Linux)
            _saved_sites.add(site)
        except Exception as e:
            print(f"❌ Error saving site to file: {e}")

def save_all_sites_to_file(sites):
    """Save all sites to sites.txt (thread-safe, removes duplicates)"""
    if not sites:
        return
    
    with _sites_file_lock:
        try:
            # Read existing sites to avoid duplicates
            existing_sites = set()
            if os.path.exists(_sites_file_path):
                try:
                    with open(_sites_file_path, 'r', encoding='utf-8', errors='replace') as f:
                        existing_sites = set(line.strip() for line in f if line.strip())
                except:
                    pass
            
            # Add new sites
            new_sites = set(sites) - existing_sites
            if new_sites:
                with open(_sites_file_path, 'a', encoding='utf-8', errors='replace') as f:
                    for site in sorted(new_sites):
                        f.write(f"{site}\n")
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk
            
            # Update saved sites set
            _saved_sites.update(sites)
        except Exception as e:
            print(f"❌ Error saving sites to file: {e}")

# Smart Engine Rotation System
_engine_stats = {}  # Track success/failure per engine
_engine_cooldowns = {}  # Cooldown timestamps for failed engines
_engine_round_robin_index = 0  # For round-robin fallback
_engine_lock = threading.Lock()

def reset_engine_stats():
    """Reset engine statistics - call at start of new scraping session"""
    global _engine_stats, _engine_cooldowns, _engine_round_robin_index
    with _engine_lock:
        _engine_stats = {}
        _engine_cooldowns = {}
        _engine_round_robin_index = 0

def record_engine_result(engine_name, success, urls_found=0):
    """Record success/failure for an engine"""
    with _engine_lock:
        if engine_name not in _engine_stats:
            _engine_stats[engine_name] = {'success': 0, 'fail': 0, 'urls': 0, 'consecutive_fails': 0}
        
        if success:
            _engine_stats[engine_name]['success'] += 1
            _engine_stats[engine_name]['urls'] += urls_found
            _engine_stats[engine_name]['consecutive_fails'] = 0
            # Remove from cooldown if successful
            if engine_name in _engine_cooldowns:
                del _engine_cooldowns[engine_name]
        else:
            _engine_stats[engine_name]['fail'] += 1
            _engine_stats[engine_name]['consecutive_fails'] += 1
            # Add cooldown after 3 consecutive failures
            if _engine_stats[engine_name]['consecutive_fails'] >= 3:
                _engine_cooldowns[engine_name] = time.time() + 30  # 30 second cooldown

def get_engine_score(engine):
    """Calculate engine score based on performance"""
    name = engine['name']
    with _engine_lock:
        if name not in _engine_stats:
            return engine['weight']  # Use default weight for new engines
        
        stats = _engine_stats[name]
        total = stats['success'] + stats['fail']
        if total == 0:
            return engine['weight']
        
        # Success rate (0-1)
        success_rate = stats['success'] / total
        # Bonus for finding URLs
        url_bonus = min(stats['urls'] / 100, 0.3)  # Max 0.3 bonus
        
        # Combined score
        return (engine['weight'] * 0.5) + (success_rate * 0.3) + url_bonus

def select_search_engine():
    """Smart engine selection with performance tracking and cooldowns"""
    global _engine_round_robin_index
    
    current_time = time.time()
    
    with _engine_lock:
        # Filter out engines on cooldown
        available_engines = [
            e for e in SEARCH_ENGINES 
            if e['name'] not in _engine_cooldowns or _engine_cooldowns[e['name']] < current_time
        ]
        
        # If all engines on cooldown, use round-robin on all engines
        if not available_engines:
            _engine_round_robin_index = (_engine_round_robin_index + 1) % len(SEARCH_ENGINES)
            return SEARCH_ENGINES[_engine_round_robin_index]
    
    # Calculate scores for available engines
    scored_engines = [(e, get_engine_score(e)) for e in available_engines]
    total_score = sum(score for _, score in scored_engines)
    
    if total_score <= 0:
        return random.choice(available_engines)
    
    # Weighted random selection based on scores
    rand = random.random() * total_score
    cumulative = 0
    for engine, score in scored_engines:
        cumulative += score
        if rand <= cumulative:
            return engine
    
    return available_engines[0]

def test_proxy_with_search(proxy):
    try:
        engine = random.choice(SEARCH_ENGINES)
        response = requests.get(
            engine['url'],
            params={engine['param']: 'site:myshopify.com test'},
            headers=get_headers(),
            proxies={"http": proxy, "https": proxy},
            timeout=10,
            verify=False,
            allow_redirects=True
        )
        
        if 200 <= response.status_code < 400:
            urls = extract_shopify_urls(response.text)
            return len(response.text) > 100
        return False
    except:
        return False

def _normalize_shopify_url(url):
    if not url:
        return None
    
    url = url.strip().strip('\'"')
    if not url:
        return None
    
    # Remove common trailing punctuation and stray slashes/backslashes
    url = re.sub(r'[\\\/]+$', '', url)
    url = url.rstrip('.,;!?)]}')
    
    if not url:
        return None
    
    if not url.lower().startswith(('http://', 'https://')):
        url = 'https://' + url.lstrip('/')
    
    url = url.replace('http://', 'https://', 1)
    if '#' in url:
        url = url.split('#', 1)[0]
    url = url.strip()
    
    parsed = urllib.parse.urlparse(url)
    netloc = parsed.netloc or parsed.path
    netloc = netloc.lower()
    
    if not netloc or '.myshopify.com' not in netloc:
        return None
    
    netloc = netloc.split('@', 1)[-1]
    netloc = netloc.split(':', 1)[0]
    
    return f"https://{netloc}"


def extract_shopify_urls(html):
    urls = set()
    
    def add_url(candidate):
        normalized = _normalize_shopify_url(candidate)
        if normalized:
            urls.add(normalized)
    
    for match in MYSHOPIFY_RE.finditer(html):
        add_url(match.group(0))
    
    for match in MYSHOPIFY_RE_FULL.finditer(html):
        add_url(match.group(0))
    
    for match in MYSHOPIFY_RE_ALT1.finditer(html):
        domain = match.group(1)
        if domain and len(domain) > 3:
            add_url(f"https://{domain}.myshopify.com")
            add_url(f"http://{domain}.myshopify.com")
    
    for match in MYSHOPIFY_RE_ALT2.finditer(html):
        domain = match.group(1)
        if domain and len(domain) > 3:
            add_url(f"https://{domain}.myshopify.com")
            add_url(f"http://{domain}.myshopify.com")
    
    href_pattern = re.compile(r'href=["\']([^"\']*\.myshopify\.com[^"\']*)["\']', re.IGNORECASE)
    for match in href_pattern.finditer(html):
        add_url(match.group(1))
    
    src_pattern = re.compile(r'src=["\']([^"\']*\.myshopify\.com[^"\']*)["\']', re.IGNORECASE)
    for match in src_pattern.finditer(html):
        add_url(match.group(1))
    
    return list(urls)

def fetch_page_parallel(engine, query, page, proxy=None):
    try:
        params = {engine['param']: query}
        
        if engine['name'] == 'DuckDuckGo':
            params['s'] = (page - 1) * 20
        elif engine['name'] == 'Brave':
            params['offset'] = (page - 1) * 10
        elif engine['name'] == 'Startpage':
            params['page'] = page
        elif engine['name'] == 'Mojeek':
            params['pn'] = page
        
        proxies = {"http": proxy, "https": proxy} if proxy else None
        
        session = get_session(proxy)
        response = session.get(
            engine['url'],
            params=params,
            proxies=proxies,
            timeout=8,
            verify=False,
            allow_redirects=True
        )
        
        if 200 <= response.status_code < 400:
            return extract_shopify_urls(response.text), True
        return [], False
    except:
        return [], False

def search_with_proxy(query, proxy=None, chat_id=None):
    max_retries = 3
    all_urls = set()
    
    for attempt in range(max_retries):
        try:
            engine = select_search_engine()
            engine_name = engine['name']
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for page in range(1, 51):  # 50 pages for MORE results
                    future = executor.submit(fetch_page_parallel, engine, query, page, proxy)
                    futures.append((page, future))
                
                pages_with_results = 0
                page_urls_total = 0
                for page, future in futures:
                    # Check stop flag before processing each page result
                    if chat_id and stop_flags.get(chat_id, False):
                        # Cancel remaining futures and return what we have
                        for _, f in futures:
                            if not f.done():
                                f.cancel()
                        return list(all_urls) if all_urls else []
                    
                    try:
                        page_urls, success = future.result(timeout=3)  # Reduced from 15s to 3s
                        if success:
                            pages_with_results += 1
                            if page_urls:
                                page_urls_total += len(page_urls)
                                all_urls.update(page_urls)
                                print(f"✅ [{engine_name}] Page {page}: Found {len(page_urls)} URLs")
                            elif page == 1 and not page_urls:
                                pass
                    except:
                        continue
            
            if all_urls:
                # Record success with URL count
                record_engine_result(engine_name, True, len(all_urls))
                print(f"✅ [{engine_name}] Total: {len(all_urls)} unique URLs from {pages_with_results} page(s)")
                return list(all_urls)
            else:
                # Record failure (no results)
                record_engine_result(engine_name, False)
                if attempt < max_retries - 1:
                    time.sleep(0.1)
                continue
                
        except Exception as e:
            # Record failure (exception)
            if 'engine_name' in locals():
                record_engine_result(engine_name, False)
            if attempt < max_retries - 1:
                time.sleep(0.1)
            continue
    
    return list(all_urls) if all_urls else []

def search_proxyless(query, chat_id=None):
    """Search using proxyless engines (SearX instances, Yandex, etc.) with curl_cffi browser impersonation"""
    all_urls = set()
    
    # Try multiple engines without proxy
    engines_to_try = random.sample(PROXYLESS_ENGINES, min(3, len(PROXYLESS_ENGINES)))
    
    for engine in engines_to_try:
        if chat_id and stop_flags.get(chat_id, False):
            break
            
        try:
            params = {engine['param']: query}
            
            # Add format param for SearX instances
            if 'SearX' in engine['name'] or 'searx' in engine['url']:
                params['format'] = 'html'
                params['categories'] = 'general'
            
            # Use curl_cffi with browser impersonation if available
            if CURL_CFFI_AVAILABLE:
                response = curl_requests.get(
                    engine['url'],
                    params=params,
                    headers=get_headers(),
                    timeout=8,
                    allow_redirects=True,
                    impersonate=random.choice(BROWSER_IMPERSONATE)
                )
            else:
                response = requests.get(
                    engine['url'],
                    params=params,
                    headers=get_headers(),
                    timeout=8,
                    verify=False,
                    allow_redirects=True
                )
            
            if 200 <= response.status_code < 400:
                urls = extract_shopify_urls(response.text)
                if urls:
                    all_urls.update(urls)
                    print(f"🌐 [{engine['name']}] Found {len(urls)} URLs (proxyless)")
                    
            # Minimal delay for speed
            time.sleep(random.uniform(0.05, 0.15))
            
        except Exception as e:
            continue
    
    return list(all_urls)

def proxyless_worker(found, lock, searches_counter, chat_id, stop_check_func):
    """Worker that scrapes without proxies using lenient search engines"""
    worker_found = 0
    engine_index = 0
    
    # Use curl_cffi session if available
    if CURL_CFFI_AVAILABLE:
        session = curl_requests.Session()
    else:
        session = requests.Session()
        session.verify = False
    
    while True:
        if stop_check_func():
            break
            
        try:
            query = random.choice(DORKS)
            
            # Rotate through proxyless engines
            engine = PROXYLESS_ENGINES[engine_index % len(PROXYLESS_ENGINES)]
            engine_index += 1
            
            params = {engine['param']: query}
            
            # Add format param for SearX instances  
            if 'SearX' in engine['name'] or 'searx' in engine['url']:
                params['format'] = 'html'
                params['categories'] = 'general'
            
            # Use curl_cffi with browser impersonation if available
            if CURL_CFFI_AVAILABLE:
                response = session.get(
                    engine['url'],
                    params=params,
                    headers=get_headers(),
                    timeout=10,
                    allow_redirects=True,
                    impersonate=random.choice(BROWSER_IMPERSONATE)
                )
            else:
                response = session.get(
                    engine['url'],
                    params=params,
                    headers=get_headers(),
                    timeout=10,
                    allow_redirects=True
                )
            
            if 200 <= response.status_code < 400:
                urls = extract_shopify_urls(response.text)
                if urls:
                    with lock:
                        searches_counter[0] += 1
                        for url in urls:
                            if url not in found:
                                found.add(url)
                                worker_found += 1
                                print(f"🌐 [{engine['name']}] [{len(found)}] {url}")
                                save_site_to_file(url)
                else:
                    with lock:
                        searches_counter[0] += 1
            
            # Minimal delay for turbo speed
            time.sleep(random.uniform(0.1, 0.4))
            
        except Exception as e:
            time.sleep(0.2)
            continue
    
    return worker_found

async def test_proxies(chat_id, context, proxy_list):
    working = []
    tested = 0
    total = len(proxy_list)
    lock = threading.Lock()
    
    msg = await context.bot.send_message(
        chat_id, 
        f"🧪 **STRICT TESTING {total:,} PROXIES**\n\n✅ Testing with REAL search queries\n⚡ Only proxies that work with search engines will pass"
    )
    
    def worker():
        nonlocal tested
        while True:
            try:
                proxy = q.get_nowait()
                if test_proxy_with_search(proxy):
                    with lock:
                        working.append(proxy)
                        print(f"✅ Working proxy: {proxy[:50]}")
                with lock:
                    tested += 1
                q.task_done()
            except queue.Empty:
                break
            except:
                with lock:
                    tested += 1
                q.task_done()
    
    q = queue.Queue()
    for proxy in proxy_list:
        q.put(proxy)
    
    with ThreadPoolExecutor(max_workers=min(MAX_PROXY_WORKERS, total)) as executor:
        futures = [executor.submit(worker) for _ in range(min(MAX_PROXY_WORKERS, total))]
        
        while not all(f.done() for f in futures):
            await asyncio.sleep(3)
            with lock:
                if tested > 0:
                    pct = (tested / total) * 100
                    rate = len(working) / tested * 100 if tested > 0 else 0
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=msg.message_id,
                            text=f"🧪 **STRICT TESTING PROXIES**\n\n📊 Progress: {tested:,}/{total:,} ({pct:.1f}%)\n✅ Working: {len(working)} ({rate:.1f}%)\n🔍 Testing with real searches\n⚡ {len(SEARCH_ENGINES)} search engines",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.message_id,
            text=f"✅ **TESTING COMPLETE**\n\n🎯 Found: {len(working)}/{total} working proxies\n📊 Success rate: {len(working)/total*100:.1f}%\n🔍 All tested with real searches\n🚀 Ready for scraping!",
            parse_mode='Markdown'
        )
    except:
        pass
    
    return working

async def scrape_sites(chat_id, context, proxies):
    found = set()
    searches = 0
    failed_proxies = set()
    lock = threading.Lock()
    start_time = time.time()
    
    # Reset engine stats for fresh session
    reset_engine_stats()
    
    engine_stats = {e['name']: 0 for e in SEARCH_ENGINES}
    
    stop_flags[chat_id] = False
    
    msg = await context.bot.send_message(
        chat_id, 
        f"🔍 **MULTI-ENGINE SCRAPER V6.2 (UNDER $5 FILTER)**\n\n🎯 Keywords: {len(DORKS)}\n🌐 Proxies: {len(proxies)}\n🔍 Search Engines: {len(SEARCH_ENGINES)}\n⚡ Workers: {min(MAX_SCRAPE_WORKERS, len(proxies))}\n💰 Filter: Products under $5\n\n💪 Starting...",
        parse_mode='Markdown'
    )
    
    user_data[chat_id]['scraping'] = True
    user_data[chat_id]['found_sites'] = found
    
    proxy_pool = proxies.copy()
    random.shuffle(proxy_pool)
    proxy_index = 0
    
    def get_next_proxy():
        nonlocal proxy_index
        if not proxy_pool:
            return None
        
        attempts = 0
        while attempts < len(proxy_pool):
            proxy = proxy_pool[proxy_index % len(proxy_pool)]
            proxy_index += 1
            
            if proxy not in failed_proxies:
                return proxy
            attempts += 1
        return None
    
    def scraper_worker():
        nonlocal searches
        worker_found = 0
        consecutive_failures = 0
        
        for search_count in range(10000):
            if stop_flags.get(chat_id, False):
                break
            
            if not user_data[chat_id].get('scraping', False):
                break
            
            if consecutive_failures >= 500:
                consecutive_failures = 0  # Reset instead of stopping
                time.sleep(0.5)  # Brief pause then continue
                
            try:
                query = random.choice(DORKS)
                proxy = get_next_proxy()
                
                if not proxy:
                    # Reset failed proxies and try again
                    failed_proxies.clear()
                    proxy = get_next_proxy()
                    if not proxy:
                        break
                
                if stop_flags.get(chat_id, False):
                    break
                    
                urls = search_with_proxy(query, proxy, chat_id)
                
                if stop_flags.get(chat_id, False):
                    break
                
                if urls:
                    consecutive_failures = 0
                    with lock:
                        searches += 1
                        for url in urls:
                            if url not in found:
                                found.add(url)
                                worker_found += 1
                                print(f"✅ [{len(found)}] {url}")
                                # Save site immediately to file
                                save_site_to_file(url)
                else:
                    consecutive_failures += 1
                    with lock:
                        searches += 1
                        # DON'T mark proxy as failed - keep reusing
                
                time.sleep(random.uniform(0.005, 0.02))
                
            except Exception as e:
                consecutive_failures += 1
                with lock:
                    searches += 1
                    # DON'T mark proxy as failed on exception
                time.sleep(0.01)
                continue
        
        return worker_found
    
    # Proxyless worker function for this scraper - Enhanced for V6.2 with under $5 filter
    def proxyless_scraper_worker():
        nonlocal searches
        worker_found = 0
        engine_index = 0
        consecutive_failures = 0
        
        # Use curl_cffi session if available (MUCH better at bypassing detection)
        if CURL_CFFI_AVAILABLE:
            session = curl_requests.Session()
        else:
            session = requests.Session()
            session.verify = False
        
        for _ in range(10000):  # 10000 searches per proxyless worker
            if stop_flags.get(chat_id, False):
                break
            if not user_data[chat_id].get('scraping', False):
                break
            
            if consecutive_failures >= 15:
                # Engine might be rate limited, pause and reset
                time.sleep(1)
                consecutive_failures = 0
                
            try:
                query = random.choice(DORKS)
                engine = PROXYLESS_ENGINES[engine_index % len(PROXYLESS_ENGINES)]
                engine_index += 1
                
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                
                # Add custom headers if engine has them (like Brave)
                if 'headers' in engine:
                    headers.update(engine['headers'])
                
                params = {engine['param']: query}
                if 'SearX' in engine['name'] or 'searx' in engine['url'].lower():
                    params['format'] = 'html'
                    params['categories'] = 'general'
                
                # Use curl_cffi with browser impersonation if available
                if CURL_CFFI_AVAILABLE:
                    response = session.get(
                        engine['url'],
                        params=params,
                        headers=headers,
                        timeout=8,
                        allow_redirects=True,
                        impersonate=random.choice(BROWSER_IMPERSONATE)
                    )
                else:
                    response = session.get(
                        engine['url'],
                        params=params,
                        headers=headers,
                        timeout=8,
                        allow_redirects=True
                    )
                
                if 200 <= response.status_code < 400:
                    urls = extract_shopify_urls(response.text)
                    if urls:
                        consecutive_failures = 0
                        with lock:
                            searches += 1
                            for url in urls:
                                if url not in found:
                                    found.add(url)
                                    worker_found += 1
                                    print(f"🌐 [{engine['name']}] [{len(found)}] {url}")
                                    save_site_to_file(url)
                    else:
                        consecutive_failures += 1
                        with lock:
                            searches += 1
                elif response.status_code in [429, 403, 503]:
                    consecutive_failures += 1
                    time.sleep(0.5)
                
                # TURBO delays - minimal waits
                if engine['name'] == 'Brave':
                    time.sleep(random.uniform(0.8, 1.5))
                elif 'SearX' in engine['name']:
                    time.sleep(random.uniform(0.1, 0.4))
                else:
                    time.sleep(random.uniform(0.3, 0.8))
                
            except:
                consecutive_failures += 1
                time.sleep(0.3)
                continue
        
        return worker_found
    
    workers = min(MAX_SCRAPE_WORKERS, len(proxies))
    
    # Only use proxyless if enabled (disable when your IP is blocked!)
    if USE_PROXYLESS_IN_DUAL_MODE:
        proxyless_workers = len(PROXYLESS_ENGINES) * 3
        print(f"🌐 Proxyless workers: {proxyless_workers} (enabled)")
    else:
        proxyless_workers = 0
        print(f"⚠️ Proxyless workers: DISABLED (your IP may be blocked)")
    
    # Start periodic saving task (every 10 seconds)
    last_periodic_save = time.time()
    periodic_save_interval = 10.0
    last_milestone_sent = 0  # Track last 1000 milestone sent
    
    # Store bot and message info for thread-safe updates
    bot = context.bot
    msg_id = msg.message_id
    
    def run_scraping():
        """Run scraping entirely in thread - no async blocking"""
        nonlocal searches, last_periodic_save, last_milestone_sent
        
        with ThreadPoolExecutor(max_workers=workers + max(1, proxyless_workers)) as executor:
            # Start proxy workers
            futures = [executor.submit(scraper_worker) for _ in range(workers)]
            # Start proxyless workers only if enabled
            if proxyless_workers > 0:
                proxyless_futures = [executor.submit(proxyless_scraper_worker) for _ in range(proxyless_workers)]
            else:
                proxyless_futures = []
            all_futures = futures + proxyless_futures
            
            last_update = time.time()
            
            while not all(future.done() for future in all_futures):
                if stop_flags.get(chat_id, False):
                    user_data[chat_id]['scraping'] = False
                    for future in all_futures:
                        if not future.done():
                            future.cancel()
                    break
                    
                time.sleep(0.5)  # Use time.sleep instead of await
                current = time.time()
                
                # Periodic save every 10 seconds
                if current - last_periodic_save >= periodic_save_interval:
                    with lock:
                        if found:
                            save_all_sites_to_file(list(found))
                    last_periodic_save = current
                
                # Auto-send sites every 1000 new sites (sync version)
                current_milestone = (len(found) // 1000) * 1000
                if current_milestone > last_milestone_sent and current_milestone > 0:
                    last_milestone_sent = current_milestone
                    try:
                        with lock:
                            save_all_sites_to_file(list(found))
                        
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                            for site in sorted(found):
                                f.write(f"{site}\n")
                            temp_path = f.name
                        
                        # Use requests to send file via Telegram API directly (no async)
                        with open(temp_path, 'rb') as f:
                            requests.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                                data={'chat_id': chat_id, 'caption': f"🎯 MILESTONE: {len(found):,} SITES!\n\n💰 Filter: Products under $5\n⏱️ Time: {current - start_time:.0f}s"},
                                files={'document': (f"sites_{len(found)}.txt", f)},
                                timeout=30
                            )
                        os.unlink(temp_path)
                        print(f"📤 Auto-sent {len(found)} sites at {current_milestone} milestone")
                    except Exception as e:
                        print(f"⚠️ Auto-send failed: {e}")
                
                # Check stop flag again
                if stop_flags.get(chat_id, False):
                    user_data[chat_id]['scraping'] = False
                    for future in futures:
                        if not future.done():
                            future.cancel()
                    break
                
                # Update status message (sync version via direct API)
                if current - last_update >= 5:  # Update every 5 seconds
                    with lock:
                        elapsed = current - start_time
                        rate = len(found) / max(1, searches) if searches > 0 else 0
                        sites_per_min = (len(found) / max(1, elapsed)) * 60
                        
                        proxyless_status = f"{proxyless_workers}" if proxyless_workers > 0 else "DISABLED"
                        
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                                json={
                                    'chat_id': chat_id,
                                    'message_id': msg_id,
                                    'text': f"🔥 SCRAPER V6.2 (UNDER $5)\n\n🎯 FOUND: {len(found)} SITES\n📊 Searches: {searches:,}\n⚡ Hit rate: {rate:.3f} sites/search\n🚀 Speed: {sites_per_min:.1f} sites/min\n⏱️ Time: {elapsed:.0f}s\n👥 Proxy Workers: {workers}\n🌐 Proxyless: {proxyless_status}\n🔍 Engines: {len(SEARCH_ENGINES)}\n📄 Pages per search: 50\n🔑 Keywords: {len(DORKS)}\n💰 Filter: Products under $5\n\n💡 /stop for instant results!"
                                },
                                timeout=10
                            )
                            last_update = current
                        except Exception as e:
                            print(f"⚠️ Update message failed: {e}")
        
        # Final status
        try:
            elapsed = time.time() - start_time
            status = "STOPPED" if stop_flags.get(chat_id, False) else "COMPLETE"
            sites_per_min = (len(found) / max(1, elapsed)) * 60
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                json={
                    'chat_id': chat_id,
                    'message_id': msg_id,
                    'text': f"🎉 {status} - V6.2 (UNDER $5)\n\n🎯 {len(found)} SHOPIFY SITES\n📊 Searches: {searches:,}\n⚡ Success: {len(found)/max(1,searches):.3f}\n🚀 Speed: {sites_per_min:.1f}/min\n⏱️ Time: {elapsed:.1f}s\n🔑 {len(DORKS)} keywords\n💰 Filter: Products under $5\n\n📁 Use /send to get file!"
                },
                timeout=10
            )
        except:
            pass
        
        # Final save
        with lock:
            if found:
                save_all_sites_to_file(list(found))
        
        user_data[chat_id]['found_sites'] = found
        return found
    
    # Run entirely in a separate thread - completely non-blocking
    loop = asyncio.get_event_loop()
    found = await loop.run_in_executor(None, run_scraping)
    
    stop_flags[chat_id] = False
    return list(found)


async def scrape_sites_proxyless_only(chat_id, context):
    """Ultra-fast proxyless-only scraper using all available search engines"""
    found = set()
    searches = 0
    lock = threading.Lock()
    start_time = time.time()
    
    # Reset engine stats for fresh session
    reset_engine_stats()
    
    engine_stats = {e['name']: 0 for e in PROXYLESS_ENGINES}
    
    stop_flags[chat_id] = False
    
    msg = await context.bot.send_message(
        chat_id, 
        f"🚀 **PROXYLESS ULTRA SCRAPER V6.2 (UNDER $5)**\n\n"
        f"🔍 Search Engines: {len(PROXYLESS_ENGINES)}\n"
        f"🎯 Keywords: {len(DORKS)}\n"
        f"👥 Workers: {len(PROXYLESS_ENGINES) * 3}\n"
        f"💰 Filter: Products under $5\n"
        f"⚡ NO PROXIES NEEDED!\n\n"
        f"💪 Starting massive parallel search...",
        parse_mode='Markdown'
    )
    
    user_data[chat_id]['scraping'] = True
    user_data[chat_id]['found_sites'] = found
    
    def proxyless_engine_worker(engine, worker_id):
        """Worker dedicated to one search engine"""
        nonlocal searches
        worker_found = 0
        consecutive_failures = 0
        
        # Use curl_cffi session if available (MUCH better at bypassing detection)
        if CURL_CFFI_AVAILABLE:
            session = curl_requests.Session()
        else:
            session = requests.Session()
            session.verify = False
        
        # Each worker does many searches
        for search_num in range(2500):  # 2500 searches per engine worker for more coverage
            if stop_flags.get(chat_id, False):
                break
            if not user_data[chat_id].get('scraping', False):
                break
            
            if consecutive_failures >= 20:
                # This engine is rate limited, give up on this engine
                print(f"❌ [{engine['name']}] Too many failures ({consecutive_failures}), stopping worker")
                break                
            try:
                query = random.choice(DORKS)
                
                headers = {
                    'User-Agent': random.choice(USER_AGENTS),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                
                # Add custom headers if engine has them
                if 'headers' in engine:
                    headers.update(engine['headers'])
                
                params = {engine['param']: query}
                
                # SearX-specific params
                if 'SearX' in engine['name'] or 'searx' in engine['url'].lower():
                    params['format'] = 'html'
                    params['categories'] = 'general'
                
                # DEBUG: Try request and log errors
                try:
                    if CURL_CFFI_AVAILABLE:
                        response = session.get(
                            engine['url'],
                            params=params,
                            headers=headers,
                            timeout=8,
                            allow_redirects=True,
                            impersonate=random.choice(BROWSER_IMPERSONATE)
                        )
                    else:
                        response = session.get(
                            engine['url'],
                            params=params,
                            headers=headers,
                            timeout=8,
                            allow_redirects=True
                        )
                except Exception as req_err:
                    print(f"🔴 [{engine['name']}] Request error: {type(req_err).__name__}: {str(req_err)[:100]}")
                    consecutive_failures += 1
                    time.sleep(0.3)
                    continue
                
                if 200 <= response.status_code < 400:
                    urls = extract_shopify_urls(response.text)
                    if urls:
                        consecutive_failures = 0
                        with lock:
                            searches += 1
                            engine_stats[engine['name']] += len(urls)
                            for url in urls:
                                if url not in found:
                                    found.add(url)
                                    worker_found += 1
                                    print(f"🌐 [{engine['name']}] [{len(found)}] {url}")
                                    save_site_to_file(url)
                    else:
                        consecutive_failures += 1
                        with lock:
                            searches += 1
                elif response.status_code in [429, 403, 503]:
                    # Rate limited - log it
                    print(f"🟡 [{engine['name']}] Rate limited: {response.status_code}")
                    consecutive_failures += 1
                    time.sleep(0.5)
                else:
                    print(f"🟠 [{engine['name']}] Bad status: {response.status_code}")
                    consecutive_failures += 1
                
                # Delays to avoid rate limiting
                if engine['name'] == 'Brave':
                    time.sleep(random.uniform(2.0, 4.0))  # Brave rate limits aggressively
                elif 'SearX' in engine['name']:
                    time.sleep(random.uniform(0.5, 1.0))
                else:
                    time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                consecutive_failures += 1
                time.sleep(0.2)
                continue
        
        return worker_found
    
    # Create 2 workers per engine (more causes rate limiting!)
    workers_per_engine = 2
    total_workers = len(PROXYLESS_ENGINES) * workers_per_engine
    last_milestone_sent = 0  # Track last 1000 milestone sent
    
    # Store message info for thread-safe updates
    msg_id = msg.message_id
    
    def run_proxyless_scraping():
        """Run proxyless scraping entirely in thread - no async blocking"""
        nonlocal searches, last_milestone_sent
        last_update = time.time()
        last_periodic_save = time.time()
        
        with ThreadPoolExecutor(max_workers=total_workers) as executor:
            futures = []
            for engine in PROXYLESS_ENGINES:
                for worker_id in range(workers_per_engine):
                    futures.append(executor.submit(proxyless_engine_worker, engine, worker_id))
            
            while not all(future.done() for future in futures):
                if stop_flags.get(chat_id, False):
                    user_data[chat_id]['scraping'] = False
                    break
                    
                time.sleep(0.5)  # Use time.sleep instead of await
                current = time.time()
                
                # Periodic save every 10 seconds
                if current - last_periodic_save >= 10:
                    with lock:
                        if found:
                            save_all_sites_to_file(list(found))
                    last_periodic_save = current
                
                # Auto-send sites every 1000 new sites (sync version)
                current_milestone = (len(found) // 1000) * 1000
                if current_milestone > last_milestone_sent and current_milestone > 0:
                    last_milestone_sent = current_milestone
                    try:
                        with lock:
                            save_all_sites_to_file(list(found))
                        
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                            for site in sorted(found):
                                f.write(f"{site}\n")
                            temp_path = f.name
                        
                        with open(temp_path, 'rb') as f:
                            requests.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                                data={'chat_id': chat_id, 'caption': f"🎯 MILESTONE: {len(found):,} SITES!\n\n💰 Filter: Products under $5\n⏱️ Time: {current - start_time:.0f}s"},
                                files={'document': (f"sites_{len(found)}.txt", f)},
                                timeout=30
                            )
                        os.unlink(temp_path)
                        print(f"📤 Auto-sent {len(found)} sites at {current_milestone} milestone")
                    except Exception as e:
                        print(f"⚠️ Auto-send failed: {e}")
                
                # Update status message (sync version via direct API)
                if current - last_update >= 5:
                    with lock:
                        elapsed = current - start_time
                        rate = len(found) / max(1, searches) if searches > 0 else 0
                        sites_per_min = (len(found) / max(1, elapsed)) * 60
                        
                        top_engines = sorted(engine_stats.items(), key=lambda x: x[1], reverse=True)[:5]
                        top_str = '\n'.join([f"  • {name}: {count}" for name, count in top_engines if count > 0])
                        
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                                json={
                                    'chat_id': chat_id,
                                    'message_id': msg_id,
                                    'text': f"🔥 PROXYLESS ULTRA V6.2 (UNDER $5)\n\n🎯 FOUND: {len(found)} SITES\n📊 Searches: {searches:,}\n⚡ Hit rate: {rate:.3f}\n🚀 Speed: {sites_per_min:.1f} sites/min\n⏱️ Time: {elapsed:.0f}s\n🌐 Engines: {len(PROXYLESS_ENGINES)}\n👥 Workers: {total_workers}\n💰 Filter: Products under $5\n\n🏆 TOP ENGINES:\n{top_str if top_str else '  Starting...'}\n\n💡 /stop for instant results!"
                                },
                                timeout=10
                            )
                            last_update = current
                        except Exception as e:
                            print(f"⚠️ Update message failed: {e}")
        
        # Final status
        try:
            elapsed = time.time() - start_time
            status = "STOPPED" if stop_flags.get(chat_id, False) else "COMPLETE"
            sites_per_min = (len(found) / max(1, elapsed)) * 60
            
            top_engines = sorted(engine_stats.items(), key=lambda x: x[1], reverse=True)[:5]
            top_str = '\n'.join([f"  • {name}: {count}" for name, count in top_engines if count > 0])
            
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                json={
                    'chat_id': chat_id,
                    'message_id': msg_id,
                    'text': f"🎉 {status} - PROXYLESS V6.2 (UNDER $5)\n\n🎯 {len(found)} SHOPIFY SITES\n📊 Searches: {searches:,}\n⚡ Rate: {len(found)/max(1,searches):.3f}\n🚀 Speed: {sites_per_min:.1f}/min\n⏱️ Time: {elapsed:.1f}s\n💰 Filter: Products under $5\n\n🏆 TOP ENGINES:\n{top_str}\n\n📁 Use /send to get file!"
                },
                timeout=10
            )
        except Exception as e:
            print(f"⚠️ Final status message failed: {e}")
        
        # Final save
        with lock:
            if found:
                save_all_sites_to_file(list(found))
        
        user_data[chat_id]['found_sites'] = found
        stop_flags[chat_id] = False
        return list(found)
    
    # Run entirely in a separate thread - completely non-blocking
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_proxyless_scraping)
    return result


async def toggle_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle proxyless mode on/off for dual mode scraping"""
    global USE_PROXYLESS_IN_DUAL_MODE
    
    USE_PROXYLESS_IN_DUAL_MODE = not USE_PROXYLESS_IN_DUAL_MODE
    
    if USE_PROXYLESS_IN_DUAL_MODE:
        status = "✅ **ENABLED**"
        msg = "Proxyless workers will run alongside proxy workers in /done mode."
    else:
        status = "❌ **DISABLED**"
        msg = "Only proxy workers will run in /done mode.\nUse this when your IP is blocked!"
    
    await update.message.reply_text(
        f"🔄 **PROXYLESS MODE TOGGLED**\n\n"
        f"Status: {status}\n\n"
        f"{msg}\n\n"
        f"💡 Use /toggle again to switch.",
        parse_mode='Markdown'
    )


async def proxyless_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start proxyless-only scraping - no proxies needed!"""
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        f"🚀 **PROXYLESS MODE ACTIVATED**\n\n"
        f"🔍 Search Engines: {len(PROXYLESS_ENGINES)}\n"
        f"• Brave (excellent for Shopify)\n"
        f"• 10+ SearX instances\n"
        f"• Yahoo, Ecosia, Yandex\n"
        f"• Metager, Swisscows, Dogpile\n\n"
        f"🎯 Keywords: {len(DORKS)}+\n"
        f"💰 Filter: Products under $5\n"
        f"⚡ NO PROXIES REQUIRED!\n\n"
        f"💪 Starting ultra scraper...",
        parse_mode='Markdown'
    )
    
    user_data[chat_id] = {'proxy_files': [], 'all_proxies': set()}
    stop_flags[chat_id] = False
    
    # Run scraping as background task so bot stays responsive
    async def background_scrape_proxyless():
        try:
            sites = await scrape_sites_proxyless_only(chat_id, context)
            if not stop_flags.get(chat_id, False):
                try:
                    await send_results(chat_id, context, sites)
                except Exception as e:
                    print(f"❌ Error sending results: {e}")
                    try:
                        await context.bot.send_message(
                            chat_id,
                            f"⚠️ Error sending file, but sites are saved!\n\n"
                            f"🎯 Found: {len(sites)} sites\n"
                            f"💰 Filter: Products under $5\n"
                            f"📁 Check sites.txt file"
                        )
                    except:
                        pass
        except Exception as e:
            print(f"❌ Background proxyless scrape error: {e}")
            import traceback
            traceback.print_exc()
    
    # Start as background task - returns immediately so bot stays responsive
    asyncio.create_task(background_scrape_proxyless())


async def send_results(chat_id, context, sites, proxies=None):
    """Send results with proxy rotation filtering"""
    # First, filter sites to only include working ones with products under $5
    if sites:
        print(f"\n🔍 **FILTERING {len(sites)} SITES FOR UNDER $5 PRODUCTS**")
        filtered_sites = filter_sites(
            sites, 
            max_workers=MAX_FILTER_WORKERS, 
            timeout=15, 
            check_products=True,
            proxies=proxies  # ← Pass proxies for rotation
        )
        
        if filtered_sites:
            sorted_sites = sorted(list(set(filtered_sites)))
            
            # Ensure all sites are saved to file before sending
            save_all_sites_to_file(sorted_sites)
            
            # Use absolute path for better Linux compatibility
            # Try multiple locations for better compatibility
            filename = None
            temp_locations = [
                os.path.join(tempfile.gettempdir(), f"shopify_under5_{len(sorted_sites)}_sites_{int(time.time())}.txt"),
                os.path.abspath(f"shopify_under5_{len(sorted_sites)}_sites_{int(time.time())}.txt"),
                os.path.join(os.getcwd(), f"shopify_under5_{len(sorted_sites)}_sites_{int(time.time())}.txt"),
            ]
            
            for temp_file in temp_locations:
                try:
                    # Write file with explicit encoding and flush
                    with open(temp_file, 'w', encoding='utf-8', errors='replace') as f:
                        for site in sorted_sites:
                            f.write(f"{site}\n")
                        f.flush()
                        os.fsync(f.fileno())  # Force write to disk (important for Linux)
                    filename = temp_file
                    break
                except Exception as e:
                    print(f"⚠️ Could not write to {temp_file}: {e}")
                    continue
            
            # Last resort: use sites.txt if it exists and other attempts failed
            if not filename and os.path.exists(_sites_file_path):
                filename = os.path.abspath(_sites_file_path)
                print(f"📁 Using sites.txt as fallback: {filename}")
            
            # Send file first to ensure it's always sent
            file_sent = False
            if filename and os.path.exists(filename):
                try:
                    with open(filename, 'rb') as f:
                        await context.bot.send_document(
                            chat_id, f,
                            filename=f"shopify_under5_{len(sorted_sites)}_sites.txt",
                            caption=f"💰 {len(sorted_sites)} SITES WITH PRODUCTS UNDER $5\n🔍 {len(SEARCH_ENGINES)} engines\n🚀 V6.2"
                        )
                    file_sent = True
                except Exception as e:
                    print(f"❌ File send error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Try to send file again if first attempt failed
                    try:
                        await asyncio.sleep(1)  # Brief delay before retry
                        with open(filename, 'rb') as f:
                            await context.bot.send_document(
                                chat_id, f,
                                filename=f"shopify_under5_{len(sorted_sites)}_sites.txt",
                                caption=f"💰 {len(sorted_sites)} SITES WITH PRODUCTS UNDER $5"
                            )
                        file_sent = True
                    except Exception as e2:
                        print(f"❌ File send error (retry): {e2}")
                        import traceback
                        traceback.print_exc()
                
                # Clean up temp file (but keep sites.txt)
                if filename != os.path.abspath(_sites_file_path):
                    try:
                        if os.path.exists(filename):
                            os.unlink(filename)
                    except Exception as e:
                        print(f"⚠️ Could not delete temp file: {e}")
            
            # Send sample message (use HTML to avoid Markdown parsing issues with URLs)
            sample = sorted_sites[:25]
            sample_text = f"💰 <b>{len(sorted_sites)} SITES WITH PRODUCTS UNDER $5</b>\n\n"
            
            for i, site in enumerate(sample, 1):
                # Escape HTML special characters in URLs
                escaped_site = site.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                sample_text += f"{i}. {escaped_site}\n"
                
            if len(sorted_sites) > 25:
                sample_text += f"\n📁 +{len(sorted_sites)-25} more in file"
            
            sample_text += f"\n\n🏆 <b>FILTERED FOR UNDER $5 PRODUCTS!</b> 🏆"
            
            try:
                await context.bot.send_message(chat_id, sample_text, parse_mode='HTML')
            except Exception as e:
                # Fallback to plain text if HTML also fails
                print(f"❌ Message error: {e}")
                try:
                    sample_text_plain = f"💰 {len(sorted_sites)} SITES WITH PRODUCTS UNDER $5:\n\n"
                    for i, site in enumerate(sample, 1):
                        sample_text_plain += f"{i}. {site}\n"
                    if len(sorted_sites) > 25:
                        sample_text_plain += f"\n📁 +{len(sorted_sites)-25} more in file"
                    sample_text_plain += f"\n\n🏆 FILTERED FOR UNDER $5 PRODUCTS! 🏆"
                    await context.bot.send_message(chat_id, sample_text_plain)
                except Exception as e2:
                    print(f"❌ Message error (retry): {e2}")
            
            # Clean up file if it wasn't deleted
            if os.path.exists(filename):
                try:
                    os.unlink(filename)
                except:
                    pass
        else:
            await context.bot.send_message(
                chat_id, 
                f"❌ **NO SITES WITH PRODUCTS UNDER $5 FOUND**\n\n"
                f"📊 Found {len(sites)} total sites, but none had products under $5\n\n"
                f"💡 Try:\n"
                f"• Running the scraper longer\n"
                f"• Using more proxies\n"
                f"• Adjusting the price filter"
            )
    else:
        await context.bot.send_message(
            chat_id, 
            "❌ **NO SITES FOUND**\n\n💡 Reasons:\n• Proxies don't work with search engines\n• Try different proxy source\n• Need higher quality proxies\n\n📁 Send better proxies to try again"
        )

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    proxyless_status = "✅ ON" if USE_PROXYLESS_IN_DUAL_MODE else "❌ OFF"
    await update.message.reply_text(
        f"🛍️ **SHOPIFY FINDER V6.2 (UNDER $5 FILTER)**\n\n"
        f"💰 **FILTER: Only sites with products under $5**\n\n"
        f"🚀 **COMMANDS:**\n"
        f"• `/proxyless` - NO proxies needed!\n"
        f"• `/done` - With proxies\n"
        f"• `/toggle` - Turn proxyless ON/OFF\n"
        f"• `/stop` - Stop & get results\n\n"
        f"⚡ **PROXYLESS IN DUAL MODE:** {proxyless_status}\n"
        f"(Use /toggle if your IP is blocked)\n\n"
        f"📁 **WITH PROXY MODE:**\n"
        f"1. Send proxy file(s) (.txt)\n"
        f"2. Select type: HTTP / SOCKS4 / SOCKS5\n"
        f"3. Type /done\n\n"
        f"🧦 **SOCKS SUPPORT:** HTTP, SOCKS4, SOCKS5\n"
        f"🔍 **ENGINES:** {len(SEARCH_ENGINES)} proxy + {len(PROXYLESS_ENGINES)} proxyless\n"
        f"💰 **FILTER:** Products under $5",
        parse_mode='Markdown'
    )
    user_data[chat_id] = {'proxy_files': [], 'all_proxies': set(), 'pending_file': None}
    stop_flags[chat_id] = False

async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in user_data or not user_data[chat_id].get('all_proxies'):
        await update.message.reply_text(
            "❌ **NO PROXIES LOADED**\n\n📁 Send proxy file(s) first, then use /done"
        )
        return
    
    all_proxies = list(user_data[chat_id]['all_proxies'])
    file_count = len(user_data[chat_id].get('proxy_files', []))
    
    await update.message.reply_text(
        f"✅ **BATCH PROCESSING STARTED**\n\n📁 Files received: {file_count}\n🌐 Total unique proxies: {len(all_proxies):,}\n🧪 Starting strict validation...",
        parse_mode='Markdown'
    )
    
    working = await test_proxies(chat_id, context, all_proxies)
    
    if not working:
        await context.bot.send_message(
            chat_id,
            "❌ **NO WORKING PROXIES**\n\n💡 All proxies failed strict testing\n🔍 Proxies must work with search engines\n📁 Try different proxy source"
        )
        user_data[chat_id] = {'proxy_files': [], 'all_proxies': set()}
        return
    
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8', errors='replace') as f:
            for proxy in working:
                f.write(f"{proxy.replace('http://', '')}\n")
            filename = f.name
        
        with open(filename, 'rb') as f:
            await context.bot.send_document(
                chat_id, f,
                filename=f"working_proxies_v40_{len(working)}.txt",
                caption=f"📁 {len(working)} validated proxies"
            )
        os.unlink(filename)
    except:
        pass
    
    await context.bot.send_message(
        chat_id,
        f"🚀 **LAUNCHING V6.2 ULTRA SCRAPER (UNDER $5)**\n\n"
        f"🔧 Working proxies: {len(working)}\n"
        f"🔍 Proxy engines: {len(SEARCH_ENGINES)}\n"
        f"🌐 Proxyless engines: {len(PROXYLESS_ENGINES)}\n"
        f"🎯 Keywords: {len(DORKS)}\n"
        f"👥 Proxy workers: {min(MAX_SCRAPE_WORKERS, len(working))}\n"
        f"👥 Proxyless workers: {len(PROXYLESS_ENGINES) * 3}\n"
        f"💰 Filter: Products under $5\n\n"
        f"⚡ DUAL MODE: PROXY + PROXYLESS\n"
        f"💡 /stop for instant results!"
    )
    
    # Run scraping as background task so bot stays responsive
    async def background_scrape():
        try:
            sites = await scrape_sites(chat_id, context, working)
            if not stop_flags.get(chat_id, False):
                try:
                    await send_results(chat_id, context, sites, used_proxies) 
                except Exception as e:
                    print(f"❌ Error sending results: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        await context.bot.send_message(
                            chat_id,
                            f"⚠️ Error sending results, but sites are saved to sites.txt\n\n🎯 Found: {len(sites)} sites\n💰 Filter: Products under $5\n📁 Check sites.txt file"
                        )
                    except:
                        pass
        except Exception as e:
            print(f"❌ Background scrape error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            user_data[chat_id] = {'proxy_files': [], 'all_proxies': set()}
    
    # Start as background task - returns immediately so bot stays responsive
    asyncio.create_task(background_scrape())

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    stop_flags[chat_id] = True
    if chat_id in user_data:
        user_data[chat_id]['scraping'] = False
    
    await update.message.reply_text(
        "🛑 **EMERGENCY STOP**\n\n⚡ Stopping workers...\n⏳ Collecting results...",
        parse_mode='Markdown'
    )
    
    await asyncio.sleep(2)
    
    sites = []
    if chat_id in user_data and 'found_sites' in user_data[chat_id]:
        sites = list(user_data[chat_id]['found_sites'])
    
    if sites:
        try:
            await send_results(chat_id, context, sites)
            await update.message.reply_text(
                f"✅ **STOPPED**\n\n💰 {len(sites)} sites with products under $5 delivered\n📁 Send new proxies to restart",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"❌ Error sending results: {e}")
            import traceback
            traceback.print_exc()
            try:
                await update.message.reply_text(
                    f"⚠️ **STOPPED**\n\n💰 {len(sites)} sites with products under $5 found\n📁 Sites saved to sites.txt\n\n⚠️ Error sending file: {str(e)[:200]}",
                    parse_mode='Markdown'
                )
            except:
                pass
    else:
        await update.message.reply_text(
            "🛑 **STOPPED**\n\n⚠️ No sites yet\n📁 Send proxies to restart"
        )

async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send current sites.txt file - works anytime, even during active scraping"""
    chat_id = update.effective_chat.id
    
    # Check if sites.txt exists
    sites_file = os.path.abspath(_sites_file_path)
    
    # Also check in-memory sites
    memory_sites = len(_saved_sites)
    
    if not os.path.exists(sites_file) and memory_sites == 0:
        await update.message.reply_text(
            "❌ **NO SITES FOUND**\n\n"
            "📁 sites.txt does not exist\n"
            "📝 No sites in memory\n"
            "💡 Run the scraper first to find sites",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Collect all sites from file and memory
        all_sites = set()
        
        # Read from file if exists
        if os.path.exists(sites_file):
            with open(sites_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    site = line.strip()
                    if site:
                        all_sites.add(site)
        
        # Add any sites from memory that might not be in file yet
        all_sites.update(_saved_sites)
        
        if not all_sites:
            await update.message.reply_text(
                "⚠️ **NO SITES YET**\n\n"
                "📁 File exists but is empty\n"
                "💡 Scraping may still be in progress...",
                parse_mode='Markdown'
            )
            return
        
        # Filter sites for under $5 products
        print(f"\n🔍 **FILTERING {len(all_sites)} SITES FOR UNDER $5 PRODUCTS**")
        filtered_sites = filter_sites(list(all_sites), max_workers=MAX_FILTER_WORKERS, timeout=15, check_products=True)
        
        if not filtered_sites:
            await update.message.reply_text(
                f"❌ **NO SITES WITH PRODUCTS UNDER $5**\n\n"
                f"📊 Found {len(all_sites)} total sites, but none had products under $5\n"
                f"💡 Try running the scraper longer",
                parse_mode='Markdown'
            )
            return
        
        site_count = len(filtered_sites)
        
        # Create temp file with all sites
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for site in sorted(filtered_sites):
                f.write(f"{site}\n")
            temp_path = f.name
        
        await update.message.reply_text(
            f"💰 **SENDING FILTERED SITES**\n\n"
            f"🎯 Sites with under $5 products: {site_count:,}\n"
            f"⏳ Uploading...",
            parse_mode='Markdown'
        )
        
        # Send the file
        with open(temp_path, 'rb') as f:
            await context.bot.send_document(
                chat_id,
                f,
                filename=f"shopify_under5_{site_count}.txt",
                caption=f"💰 **{site_count:,} SITES WITH PRODUCTS UNDER $5**\n\n"
                        f"🔍 Engines: {len(SEARCH_ENGINES)} proxy + {len(PROXYLESS_ENGINES)} proxyless\n"
                        f"🚀 Shopify Finder V6.2"
            )
        
        # Cleanup temp file
        try:
            os.unlink(temp_path)
        except:
            pass
        
        await context.bot.send_message(
            chat_id,
            f"✅ **SENT SUCCESSFULLY**\n\n💰 {site_count:,} sites with products under $5",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **ERROR**\n\n{str(e)[:200]}",
            parse_mode='Markdown'
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    doc = update.message.document
    if not doc.file_name.lower().endswith('.txt'):
        await update.message.reply_text("❌ Send .txt files only!")
        return
    
    if chat_id not in user_data:
        user_data[chat_id] = {'proxy_files': [], 'all_proxies': set(), 'pending_file': None}
    
    # Download and store file content temporarily
    try:
        file = await context.bot.get_file(doc.file_id)
        content = (await file.download_as_bytearray()).decode('utf-8', errors='ignore')
        
        # Count valid proxy lines
        proxy_lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith('#')]
        
        if not proxy_lines:
            await update.message.reply_text("❌ No valid proxy lines found in file!")
            return
        
        # Store pending file info
        user_data[chat_id]['pending_file'] = {
            'name': doc.file_name,
            'content': content,
            'count': len(proxy_lines)
        }
        
        # Ask for proxy type
        keyboard = [
            [
                InlineKeyboardButton("🌐 HTTP", callback_data="proxy_type:http"),
                InlineKeyboardButton("🧦 SOCKS4", callback_data="proxy_type:socks4"),
            ],
            [
                InlineKeyboardButton("🧦 SOCKS5", callback_data="proxy_type:socks5"),
                InlineKeyboardButton("🌀 MIX", callback_data="proxy_type:mix")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Escape underscores for Markdown
        safe_filename = doc.file_name.replace('_', '\\_')
        
        await update.message.reply_text(
            f"📁 **FILE RECEIVED**\n\n"
            f"📄 File: {safe_filename}\n"
            f"📊 Proxies found: {len(proxy_lines):,}\n\n"
            f"🔧 **What type of proxies are these?**\n"
            f"(Use MIX if file has socks4://, socks5://, http:// prefixes)",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")


async def handle_proxy_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle proxy type selection from inline keyboard"""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    
    if not query.data.startswith("proxy_type:"):
        return
    
    proxy_type = query.data.split(":")[1]  # http, socks4, or socks5
    
    if chat_id not in user_data or not user_data[chat_id].get('pending_file'):
        await query.edit_message_text("❌ No pending file. Please send a proxy file first.")
        return
    
    pending = user_data[chat_id]['pending_file']
    content = pending['content']
    filename = pending['name']
    
    # Escape underscores for Markdown
    safe_filename = filename.replace('_', '\\_')
    
    # Parse proxies with selected type
    valid = []
    for line in content.splitlines():
        proxy = parse_proxy(line, proxy_type)
        if proxy and proxy not in user_data[chat_id]['all_proxies']:
            valid.append(proxy)
            user_data[chat_id]['all_proxies'].add(proxy)
    
    # Clear pending file
    user_data[chat_id]['pending_file'] = None
    
    if not valid:
        await query.edit_message_text(
            f"⚠️ **NO NEW PROXIES**\n\n"
            f"All proxies from {safe_filename} were duplicates or invalid\n\n"
            f"📊 Total unique: {len(user_data[chat_id]['all_proxies']):,}",
            parse_mode='Markdown'
        )
        return
    
    user_data[chat_id]['proxy_files'].append(filename)
    
    file_count = len(user_data[chat_id]['proxy_files'])
    total_unique = len(user_data[chat_id]['all_proxies'])
    
    # Set emoji based on type
    if proxy_type == "http":
        type_emoji = "🌐"
    elif proxy_type == "mix":
        type_emoji = "🌀"
    else:
        type_emoji = "🧦"
    type_name = proxy_type.upper()
    
    await query.edit_message_text(
        f"✅ **{type_name} PROXIES LOADED**\n\n"
        f"📁 File: {safe_filename}\n"
        f"{type_emoji} Type: {type_name}\n"
        f"➕ New proxies: {len(valid):,}\n"
        f"📊 Total unique: {total_unique:,}\n"
        f"📂 Files loaded: {file_count}\n\n"
        f"💡 Send more files or type /done to start!",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📁 **SEND PROXY FILES**\n\n1. Send one or more .txt files\n2. Type /done when ready\n3. Use /start for info"
    )

def load_proxies_from_file(filepath):
    proxies = set()
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return proxies
    
    print(f"📥 Loading proxies from: {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                proxy = parse_proxy(line.strip())
                if proxy:
                    proxies.add(proxy)
        print(f"✅ Loaded {len(proxies):,} unique proxies")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
    return proxies

def console_test_proxies(proxy_list):
    working = []
    tested = 0
    total = len(proxy_list)
    lock = threading.Lock()
    
    print(f"\n🧪 **TESTING {total:,} PROXIES**")
    print(f"✅ Testing with REAL search queries")
    print(f"⚡ Only proxies that work with search engines will pass\n")
    
    def worker():
        nonlocal tested
        while True:
            try:
                proxy = q.get_nowait()
                if test_proxy_with_search(proxy):
                    with lock:
                        working.append(proxy)
                        print(f"✅ [{len(working)}/{tested}] Working proxy found")
                with lock:
                    tested += 1
                    if tested % 10 == 0:
                        print(f"📊 Progress: {tested:,}/{total:,} ({tested/total*100:.1f}%) | Working: {len(working)} ({len(working)/tested*100:.1f}%)")
                q.task_done()
            except queue.Empty:
                break
            except:
                with lock:
                    tested += 1
                q.task_done()
    
    q = queue.Queue()
    for proxy in proxy_list:
        q.put(proxy)
    
    with ThreadPoolExecutor(max_workers=min(MAX_PROXY_WORKERS, total)) as executor:
        futures = [executor.submit(worker) for _ in range(min(MAX_PROXY_WORKERS, total))]
        
        while not all(f.done() for f in futures):
            time.sleep(2)
    
    print(f"\n✅ **TESTING COMPLETE**")
    print(f"🎯 Found: {len(working)}/{total} working proxies")
    print(f"📊 Success rate: {len(working)/total*100:.1f}%")
    print(f"🚀 Ready for scraping!\n")
    
    return working

def console_scrape_sites(proxies):
    found = set()
    searches = 0
    failed_proxies = set()
    lock = threading.Lock()
    start_time = time.time()
    stop_flag = threading.Event()
    
    print(f"🔍 **MULTI-ENGINE SCRAPER V6.2 (UNDER $5)**\n")
    print(f"🎯 Keywords: {len(DORKS):,}")
    print(f"🌐 Proxies: {len(proxies):,}")
    print(f"🔍 Search Engines: {len(SEARCH_ENGINES)}")
    print(f"⚡ Workers: {min(MAX_SCRAPE_WORKERS, len(proxies))}")
    print(f"📄 Pages per search: 50 (for maximum coverage)")
    print(f"💰 Filter: Products under $5")
    print(f"💪 Starting...\n")
    print("💡 Press Ctrl+C to stop and get results\n")
    
    proxy_pool = proxies.copy()
    random.shuffle(proxy_pool)
    proxy_index = 0
    
    def get_next_proxy():
        nonlocal proxy_index
        if not proxy_pool:
            return None
        
        attempts = 0
        while attempts < len(proxy_pool):
            proxy = proxy_pool[proxy_index % len(proxy_pool)]
            proxy_index += 1
            
            if proxy not in failed_proxies:
                return proxy
            attempts += 1
        return None
    
    def scraper_worker():
        nonlocal searches
        worker_found = 0
        consecutive_failures = 0
        
        for search_count in range(10000):
            if stop_flag.is_set():
                break
            
            if consecutive_failures >= 500:
                consecutive_failures = 0  # Reset instead of stopping
                time.sleep(0.5)
                
            try:
                query = random.choice(DORKS)
                proxy = get_next_proxy()
                
                if not proxy:
                    # Reset failed proxies and try again
                    failed_proxies.clear()
                    proxy = get_next_proxy()
                    if not proxy:
                        break
                
                if stop_flag.is_set():
                    break
                    
                urls = search_with_proxy(query, proxy, chat_id)
                
                if stop_flag.is_set():
                    break
                
                if urls:
                    consecutive_failures = 0
                    with lock:
                        searches += 1
                        for url in urls:
                            if url not in found:
                                found.add(url)
                                worker_found += 1
                                print(f"✅ [{len(found)}] {url}")
                                # Save site immediately to file
                                save_site_to_file(url)
                else:
                    consecutive_failures += 1
                    with lock:
                        searches += 1
                        # DON'T mark proxy as failed
                
                time.sleep(random.uniform(0.005, 0.02))
                
            except Exception as e:
                consecutive_failures += 1
                with lock:
                    searches += 1
                time.sleep(0.01)
                continue
        
        return worker_found
    
    workers = min(MAX_SCRAPE_WORKERS, len(proxies))
    futures = []
    
    # Start periodic saving task (every 10 seconds)
    last_periodic_save = time.time()
    periodic_save_interval = 10.0
    
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(scraper_worker) for _ in range(workers)]
            
            last_update = time.time()
            
            while not all(future.done() for future in futures):
                time.sleep(2)
                current = time.time()
                
                # Periodic save every 10 seconds
                if current - last_periodic_save >= periodic_save_interval:
                    with lock:
                        if found:
                            save_all_sites_to_file(list(found))
                    last_periodic_save = current
                
                if current - last_update >= 2:
                    with lock:
                        elapsed = current - start_time
                        rate = len(found) / max(1, searches) if searches > 0 else 0
                        sites_per_min = (len(found) / max(1, elapsed)) * 60
                        active_proxies = len(proxy_pool) - len(failed_proxies)
                        
                        print(f"\r🔥 FOUND: {len(found):,} SITES | Searches: {searches:,} | Hit rate: {rate:.3f} | Speed: {sites_per_min:.1f}/min | Time: {elapsed:.0f}s | Active proxies: {active_proxies}/{len(proxy_pool)}", end='', flush=True)
                        last_update = current
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping workers...")
        stop_flag.set()
        if futures:
            for future in futures:
                if not future.done():
                    future.cancel()
    
    # Final save of all sites before returning
    with lock:
        if found:
            save_all_sites_to_file(list(found))
    
    elapsed = time.time() - start_time
    sites_per_min = (len(found) / max(1, elapsed)) * 60
    
    print(f"\n\n🎉 **SCRAPING COMPLETE**\n")
    print(f"🎯 **{len(found):,} SHOPIFY SITES FOUND**")
    print(f"📊 Searches: {searches:,}")
    print(f"⚡ Success: {len(found)/max(1,searches):.3f}")
    print(f"🚀 Speed: {sites_per_min:.1f}/min")
    print(f"💰 Filter: Products under $5")
    print(f"📁 Sites saved to: {os.path.abspath(_sites_file_path)}")
    print(f"⏱️  Time: {elapsed:.1f}s")
    print(f"🔑 {len(DORKS):,} keywords\n")
    
    return list(found)

def save_results_to_file(sites, output_file=None):
    if not sites:
        print("❌ No sites to save")
        return
    
    # Filter sites for under $5 products
    print(f"\n🔍 **FILTERING {len(sites)} SITES FOR UNDER $5 PRODUCTS**")
    filtered_sites = filter_sites(sites, max_workers=MAX_FILTER_WORKERS, timeout=15, check_products=True)
    
    if not filtered_sites:
        print("❌ No sites with products under $5 found")
        return
    
    if not output_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"shopify_under5_{len(filtered_sites)}_{timestamp}.txt"
    
    sorted_sites = sorted(list(set(filtered_sites)))
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            for site in sorted_sites:
                f.write(f"{site}\n")
        
        print(f"✅ Results saved to: {output_file}")
        print(f"💰 {len(sorted_sites):,} sites with products under $5")
        return output_file
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None

def console_mode(proxy_file, output_file=None, skip_test=False):
    print("=" * 80)
    print("🚀 Shopify Multi-Engine Scraper V6.2 - CONSOLE MODE (UNDER $5)")
    print("=" * 80)
    print(f"🔍 Search Engines: {len(SEARCH_ENGINES)}")
    for engine in SEARCH_ENGINES:
        print(f"  • {engine['name']} ({engine['weight']*100:.0f}%)")
    print(f"🔑 Keywords: {len(DORKS):,}")
    print(f"💰 Filter: Products under $5")
    print(f"✅ Strict proxy validation: ENABLED")
    print(f"🔄 Batch processing: ENABLED")
    print(f"🚫 Auto-deduplication: ENABLED")
    print(f"📄 Pages per search: 50 (for maximum coverage)")
    print("=" * 80)
    print()
    
    all_proxies = load_proxies_from_file(proxy_file)
    if not all_proxies:
        print("❌ No valid proxies found. Exiting.")
        return
    
    if not skip_test:
        working = console_test_proxies(all_proxies)
    else:
        print("⚠️  Skipping proxy testing (--skip-test)")
        working = list(all_proxies)
    
    if not working:
        print("❌ No working proxies found. Exiting.")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    working_proxy_file = f"working_proxies_{len(working)}_{timestamp}.txt"
    with open(working_proxy_file, 'w', encoding='utf-8') as f:
        for proxy in working:
            f.write(f"{proxy.replace('http://', '')}\n")
    print(f"💾 Working proxies saved to: {working_proxy_file}\n")
    
    sites = console_scrape_sites(working)
    
    if sites:
        save_results_to_file(sites, output_file)
    else:
        print("❌ No sites found")

async def main_async():
    if not TELEGRAM_AVAILABLE:
        print("❌ Error: Telegram library not available")
        return
    
    print("=" * 80)
    print("🚀 Shopify Multi-Engine Scraper V6.2 (UNDER $5 FILTER)")
    print("=" * 80)
    print(f"🔍 Search Engines: {len(SEARCH_ENGINES)}")
    for engine in SEARCH_ENGINES:
        print(f"  • {engine['name']} ({engine['weight']*100:.0f}%)")
    print(f"🔑 Keywords: {len(DORKS)}")
    print(f"💰 Filter: Products under $5")
    print(f"✅ Strict proxy validation: ENABLED")
    print(f"🔄 Batch processing: ENABLED")
    print(f"🚫 Auto-deduplication: ENABLED")
    print("=" * 80)
    
    # Enable concurrent updates so /send works during scraping
    app = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("send", send_cmd))
    app.add_handler(CommandHandler("proxyless", proxyless_cmd))
    app.add_handler(CommandHandler("toggle", toggle_cmd))  # Toggle proxyless on/off
    app.add_handler(CallbackQueryHandler(handle_proxy_type_callback, pattern="^proxy_type:"))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Bot V6.2 (UNDER $5) is LIVE!")
    print("🚀 Commands: /proxyless, /toggle, /send")
    print(f"🌐 Proxyless engines: {len(PROXYLESS_ENGINES)}")
    print(f"🔄 Proxyless in dual mode: {'ON' if USE_PROXYLESS_IN_DUAL_MODE else 'OFF'}")
    print(f"💰 Filter: Products under $5")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

def main():
    parser = argparse.ArgumentParser(
        description='Shopify Scraper V6.2 - Under $5 Filter Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python shfinder2.1.py --console --proxies proxies.txt
  python shfinder2.1.py --console --proxies proxies.txt --output results.txt
  python shfinder2.1.py --console --proxies proxies.txt --skip-test
  python shfinder2.1.py
  python shfinder2.1.py --bot
        """
    )
    
    parser.add_argument(
        '--console', '-c',
        action='store_true',
        help='Run in console/CLI mode instead of Telegram bot mode'
    )
    
    parser.add_argument(
        '--proxies', '-p',
        type=str,
        help='Path to proxy file (required for console mode)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output file for results (optional, auto-generated if not specified)'
    )
    
    parser.add_argument(
        '--skip-test',
        action='store_true',
        help='Skip proxy testing (use all proxies directly)'
    )
    
    parser.add_argument(
        '--bot', '-b',
        action='store_true',
        help='Run in Telegram bot mode (default)'
    )
    
    args = parser.parse_args()
    
    if args.console:
        if not args.proxies:
            print("❌ Error: --proxies is required for console mode")
            print("💡 Usage: python shfinder2.1.py --console --proxies proxies.txt")
            sys.exit(1)
        
        try:
            console_mode(
                proxy_file=args.proxies,
                output_file=args.output,
                skip_test=args.skip_test
            )
        except KeyboardInterrupt:
            print("\n\n🛑 Scraping stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    elif args.bot or not args.console:
        if not TELEGRAM_AVAILABLE:
            print("❌ Error: Telegram library not installed")
            print("💡 Install with: pip install python-telegram-bot")
            print("💡 Or use console mode: python shfinder2.1.py --console --proxies proxies.txt")
            sys.exit(1)
        
        try:
            # Check if we're already in an async context
            try:
                # If there's a running loop, we can't use asyncio.run()
                loop = asyncio.get_running_loop()
                # If we get here, there's a loop - this shouldn't happen in main()
                # but handle it gracefully
                import nest_asyncio
                nest_asyncio.apply()
                asyncio.run(main_async())
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                asyncio.run(main_async())
        except KeyboardInterrupt:
            print("\n🛑 V6.2 stopped")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()