"""
Collect hackathon data from multiple platforms: Unstop, HackerEarth, MLH.
Merges with existing Devpost data for a comprehensive multi-platform dataset.

Platforms:
1. Unstop     - API: /api/public/opportunity/search-new  (~5,700 hackathons)
2. HackerEarth - Chrome extension API (limited current events)  
3. MLH        - Web scraping seasons pages (~200+ events across years)
"""

import requests
import json
import csv
import time
import re
import sys
import os
from datetime import datetime
from collections import Counter
from typing import Any

# ─── Configuration ────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
})

# ─── Utility ──────────────────────────────────────────────────────────────
def safe_print(msg: str):
    """Print with ASCII-safe encoding for Windows console."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))

def parse_date(date_str: str | None) -> str:
    """Try to parse a date string into ISO format."""
    if not date_str:
        return ""
    try:
        # Handle Unstop format: "2026-05-20T00:00:00+05:30"
        if "T" in date_str:
            return date_str[:10]
        return date_str
    except Exception:
        return str(date_str)

def classify_prize_tier(amount: float) -> str:
    """Classify prize amount into tiers."""
    if amount <= 0:
        return "no_prize"
    elif amount < 100:
        return "micro"
    elif amount < 1000:
        return "small"
    elif amount < 10000:
        return "medium"
    elif amount < 50000:
        return "large"
    else:
        return "mega"

# ═══════════════════════════════════════════════════════════════════════════
# 1. UNSTOP COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════

def collect_unstop() -> list[dict]:
    """Collect all hackathon data from Unstop API."""
    safe_print("\n" + "=" * 70)
    safe_print("  UNSTOP - Collecting Hackathon Data")
    safe_print("=" * 70)
    
    all_records = []
    page = 1
    per_page = 100
    total_pages = None
    
    while True:
        try:
            r = SESSION.get(
                "https://unstop.com/api/public/opportunity/search-new",
                params={
                    "opportunity": "hackathons",
                    "per_page": per_page,
                    "page": page,
                    "oppstatus": "all",  # Gets all (live + expired)
                },
                timeout=20,
            )
            r.raise_for_status()
            data = r.json().get("data", {})
            
            if total_pages is None:
                total_pages = data.get("last_page", 1)
                total_count = data.get("total", 0)
                safe_print(f"  Total hackathons available: {total_count}")
                safe_print(f"  Total pages: {total_pages}")
            
            items = data.get("data", [])
            if not items:
                break
                
            for item in items:
                if isinstance(item, dict):
                    record = _parse_unstop_item(item)
                    if record:
                        all_records.append(record)
            
            safe_print(f"  Page {page}/{total_pages}: collected {len(items)} items (total: {len(all_records)})")
            
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.8)  # Rate limiting
            
        except requests.exceptions.RequestException as e:
            safe_print(f"  ERROR on page {page}: {e}")
            if page > 3:  # Skip after initial failures
                if total_pages and page >= total_pages:
                    break
                page += 1
                time.sleep(2)
                continue
            break
        except Exception as e:
            safe_print(f"  UNEXPECTED ERROR on page {page}: {e}")
            if total_pages and page >= total_pages:
                break
            page += 1
            time.sleep(2)
            continue
    
    safe_print(f"\n  UNSTOP TOTAL: {len(all_records)} records collected")
    return all_records


def _parse_unstop_item(item: dict) -> dict:
    """Parse a single Unstop API item into a normalized record."""
    org = item.get("organisation", {})
    if not isinstance(org, dict):
        org = {"name": str(org)} if org else {}
        
    regn = item.get("regnRequirements", {})
    if not isinstance(regn, dict):
        regn = {}
        
    prizes = item.get("prizes", [])
    if not isinstance(prizes, list):
        prizes = []
    
    # Calculate total prize money (convert INR to USD roughly)
    total_prize = 0
    prize_currency = ""
    for p in prizes:
        if not isinstance(p, dict):
            continue
        cash = p.get("cash", 0) or 0
        currency = p.get("currency", "") or ""
        if currency == "fa-rupee":
            total_prize += cash  # Keep in INR for now
            prize_currency = "INR"
        elif currency == "fa-dollar":
            total_prize += cash
            prize_currency = "USD"
        else:
            total_prize += cash
            prize_currency = currency or "UNKNOWN"
    
    # Convert INR to USD for consistent comparison (1 USD ~ 83 INR)
    prize_usd = total_prize / 83.0 if prize_currency == "INR" else total_prize
    
    # Parse dates
    start_date = parse_date(item.get("start_date"))
    end_date = parse_date(item.get("end_date"))
    regn_start = parse_date(regn.get("start_regn_dt"))
    regn_end = parse_date(regn.get("end_regn_dt"))
    
    # Determine status based on dates (since Unstop API reports raw status "LIVE" for past events)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    raw_status = (item.get("status") or "").upper()
    
    if end_date and end_date < today_str:
        status = "ended"
    elif regn_end and regn_end < today_str:
        status = "ended"
    elif raw_status in ("CLOSED", "EXPIRED", "ENDED"):
        status = "ended"
    elif start_date and start_date > today_str:
        status = "upcoming"
    elif raw_status in ("LIVE", "OPEN"):
        status = "open"
    elif raw_status == "UPCOMING":
        status = "upcoming"
    else:
        status = raw_status.lower() or "unknown"
    
    # Region/online detection
    region = (item.get("region") or "").lower()
    is_online = region in ("online", "virtual", "")
    
    # Tags and themes
    raw_tags = item.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = []
    tags = []
    for t in raw_tags:
        if isinstance(t, dict):
            tags.append(t.get("name", "") or "")
        elif isinstance(t, str):
            tags.append(t)
            
    raw_fields = item.get("fields", [])
    if not isinstance(raw_fields, list):
        raw_fields = []
    fields = []
    for f in raw_fields:
        if isinstance(f, dict):
            fields.append(f.get("name", "") or "")
        elif isinstance(f, str):
            fields.append(f)
    
    # Team size
    min_team = regn.get("min_team_size", 1) or 1
    max_team = regn.get("max_team_size", 1) or 1
    
    # Subtype classification
    subtype = (item.get("subtype") or "").lower()
    
    return {
        "id": f"unstop_{item.get('id', '')}",
        "platform_id": str(item.get("id", "")),
        "name": (item.get("title") or "").strip(),
        "url": f"https://unstop.com/{item.get('public_url', '')}",
        "platform": "unstop",
        "status": status,
        "status_detail": raw_status.lower(),
        "organizer": (org.get("name") or "").strip(),
        "organizer_type": _classify_unstop_org(org, item),
        "location": region if not is_online else "online",
        "is_online": is_online,
        "participant_count": item.get("registerCount", 0) or 0,
        "views_count": item.get("viewsCount", 0) or 0,
        "prize_amount_raw": f"{prize_currency} {total_prize}" if total_prize > 0 else "",
        "prize_amount_numeric": round(prize_usd, 2),
        "prize_currency": prize_currency,
        "prize_tier": classify_prize_tier(prize_usd),
        "prize_count": len(prizes),
        "start_date": start_date,
        "end_date": end_date,
        "registration_start": regn_start,
        "registration_end": regn_end,
        "min_team_size": min_team,
        "max_team_size": max_team,
        "subtype": subtype,
        "is_paid": item.get("isPaid", False),
        "tags": "|".join(tags[:5]),
        "fields": "|".join(fields[:5]),
        "themes": "|".join(tags[:3] + fields[:3]),
        "theme_count": len(set(tags + fields)),
        "has_cash_prize": total_prize > 0,
        "is_beginner_friendly": any(
            kw in " ".join(tags + fields).lower()
            for kw in ["beginner", "intro", "starter", "first", "learn"]
        ),
        "is_ai_ml": any(
            kw in " ".join(tags + fields + [item.get("title", "")]).lower()
            for kw in ["ai", "machine learning", "ml", "deep learning", "nlp", "llm", "generative"]
        ),
        "is_social_good": any(
            kw in " ".join(tags + fields + [item.get("title", "")]).lower()
            for kw in ["social", "impact", "sustainability", "environment", "health", "education", "ngo"]
        ),
        "is_web": any(
            kw in " ".join(tags + fields).lower()
            for kw in ["web", "frontend", "fullstack", "javascript", "react"]
        ),
        "is_mobile": any(
            kw in " ".join(tags + fields).lower()
            for kw in ["mobile", "android", "ios", "flutter", "react native"]
        ),
        "is_fintech": any(
            kw in " ".join(tags + fields + [item.get("title", "")]).lower()
            for kw in ["fintech", "finance", "banking", "payment", "crypto", "defi"]
        ),
        "is_blockchain": any(
            kw in " ".join(tags + fields + [item.get("title", "")]).lower()
            for kw in ["blockchain", "web3", "crypto", "nft", "defi", "ethereum", "solidity"]
        ),
        "is_cybersecurity": any(
            kw in " ".join(tags + fields + [item.get("title", "")]).lower()
            for kw in ["security", "cyber", "ctf", "hack", "vulnerability", "penetration"]
        ),
        "collected_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "unstop_api",
        "is_synthetic": False,
    }


def _classify_unstop_org(org: dict, item: dict) -> str:
    """Classify Unstop organizer type."""
    name = (org.get("name") or "").lower()
    title = (item.get("title") or "").lower()
    
    edu_keywords = ["university", "college", "institute", "iit", "nit", "bits", "iiit", 
                     "school", "academy", "education", "campus", "student"]
    corp_keywords = ["google", "microsoft", "amazon", "meta", "apple", "ibm", "intel",
                     "samsung", "nvidia", "cisco", "oracle", "sap", "infosys", "tcs",
                     "wipro", "accenture", "deloitte", "jpmorgan", "goldman"]
    startup_keywords = ["startup", "labs", "tech", "io", "ventures", "hub"]
    community_keywords = ["community", "club", "society", "group", "chapter", "gdsc", "gdg"]
    
    combined = f"{name} {title}"
    if any(kw in combined for kw in edu_keywords):
        return "educational"
    if any(kw in combined for kw in corp_keywords):
        return "corporate"
    if any(kw in combined for kw in community_keywords):
        return "community"
    if any(kw in combined for kw in startup_keywords):
        return "startup"
    return "independent"


# ═══════════════════════════════════════════════════════════════════════════
# 2. HACKEREARTH COLLECTOR
# ═══════════════════════════════════════════════════════════════════════════

def collect_hackerearth() -> list[dict]:
    """Collect hackathon data from HackerEarth chrome extension API."""
    safe_print("\n" + "=" * 70)
    safe_print("  HACKEREARTH - Collecting Hackathon Data")
    safe_print("=" * 70)
    
    records = []
    try:
        r = SESSION.get(
            "https://www.hackerearth.com/chrome-extension/events/",
            timeout=20,
        )
        r.raise_for_status()
        events = r.json().get("response", [])
        safe_print(f"  Found {len(events)} events")
        
        for event in events:
            record = _parse_hackerearth_event(event)
            records.append(record)
            
    except Exception as e:
        safe_print(f"  ERROR: {e}")
    
    safe_print(f"  HACKEREARTH TOTAL: {len(records)} records collected")
    return records


def _parse_hackerearth_event(event: dict) -> dict:
    """Parse a HackerEarth event into normalized format."""
    status_raw = (event.get("status") or "").upper()
    if status_raw == "ONGOING":
        status = "open"
    elif status_raw == "UPCOMING":
        status = "upcoming"
    else:
        status = "ended"
    
    # Parse dates
    start_date = parse_date(event.get("start_tz", ""))
    end_date = parse_date(event.get("end_tz", ""))
    
    title = event.get("title", "")
    
    return {
        "id": f"hackerearth_{hash(event.get('url', '')) % 10**8}",
        "platform_id": str(hash(event.get("url", "")) % 10**8),
        "name": title,
        "url": event.get("url", ""),
        "platform": "hackerearth",
        "status": status,
        "status_detail": status_raw.lower(),
        "organizer": "HackerEarth",
        "organizer_type": "platform",
        "location": "online",
        "is_online": True,
        "participant_count": 0,
        "views_count": 0,
        "prize_amount_raw": "",
        "prize_amount_numeric": 0,
        "prize_currency": "",
        "prize_tier": "no_prize",
        "prize_count": 0,
        "start_date": start_date,
        "end_date": end_date,
        "registration_start": "",
        "registration_end": "",
        "min_team_size": 1,
        "max_team_size": 1,
        "subtype": event.get("challenge_type", ""),
        "is_paid": False,
        "tags": "",
        "fields": "",
        "themes": "",
        "theme_count": 0,
        "has_cash_prize": False,
        "is_beginner_friendly": False,
        "is_ai_ml": any(kw in title.lower() for kw in ["ai", "ml", "machine learning"]),
        "is_social_good": False,
        "is_web": False,
        "is_mobile": False,
        "is_fintech": False,
        "is_blockchain": False,
        "is_cybersecurity": any(kw in title.lower() for kw in ["security", "cyber", "ctf"]),
        "collected_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "hackerearth_api",
        "is_synthetic": False,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. MLH COLLECTOR (Web Scraping)
# ═══════════════════════════════════════════════════════════════════════════

def collect_mlh() -> list[dict]:
    """Collect hackathon data from MLH seasons pages."""
    safe_print("\n" + "=" * 70)
    safe_print("  MLH - Collecting Hackathon Data (Web Scraping)")
    safe_print("=" * 70)
    
    records = []
    # MLH seasons from 2022 to 2026
    seasons = [
        "https://mlh.io/seasons/2026/events",
        "https://mlh.io/seasons/2025/events",
        "https://mlh.io/seasons/2024/events",
        "https://mlh.io/seasons/2023/events",
        "https://mlh.io/seasons/2022/events",
    ]
    
    for season_url in seasons:
        try:
            safe_print(f"  Fetching: {season_url}")
            r = SESSION.get(season_url, timeout=30)
            if r.status_code != 200:
                safe_print(f"    HTTP {r.status_code}")
                continue
            
            events = _parse_mlh_page(r.text, season_url)
            records.extend(events)
            safe_print(f"    Found {len(events)} events")
            time.sleep(1)
            
        except requests.exceptions.Timeout:
            safe_print(f"    TIMEOUT - skipping")
        except Exception as e:
            safe_print(f"    ERROR: {e}")
    
    safe_print(f"  MLH TOTAL: {len(records)} records collected")
    return records


def _parse_mlh_page(html: str, season_url: str) -> list[dict]:
    """Parse MLH events page HTML to extract hackathon data."""
    events = []
    year_match = re.search(r"/seasons/(\d{4})/", season_url)
    season_year = year_match.group(1) if year_match else "unknown"
    
    # MLH uses event cards with specific class patterns
    # Look for event entries using regex on the HTML
    event_blocks = re.findall(
        r'<div[^>]*class="[^"]*event[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        html, re.DOTALL | re.IGNORECASE
    )
    
    # Alternative: extract individual event URLs and names
    event_links = re.findall(
        r'<a[^>]*href="(https?://[^"]*)"[^>]*>.*?<h3[^>]*>(.*?)</h3>',
        html, re.DOTALL | re.IGNORECASE
    )
    
    if not event_links:
        # Try another pattern
        event_links = re.findall(
            r'<h3[^>]*class="[^"]*event-name[^"]*"[^>]*>(.*?)</h3>.*?'
            r'<p[^>]*class="[^"]*event-date[^"]*"[^>]*>(.*?)</p>.*?'
            r'<p[^>]*class="[^"]*event-location[^"]*"[^>]*>(.*?)</p>',
            html, re.DOTALL | re.IGNORECASE
        )
        
        for match in event_links:
            if len(match) >= 3:
                name, date_str, location = match[0].strip(), match[1].strip(), match[2].strip()
                name = re.sub(r'<[^>]+>', '', name).strip()
                date_str = re.sub(r'<[^>]+>', '', date_str).strip()
                location = re.sub(r'<[^>]+>', '', location).strip()
                
                is_online = "digital" in location.lower() or "virtual" in location.lower() or "online" in location.lower()
                
                events.append({
                    "id": f"mlh_{hash(name + season_year) % 10**8}",
                    "platform_id": str(hash(name + season_year) % 10**8),
                    "name": name,
                    "url": season_url,
                    "platform": "mlh",
                    "status": "ended" if int(season_year) < 2026 else "open",
                    "status_detail": f"season_{season_year}",
                    "organizer": "MLH",
                    "organizer_type": "mlh_official",
                    "location": location or "online",
                    "is_online": is_online,
                    "participant_count": 0,
                    "views_count": 0,
                    "prize_amount_raw": "",
                    "prize_amount_numeric": 0,
                    "prize_currency": "",
                    "prize_tier": "no_prize",
                    "prize_count": 0,
                    "start_date": "",
                    "end_date": "",
                    "registration_start": "",
                    "registration_end": "",
                    "min_team_size": 1,
                    "max_team_size": 5,
                    "subtype": "hackathon",
                    "is_paid": False,
                    "tags": f"mlh|season_{season_year}",
                    "fields": "",
                    "themes": f"mlh_season_{season_year}",
                    "theme_count": 1,
                    "has_cash_prize": False,
                    "is_beginner_friendly": True,
                    "is_ai_ml": False,
                    "is_social_good": False,
                    "is_web": False,
                    "is_mobile": False,
                    "is_fintech": False,
                    "is_blockchain": False,
                    "is_cybersecurity": False,
                    "collected_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "data_source": "mlh_scrape",
                    "is_synthetic": False,
                })
    else:
        for url, name in event_links:
            name = re.sub(r'<[^>]+>', '', name).strip()
            events.append({
                "id": f"mlh_{hash(name + season_year) % 10**8}",
                "platform_id": str(hash(name + season_year) % 10**8),
                "name": name,
                "url": url,
                "platform": "mlh",
                "status": "ended" if int(season_year) < 2026 else "open",
                "status_detail": f"season_{season_year}",
                "organizer": "MLH",
                "organizer_type": "mlh_official",
                "location": "online",
                "is_online": True,
                "participant_count": 0,
                "views_count": 0,
                "prize_amount_raw": "",
                "prize_amount_numeric": 0,
                "prize_currency": "",
                "prize_tier": "no_prize",
                "prize_count": 0,
                "start_date": "",
                "end_date": "",
                "registration_start": "",
                "registration_end": "",
                "min_team_size": 1,
                "max_team_size": 5,
                "subtype": "hackathon",
                "is_paid": False,
                "tags": f"mlh|season_{season_year}",
                "fields": "",
                "themes": f"mlh_season_{season_year}",
                "theme_count": 1,
                "has_cash_prize": False,
                "is_beginner_friendly": True,
                "is_ai_ml": False,
                "is_social_good": False,
                "is_web": False,
                "is_mobile": False,
                "is_fintech": False,
                "is_blockchain": False,
                "is_cybersecurity": False,
                "collected_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "mlh_scrape",
                "is_synthetic": False,
            })
    
    return events


# ═══════════════════════════════════════════════════════════════════════════
# 4. MERGE & SAVE
# ═══════════════════════════════════════════════════════════════════════════

def load_existing_devpost() -> list[dict]:
    """Load existing Devpost data and normalize columns."""
    csv_path = os.path.join(DATA_DIR, "devpost_all_hackathons.csv")
    if not os.path.exists(csv_path):
        safe_print("  WARNING: No existing Devpost data found")
        return []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        records = list(reader)
    
    safe_print(f"  Loaded {len(records)} existing Devpost records")
    
    # Normalize Devpost columns to match our schema
    normalized = []
    for r in records:
        normalized.append({
            "id": r.get("id", ""),
            "platform_id": r.get("devpost_id", ""),
            "name": r.get("name", ""),
            "url": r.get("url", ""),
            "platform": "devpost",
            "status": r.get("status", ""),
            "status_detail": r.get("status_detail", ""),
            "organizer": r.get("organizer", ""),
            "organizer_type": r.get("organizer_type", "unknown"),
            "location": r.get("location", ""),
            "is_online": str(r.get("is_online", "")).lower() in ("true", "1", "yes"),
            "participant_count": int(float(r.get("participant_count", 0) or 0)),
            "views_count": 0,
            "prize_amount_raw": r.get("prize_amount_raw", ""),
            "prize_amount_numeric": float(r.get("prize_amount_numeric", 0) or 0),
            "prize_currency": r.get("prize_currency", ""),
            "prize_tier": r.get("prize_tier", "no_prize"),
            "prize_count": int(float(r.get("total_prizes_count", 0) or 0)),
            "start_date": r.get("start_date", ""),
            "end_date": r.get("end_date", ""),
            "registration_start": "",
            "registration_end": "",
            "min_team_size": 1,
            "max_team_size": 5,
            "subtype": "hackathon",
            "is_paid": False,
            "tags": "",
            "fields": "",
            "themes": r.get("themes", ""),
            "theme_count": int(float(r.get("theme_count", 0) or 0)),
            "has_cash_prize": str(r.get("has_cash_prize", "")).lower() in ("true", "1", "yes"),
            "is_beginner_friendly": str(r.get("is_beginner_friendly", "")).lower() in ("true", "1", "yes"),
            "is_ai_ml": str(r.get("is_ai_ml", "")).lower() in ("true", "1", "yes"),
            "is_social_good": str(r.get("is_social_good", "")).lower() in ("true", "1", "yes"),
            "is_web": str(r.get("is_web", "")).lower() in ("true", "1", "yes"),
            "is_mobile": str(r.get("is_mobile", "")).lower() in ("true", "1", "yes"),
            "is_fintech": str(r.get("is_fintech", "")).lower() in ("true", "1", "yes"),
            "is_blockchain": str(r.get("is_blockchain", "")).lower() in ("true", "1", "yes"),
            "is_cybersecurity": str(r.get("is_cybersecurity", "")).lower() in ("true", "1", "yes"),
            "collected_at": r.get("collected_at", ""),
            "data_source": r.get("data_source", "devpost_api"),
            "is_synthetic": str(r.get("is_synthetic", "")).lower() in ("true", "1", "yes"),
            "winners_announced": str(r.get("winners_announced", "")).lower() in ("true", "1", "yes"),
        })
    
    return normalized


def save_merged_dataset(all_records: list[dict]):
    """Save the merged multi-platform dataset."""
    if not all_records:
        safe_print("  No records to save!")
        return
    
    # Determine all column names (union of all records)
    all_keys = set()
    for r in all_records:
        all_keys.update(r.keys())
    
    # Sort columns logically
    priority_cols = [
        "id", "platform_id", "name", "url", "platform", "status", "status_detail",
        "organizer", "organizer_type", "location", "is_online",
        "participant_count", "views_count",
        "prize_amount_raw", "prize_amount_numeric", "prize_currency", "prize_tier", "prize_count",
        "start_date", "end_date", "registration_start", "registration_end",
        "min_team_size", "max_team_size", "subtype", "is_paid",
        "tags", "fields", "themes", "theme_count",
        "has_cash_prize", "is_beginner_friendly",
        "is_ai_ml", "is_social_good", "is_web", "is_mobile",
        "is_fintech", "is_blockchain", "is_cybersecurity",
        "collected_at", "data_source", "is_synthetic",
    ]
    remaining = sorted(all_keys - set(priority_cols))
    fieldnames = [c for c in priority_cols if c in all_keys] + remaining
    
    # Save CSV
    csv_path = os.path.join(DATA_DIR, "hackathon_multi_platform_dataset_v2.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_records)
    
    # Save JSON
    json_path = os.path.join(DATA_DIR, "hackathon_multi_platform_dataset_v2.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, default=str, ensure_ascii=False)
    
    # Save manifest
    platform_counts = Counter(r["platform"] for r in all_records)
    status_counts = Counter(r["status"] for r in all_records)
    prize_counts = Counter(r["prize_tier"] for r in all_records)
    org_counts = Counter(r["organizer_type"] for r in all_records)
    
    manifest = {
        "total_records": len(all_records),
        "platforms": dict(platform_counts),
        "statuses": dict(status_counts),
        "prize_tiers": dict(prize_counts),
        "organizer_types": dict(org_counts),
        "columns": len(fieldnames),
        "column_names": fieldnames,
        "files": {
            "csv": csv_path,
            "json": json_path,
        },
        "collected_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    
    manifest_path = os.path.join(DATA_DIR, "hackathon_multi_platform_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    safe_print(f"\n  Saved {len(all_records)} records to:")
    safe_print(f"    CSV:      {csv_path}")
    safe_print(f"    JSON:     {json_path}")
    safe_print(f"    Manifest: {manifest_path}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    safe_print("=" * 70)
    safe_print("  MULTI-PLATFORM HACKATHON DATA COLLECTOR")
    safe_print("  Collecting from: Devpost (existing) + Unstop + HackerEarth + MLH")
    safe_print("=" * 70)
    
    # 1. Load existing Devpost data
    safe_print("\n[1/4] Loading existing Devpost data...")
    devpost_records = load_existing_devpost()
    
    # 2. Collect Unstop
    safe_print("\n[2/4] Collecting Unstop data...")
    unstop_records = collect_unstop()
    
    # 3. Skip HackerEarth as per user's request (devpost and unstop only)
    safe_print("\n[3/4] Skipping HackerEarth data collection...")
    hackerearth_records = []
    
    # 4. Skip MLH as per user's request (devpost and unstop only)
    safe_print("\n[4/4] Skipping MLH data collection...")
    mlh_records = []
    
    # Merge all
    safe_print("\n" + "=" * 70)
    safe_print("  MERGING DEVPOST AND UNSTOP")
    safe_print("=" * 70)
    
    all_records = devpost_records + unstop_records
    
    safe_print(f"  Devpost:     {len(devpost_records):,}")
    safe_print(f"  Unstop:      {len(unstop_records):,}")
    safe_print(f"  {'─' * 30}")
    safe_print(f"  TOTAL:       {len(all_records):,}")
    
    # Save
    save_merged_dataset(all_records)
    
    # Print summary stats
    safe_print("\n" + "=" * 70)
    safe_print("  FINAL DATASET SUMMARY")
    safe_print("=" * 70)
    
    platforms = Counter(r["platform"] for r in all_records)
    for plat, count in platforms.most_common():
        safe_print(f"  {plat:15s}: {count:,} records")
    
    safe_print(f"\n  Prize tiers:")
    for tier, count in Counter(r["prize_tier"] for r in all_records).most_common():
        safe_print(f"    {tier:12s}: {count:,}")
    
    online_count = sum(1 for r in all_records if r.get("is_online"))
    safe_print(f"\n  Online: {online_count:,} | In-Person: {len(all_records) - online_count:,}")
    
    participant_counts = [r["participant_count"] for r in all_records if isinstance(r.get("participant_count"), (int, float)) and r["participant_count"] > 0]
    if participant_counts:
        safe_print(f"  Participants: min={min(participant_counts)}, max={max(participant_counts):,}, median={sorted(participant_counts)[len(participant_counts)//2]:,}")
    
    safe_print("\n  DONE!")


if __name__ == "__main__":
    main()
