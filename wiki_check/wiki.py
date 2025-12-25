import os
import sys
import re
import csv
import time
from typing import Optional, Dict, List
from googleapiclient.discovery import build
from dotenv import load_dotenv
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # optional; we'll guard at runtime
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

# Import email scraper
sys.path.append(os.path.join(os.path.dirname(__file__), 'Email Scrapper'))
from email_scraper_final import EmailScraper

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") 
SCHOLAR_CSE_ID = os.getenv("GOOGLE_SCHOLAR_CSE_ID")  
GENERAL_CSE_ID = os.getenv("GOOGLE_GENERAL_CSE_ID")

# MediaWiki (Wikipedia) API config
WIKI_MAILTO = os.getenv("WIKI_MAILTO", "cryp219@gmail.com")
WIKI_DELAY_MS = int(os.getenv("WIKI_DELAY_MS", "120"))

# Pagination configuration from .env
# Note: Google CSE allows num up to 10 per request
CSE_NUM_PER_PAGE = int(os.getenv("CSE_NUM_PER_PAGE", "10"))
CSE_MAX_PAGES = int(os.getenv("CSE_MAX_PAGES", "3"))

WIKI_CACHE: Dict[str, str] = {}

# Profile fetching strategy
# PROFILE_FETCH_MODE: "auto" (try normal, then r.jina.ai), "html" (normal only), "jina" (jina only), "none" (disable)
PROFILE_FETCH_MODE = os.getenv("PROFILE_FETCH_MODE", "auto").lower()
DEBUG_FETCH = os.getenv("DEBUG_FETCH", "false").lower() == "true"

# Optional affiliation/domain filter. Comma-separated list, e.g., "stanford,stanford.edu"
AFFILIATION_FILTER = [t.strip().lower() for t in os.getenv("AFFILIATION_FILTER", "").split(",") if t.strip()]

# Optional rotating query list file. Each line format:
# search term || aff1,aff2,aff3
QUERY_LIST_PATH = os.getenv("QUERY_LIST_PATH", os.path.join(os.path.dirname(__file__), "queries.txt"))

def _load_next_query_from_file(path: str):
    try:
        if not os.path.exists(path) or os.stat(path).st_size == 0:
            return None
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n") for ln in f.readlines()]
        # Skip empty/comment lines
        while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
            lines.pop(0)
        if not lines:
            return None
        first = lines[0]
        rest = lines[1:]
        if "||" in first:
            term_part, aff_part = first.split("||", 1)
            term = term_part.strip()
            aff_tokens = [t.strip().lower() for t in aff_part.split(",") if t.strip()]
        else:
            term = first.strip()
            aff_tokens = []
        return {"term": term, "aff": aff_tokens, "rest": rest}
    except Exception:
        return None

def _consume_query_file(path: str, remaining_lines: list) -> None:
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            for ln in remaining_lines:
                f.write(ln + "\n")
    except Exception:
        pass

# Global counter for Google CSE API calls
CSE_CALL_COUNT = 0

# Strict email validator
EMAIL_REGEX = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

def is_valid_email(candidate: str) -> bool:
    if not isinstance(candidate, str):
        return False
    s = candidate.strip()
    if not EMAIL_REGEX.match(s):
        return False
    try:
        local, domain = s.split('@', 1)
    except ValueError:
        return False
    # Disallow path-like or asset-like strings
    if '/' in local or '/' in domain:
        return False
    # Disallow common file-extension TLDs
    bad_tlds = {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "tiff", "ico", "css", "js", "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"}
    tld = domain.rsplit('.', 1)[-1].lower() if '.' in domain else ''
    if tld in bad_tlds:
        return False
    # Require at least one alphabetic in the second-level domain
    second_level = domain.rsplit('.', 1)[0] if '.' in domain else domain
    if not re.search(r'[A-Za-z]', second_level):
        return False
    return True

def _count_cse_call(label: str) -> None:
    """Increment and print the Google CSE call counter."""
    global CSE_CALL_COUNT
    CSE_CALL_COUNT += 1
    try:
        print(f"CSE call [{CSE_CALL_COUNT}]: {label}")
    except Exception:
        # Avoid failing due to non-ASCII/long labels
        print(f"CSE call [{CSE_CALL_COUNT}]")

def _should_use_html_fetch() -> bool:
    return PROFILE_FETCH_MODE in ("auto", "html")

def _should_use_jina_reader() -> bool:
    return PROFILE_FETCH_MODE in ("auto", "jina")

def _is_scholar_profile_html(html: str) -> bool:
    if not html:
        return False
    return re.search(r'id="gsc_prf_in"', html) is not None

def _looks_like_google_signin(html: str) -> bool:
    if not html:
        return False
    l = html.lower()
    # Be strict: avoid false positives on normal Scholar pages that contain a top-right "Sign in" link
    return ("accounts.google.com" in l) or ("to continue, sign in" in l)

# ---------------- OpenAlex fallback (free) ----------------

def fetch_metrics_from_openalex(person_name: str, institution_hint: str = "harvard") -> Dict[str, Optional[int]]:
    """Fetch citations and h_index for an author via OpenAlex by name search.
    Returns {"citations": int|None, "h_index": int|None}.
    """
    result: Dict[str, Optional[int]] = {"citations": None, "h_index": None}
    if not person_name or person_name == "Unknown":
        return result
    try:
        import requests
        params = {
            "search": person_name,
            "per_page": 5,
            "mailto": WIKI_MAILTO,
        }
        headers = {
            "User-Agent": f"SocialSphere/1.0 (mailto:{WIKI_MAILTO})",
            "Accept": "application/json",
        }
        r = requests.get("https://api.openalex.org/authors", params=params, headers=headers, timeout=20)
        if r.status_code != 200:
            return result
        data = r.json() or {}
        candidates = data.get("results") or []
        # scoring: prefer matching name tokens and institution hint, then highest citations
        def score_author(a: Dict) -> int:
            score = 0
            name = (a.get("display_name") or "").lower()
            pn = clean_name_for_matching(person_name)
            # token overlap
            tokens = [t for t in pn.split() if len(t) > 1]
            score += sum(1 for t in tokens if t in name)
            # institution hint
            insts = a.get("last_known_institutions") or []
            if any(institution_hint.lower() in (inst.get("display_name") or "").lower() for inst in insts):
                score += 3
            # citations weight
            score += int((a.get("cited_by_count") or 0) / 10000)
            return score
        if candidates:
            best = max(candidates, key=score_author)
            result["citations"] = best.get("cited_by_count")
            ss = best.get("summary_stats") or {}
            result["h_index"] = ss.get("h_index")
    except Exception:
        return result
    return result


def search_google_custom_search(query: str, api_key: str, cx_id: str, start_index: int = 1, num: int = CSE_NUM_PER_PAGE) -> Optional[Dict]:
    """Performs a Google Custom Search and returns the JSON response."""
    if not api_key or not cx_id:
        print("Error: API key or CSE ID not provided.")
        return None

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        _count_cse_call(f"q={query} start={start_index} num={min(num,10)} cx={cx_id}")
        res = service.cse().list(
            q=query,
            cx=cx_id,
            num=min(num, 10),
            start=start_index
        ).execute()
        return res
    except Exception as e:
        print(f"An error occurred during custom search: {e}")
        return None

def extract_metrics_from_text(text: str) -> Dict[str, Optional[int]]:
    """Extract citations and h-index from arbitrary text (snippet or HTML snippet).
    Handles common Scholar formats, extra commas, and surrounding punctuation."""
    metrics = {"citations": None, "h_index": None}
    if not text:
        return metrics

    # Normalize ellipses and commas
    t = text.replace("\u2026", "...")

    # Citations patterns
    citation_patterns = [
        r"(?:Cited by|Citations?)\s*(?:[,:\-]?\s*)?([0-9][0-9,\.]*)",
        r"([0-9][0-9,\.]*)\s*citations?",
        r"Citations\s*,\s*([0-9][0-9,\.]*)",  # Citations, 617,208
    ]
    for pat in citation_patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            try:
                metrics["citations"] = int(m.group(1).replace(",", "").replace(".", ""))
                break
            except ValueError:
                pass
    
    # h-index patterns
    hindex_patterns = [
        r"h[\s\-–—]?index\s*(?:[,:\-]?\s*)?([0-9]{1,4})",
        r"([0-9]{1,4})\s*h[\s\-–—]?index",
        r"h[\s\-–—]?index\s*,\s*([0-9]{1,4})",
    ]
    for pat in hindex_patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            try:
                metrics["h_index"] = int(m.group(1))
                break
            except ValueError:
                pass
    return metrics

def extract_metrics_from_item(item: Dict[str, str]) -> Dict[str, Optional[int]]:
    """Extract metrics by combining snippet fields from a CSE item."""
    combined = " ".join(filter(None, [
        item.get("snippet", ""),
        item.get("htmlSnippet", ""),
        item.get("title", ""),
    ]))
    return extract_metrics_from_text(combined)

def try_cse_refetch_metrics_via_profile_id(api_key: str, cx_id: str, profile_url: str) -> Dict[str, Optional[int]]:
    """Make 1-2 targeted CSE queries restricted to the author id to get a richer snippet."""
    metrics = {"citations": None, "h_index": None}
    m = re.search(r"user=([A-Za-z0-9_\-]{6,})", profile_url or "")
    if not m:
        return metrics
    user_id = m.group(1)
    queries = [
        f'"Cited by" "h-index" site:scholar.google.com "user={user_id}"',
        f'"Cited by" site:scholar.google.com "user={user_id}"',
        f'"h-index" site:scholar.google.com "user={user_id}"',
    ]
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        for q in queries:
            if DEBUG_FETCH:
                print(f"  [debug] targeted CSE for metrics: {q}")
            _count_cse_call(f"targeted metrics q={q} cx={cx_id}")
            res = service.cse().list(q=q, cx=cx_id, num=3).execute()
            for item in (res.get("items") or []):
                m2 = extract_metrics_from_item(item)
                if metrics["citations"] is None and m2["citations"] is not None:
                    metrics["citations"] = m2["citations"]
                if metrics["h_index"] is None and m2["h_index"] is not None:
                    metrics["h_index"] = m2["h_index"]
                if metrics["citations"] is not None and metrics["h_index"] is not None:
                    return metrics
    except Exception:
        return metrics
    return metrics


def fetch_h_index_from_profile(profile_url: str) -> Optional[int]:
    """Deprecated in favor of fetch_profile_metrics. Kept for compatibility."""
    result = fetch_profile_metrics(profile_url)
    return result.get("h_index")

def fetch_profile_metrics(profile_url: str) -> Dict[str, Optional[int]]:
    """Fetch both total citations and h-index from a Google Scholar profile page.
    Returns a dict {"citations": int|None, "h_index": int|None}."""
    result: Dict[str, Optional[int]] = {"citations": None, "h_index": None, "affiliation_text": None}
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        html = ""
        if _should_use_html_fetch():
            if DEBUG_FETCH:
                print(f"  [debug] profile fetch(html) → {profile_url}")
            r1 = requests.get(profile_url, headers=headers, timeout=15)
            if DEBUG_FETCH:
                print(f"  [debug] html status={r1.status_code}, bytes={len(r1.text or '')}")
            if r1.status_code == 200 and r1.text:
                html = r1.text
                if DEBUG_FETCH and _looks_like_google_signin(r1.text):
                    print("  [debug] warning: html contains sign-in cues, but parsing anyway")
            elif DEBUG_FETCH:
                print("  [debug] html fetch empty or non-200; will try fallback if enabled")
        # If blocked or unexpected content, try a plain-text mirror fetch via r.jina.ai
        if (not _is_scholar_profile_html(html)) and _should_use_jina_reader():
            try:
                scheme_stripped = re.sub(r"^https?://", "", profile_url)
                jina_url = f"https://r.jina.ai/http://{scheme_stripped}"
                if DEBUG_FETCH:
                    print(f"  [debug] profile fetch(jina) → {jina_url}")
                r2 = requests.get(jina_url, headers=headers, timeout=20)
                if DEBUG_FETCH:
                    print(f"  [debug] jina status={r2.status_code}, bytes={len(r2.text or '')}")
                if r2.status_code == 200 and r2.text and not _looks_like_google_signin(r2.text):
                    html = r2.text
            except Exception:
                pass
        # Parse stats table if real Scholar HTML detected
        if _is_scholar_profile_html(html):
            if DEBUG_FETCH:
                print("  [debug] scholar profile marker found; parsing table")
            m_cit = re.search(
                r"<td[^>]*class=\"gsc_rsb_st\"[^>]*>\s*Citations\s*</td>\s*"
                r"<td[^>]*class=\"gsc_rsb_std\"[^>]*>\s*([0-9,]{1,9})\s*</td>",
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m_cit:
                try:
                    result["citations"] = int(m_cit.group(1).replace(",", ""))
                except Exception:
                    pass
            m_h = re.search(
                r"<td[^>]*class=\"gsc_rsb_st\"[^>]*>\s*h[\s\-–—]?index\s*</td>\s*"
                r"<td[^>]*class=\"gsc_rsb_std\"[^>]*>\s*([0-9]{1,4})\s*</td>",
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if m_h:
                try:
                    result["h_index"] = int(m_h.group(1))
                except Exception:
                    pass
            # Affiliation (profile subtitle area)
            try:
                m_aff = re.search(r'<div[^>]*class="gsc_prf_il"[^>]*>([\s\S]*?)</div>', html, flags=re.IGNORECASE)
                if m_aff:
                    aff_txt = re.sub(r'<[^>]+>', ' ', m_aff.group(1))
                    aff_txt = re.sub(r'\s+', ' ', aff_txt).strip()
                    result["affiliation_text"] = aff_txt
            except Exception:
                pass
        elif DEBUG_FETCH:
            print("  [debug] scholar profile marker NOT found; will try text-mode parsing")
        # Text-mode fallback parsing (works with r.jina.ai output). Be conservative.
        if result["citations"] is None and html:
            m_cit2 = re.search(r"Citations[^0-9]{0,20}([0-9,]{1,9})", html, flags=re.IGNORECASE)
            if m_cit2:
                try:
                    cand = int(m_cit2.group(1).replace(",", ""))
                    if cand >= 50:
                        result["citations"] = cand
                except Exception:
                    pass
        if result["h_index"] is None and html:
            m_h2 = re.search(r"h[\s\-–—]?index[^0-9]{0,10}([0-9]{1,4})", html, flags=re.IGNORECASE)
            if m_h2:
                try:
                    result["h_index"] = int(m_h2.group(1))
                except Exception:
                    pass
        # Affiliation from text-mode if not captured
        if result.get("affiliation_text") is None and html:
            try:
                m_aff2 = re.search(r'Affiliation[^\n<]*[:\-]?\s*([^\n<]{3,120})', html, flags=re.IGNORECASE)
                if m_aff2:
                    t = m_aff2.group(1)
                    t = re.sub(r'<[^>]+>', ' ', t)
                    t = re.sub(r'\s+', ' ', t).strip()
                    if t:
                        result["affiliation_text"] = t
            except Exception:
                pass
        if DEBUG_FETCH:
            print(f"  [debug] parsed metrics → citations={result['citations']}, h_index={result['h_index']}")
        return result
    except Exception as e:
        if DEBUG_FETCH:
            print(f"  [debug] profile fetch error: {e}")
        return result

def clean_unicode_text(text: str) -> str:
    """Clean Unicode characters from text."""
    if not text:
        return text
    
    # Debug: Show what Unicode characters are found
    unicode_chars = re.findall(r'[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\uf8ff\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a]', text)
    if unicode_chars:
        print(f"  🧹 Found Unicode chars: {[f'U+{ord(c):04X}' for c in unicode_chars]}")
    
    # Remove ALL problematic Unicode control characters and markers
    # Including: Left-to-Right Mark, Embedding, Override, etc.
    cleaned = re.sub(r'[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\uf8ff]', '', text)
    
    # Also remove other common problematic characters
    cleaned = re.sub(r'[\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a]', ' ', cleaned)
    
    # Clean up extra spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

def extract_name_from_title(title: str) -> str:
    """Extract person\"s name from title."""
    if not title:
        return "Unknown"
    
    # First clean Unicode characters
    title = clean_unicode_text(title)
    
    # Remove "Google Scholar" suffix (with or without dash)
    name = re.sub(r'\s*-\s*Google Scholar.*$', '', title, flags=re.IGNORECASE)
    name = re.sub(r'\s*Google Scholar.*$', '', name, flags=re.IGNORECASE)
    
    # Clean up extra spaces and dashes
    name = name.strip()
    name = re.sub(r'\s*-\s*$', '', name)  # Remove trailing dash
    name = re.sub(r'\s+', ' ', name)  # Normalize spaces
    
    return name if name else "Unknown"

# def search_for_email(person_name: str, api_key: str, general_cx_id: str) -> str:
def search_for_email(person_name: str, api_key: str, general_cx_id: str) -> str:
    """Search for person's email using their name + "email" on general Google search."""
    if not person_name or person_name == "Unknown":
        return "Not found"
    
    if not general_cx_id:
        print("  ⚠️ General CSE ID not configured for email search.")
        return "CSE not configured"
    
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        
        # Expanded search queries for better email discovery
        search_queries = [
            # University-specific searches
            f'"{person_name}" email site:.edu',  # US universities
            f'"{person_name}" email site:.ac.uk',  # UK universities
            f'"{person_name}" email site:.de',     # German universities
            f'"{person_name}" email site:.fr',     # French universities
            f'"{person_name}" email site:.ca',     # Canadian universities
            f'"{person_name}" email site:.au',     # Australian universities
            f'"{person_name}" email site:.nl',     # Dutch universities
            f'"{person_name}" email site:.se',     # Swedish universities
            
            # Harvard-specific searches (since your search is Harvard-focused)
            f'"{person_name}" email site:harvard.edu',
            f'"{person_name}" email site:hms.harvard.edu',
            f'"{person_name}" email site:fas.harvard.edu',
            f'"{person_name}" email site:seas.harvard.edu',
            f'"{person_name}" email site:gsas.harvard.edu',
            f'"{person_name}" email site:law.harvard.edu',
            f'"{person_name}" email site:med.harvard.edu',
            
            # General academic searches
            f'"{person_name}" email faculty profile',
            f'"{person_name}" email contact information',
            f'"{person_name}" email department contact',
            f'"{person_name}" email university directory',
            f'"{person_name}" email academic profile',
            f'"{person_name}" email research profile',
            
            # Alternative search strategies
            f'"{person_name}" contact email',
            f'"{person_name}" email address',
            f'"{person_name}" faculty email',
            f'"{person_name}" professor email',
            f'"{person_name}" researcher email',
            
            # Research platform searches
            f'"{person_name}" email site:researchgate.net',
            f'"{person_name}" email site:academia.edu',
            f'"{person_name}" email site:orcid.org',
            f'"{person_name}" email site:scholar.google.com'
        ]
        
        for i, query in enumerate(search_queries, 1):
            print(f"  🔍 Email search {i}/{len(search_queries)}: {query}")
            try:
                res = service.cse().list(q=query, cx=general_cx_id, num=5).execute()
                
                if "items" in res:
                    for item in res["items"]:
                        snippet = item.get("snippet", "")
                        title = item.get("title", "")
                        link = item.get("link", "")
                        
                        # Look for email pattern in snippet, title, and link
                        combined_text = snippet + " " + title + " " + link
                        email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', combined_text)
                        
                        if email_matches:
                            # Prefer .edu emails or emails that might contain the person's name
                            for email in email_matches:
                                if ".edu" in email.lower() or any(part.lower() in email.lower() for part in person_name.lower().split()):
                                    print(f"  ✅ Found email: {email}")
                                    return email
                            
                            # If no preferred email found, return the first one
                            found_email = email_matches[0]
                            print(f"  ✅ Found email: {found_email}")
                            return found_email
                            
                            # Add small delay between searches to avoid rate limiting
                            import time
                            time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️ Query {i} failed: {e}")
                continue
        
        print(f"  ❌ No email found after trying {len(search_queries)} search strategies")
        return "Not found"
        
    except Exception as e:
        print(f"  ❌ Email search error for {person_name}: {e}")
        return "Error"

def search_for_wikipedia_page(person_name: str, api_key: str, general_cx_id: str) -> Optional[str]:
    """DISABLED: We now use MediaWiki API instead of Google CSE for Wikipedia lookup.
    Keeping this stub to avoid accidental use. Always returns None.

    See commented legacy implementation below if you want to switch back.
    """
    if DEBUG_FETCH:
        print("  [debug] search_for_wikipedia_page is disabled (using MediaWiki API)")
        return None

# ---------------- Legacy (commented) CSE-based Wikipedia search ----------------
# def search_for_wikipedia_page(person_name: str, api_key: str, general_cx_id: str) -> Optional[str]:
#     """Search general Google CSE for a person's Wikipedia page and return the URL if found."""
#     if not person_name or person_name == "Unknown":
#         return None
#     if not general_cx_id:
#         print("  ⚠️ General CSE ID not configured for Wikipedia search.")
#         return None
#     try:
#         service = build("customsearch", "v1", developerKey=api_key)
#         search_queries = [
#             f'"{person_name}" wikipedia',
#             f'"{person_name}" site:wikipedia.org',
#             f'"{person_name}" "wikipedia" "professor"',
#             f'"{person_name}" "wikipedia" "harvard"',
#             f'"{person_name}" "wikipedia" "academic"',
#             f'"{person_name}" "wikipedia" "researcher"',
#         ]
#         for query in search_queries:
#             print(f"  🔍 Wikipedia CSE search: {query}")
#             _count_cse_call(f"wiki q={query} cx={general_cx_id}")
#             res = service.cse().list(q=query, cx=general_cx_id, num=5).execute()
#             if "items" in res:
#                 for item in res["items"]:
#                     link = item.get("link", "")
#                     title = item.get("title", "")
#                     snippet = item.get("snippet", "")
#                     if "wikipedia.org" in link.lower() and is_likely_match(person_name, title, snippet, link):
#                         return link
#         return None
#     except Exception as e:
#         print(f"  ❌ Wikipedia search error for {person_name}: {e}")
#         return None

def is_likely_match(person_name: str, title: str, snippet: str, link: str) -> bool:
    """
    Intelligent name matching that handles variations and partial matches.
    Returns True if the Wikipedia page likely matches the person.
    """
    if not person_name or not title:
        return False
    
    # Clean and normalize names
    person_clean = clean_name_for_matching(person_name)
    title_clean = clean_name_for_matching(title)
    
    # Generate alias variants for robust matching (e.g., Abraham ↔ Avi)
    def generate_name_variants(clean_name: str) -> List[str]:
        aliases = {
            # Common nicknames already handled elsewhere; include key academic ones
            "abraham": ["avi", "avraham"],
            "avraham": ["avi", "abraham"],
            "avi": ["abraham", "avraham"],
        }
        parts = clean_name.split()
        if not parts:
            return [clean_name]
        first = parts[0]
        variants = {clean_name}
        if first in aliases:
            for alt in aliases[first]:
                v = " ".join([alt] + parts[1:])
                variants.add(v)
        return list(variants)

    person_variants = generate_name_variants(person_clean)

    # Strategy 1: Exact or contained match across variants (after cleaning)
    for variant in person_variants:
        if variant == title_clean:
            print(f"     🎯 Exact name match: '{variant}' == '{title_clean}'")
            return True
        if variant in title_clean:
            print(f"     🎯 Person name contained in title: '{variant}' in '{title_clean}'")
            return True
    
    # Strategy 2.5: Handle Wikipedia titles with descriptive text in parentheses
    # e.g., "Gary King (political scientist)" should match "Gary King"
    title_without_parens = re.sub(r'\s*\([^)]*\)\s*$', '', title_clean).strip()
    for variant in person_variants:
        if variant == title_without_parens:
            print(f"     🎯 Name match after removing parentheses: '{variant}' == '{title_without_parens}'")
            return True
        if variant in title_without_parens:
            print(f"     🎯 Person name contained in title (no parens): '{variant}' in '{title_without_parens}'")
            return True
    
    # Strategy 3: Title is contained in person name (for cases like "Jeff W. Litchman" vs "Jeff Litchman")
    if title_clean in person_clean:
        print(f"     🎯 Title contained in person name: '{title_clean}' in '{person_clean}'")
        return True
    
    # Strategy 4: Check if at least 2 significant name parts match
    # Recompute parts using primary variant
    primary_variant = person_variants[0] if person_variants else person_clean
    person_parts = [part for part in primary_variant.split() if len(part) > 2]  # Ignore initials
    title_parts = [part for part in title_clean.split() if len(part) > 2]
    
    if len(person_parts) >= 2 and len(title_parts) >= 2:
        matches = sum(1 for part in person_parts if part in title_parts)
        if matches >= 2:
            print(f"     🎯 Multiple name parts match: {matches} out of {len(person_parts)} parts")
            return True
    
    # Strategy 5: Check for common name variations
    if has_common_variations(person_clean, title_clean):
        print(f"     🎯 Common name variation detected")
        return True
    
    # Strategy 5.5: Handle middle initials and name variations
    # e.g., "Donald Ingber" should match "Donald E. Ingber"
    person_parts = primary_variant.split()
    title_parts = title_clean.split()
    
    if len(person_parts) >= 2 and len(title_parts) >= 2:
        # Check if first and last names match, ignoring middle names/initials
        if (person_parts[0] == title_parts[0] and 
            person_parts[-1] == title_parts[-1]):
            print(f"     🎯 First and last name match (ignoring middle): '{person_parts[0]} {person_parts[-1]}'")
            return True
        
        # Check if person name parts are contained in title (ignoring middle initials)
        person_first_last = f"{person_parts[0]} {person_parts[-1]}"
        title_first_last = f"{title_parts[0]} {title_parts[-1]}"
        if person_first_last in title_first_last or title_first_last in person_first_last:
            print(f"     🎯 First and last name contained: '{person_first_last}' in '{title_first_last}'")
            return True
    
    # Strategy 6: Check if it's clearly about the same person (academic context)
    if is_academic_context_match(person_name, title, snippet):
        print(f"     🎯 Academic context match")
        return True
    
    return False

def clean_name_for_matching(name: str) -> str:
    """Clean name for better matching by removing common prefixes, suffixes, and normalizing."""
    if not name:
        return ""
    
    # Remove common academic titles and prefixes
    prefixes_to_remove = [
        "professor", "prof", "dr", "doctor", "phd", "ph.d", "md", "m.d",
        "associate", "assistant", "emeritus", "distinguished", "senior"
    ]
    
    # Remove common suffixes
    suffixes_to_remove = [
        "jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "phd", "ph.d", "md", "m.d"
    ]
    
    name_lower = name.lower().strip()
    
    # Remove prefixes
    for prefix in prefixes_to_remove:
        if name_lower.startswith(prefix + " "):
            name_lower = name_lower[len(prefix + " "):]
    
    # Remove suffixes
    for suffix in suffixes_to_remove:
        if name_lower.endswith(" " + suffix):
            name_lower = name_lower[:-len(" " + suffix)]
    
    # Normalize whitespace and remove extra spaces
    name_clean = " ".join(name_lower.split())
    
    return name_clean

def has_common_variations(name1: str, name2: str) -> bool:
    """Check for common name variations like Jeff/Jeffrey, Mike/Michael, etc."""
    common_variations = {
        "jeff": "jeffrey",
        "jeffrey": "jeff",
        "mike": "michael", 
        "michael": "mike",
        "bob": "robert",
        "robert": "bob",
        "jim": "james",
        "james": "jim",
        "joe": "joseph",
        "joseph": "joe",
        "nick": "nicholas",
        "nicholas": "nick",
        "chris": "christopher",
        "christopher": "chris",
        "dave": "david",
        "david": "dave",
        "steve": "steven",
        "steven": "steve",
        "tony": "anthony",
        "anthony": "tony"
    }
    
    name1_lower = name1.lower()
    name2_lower = name2.lower()
    
    # Check if names are common variations of each other
    if name1_lower in common_variations and common_variations[name1_lower] == name2_lower:
        return True
    if name2_lower in common_variations and common_variations[name2_lower] == name1_lower:
        return True
    
    return False

def is_academic_context_match(person_name: str, title: str, snippet: str) -> bool:
    """Check if the context suggests it's about the same academic person."""
    if not person_name or not title or not snippet:
        return False
    
    # Check if title contains academic keywords
    academic_keywords = ["professor", "researcher", "academic", "scholar", "scientist", "faculty"]
    title_lower = title.lower()
    snippet_lower = snippet.lower()
    
    has_academic_context = any(keyword in title_lower or keyword in snippet_lower for keyword in academic_keywords)
    
    if not has_academic_context:
        return False
    
    # Check if at least one significant name part appears in both title and snippet
    name_parts = [part for part in person_name.lower().split() if len(part) > 2]
    
    for part in name_parts:
        if part in title_lower and part in snippet_lower:
            return True
    
    return False

def fetch_homepage_from_profile(profile_url: str) -> str:
    """Attempts to fetch the 'Homepage' URL from a Google Scholar profile page.
    Handles cases where the anchor uses javascript:void(0) with data-href/onclick."""
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        html = ""
        if _should_use_html_fetch():
            if DEBUG_FETCH:
                print(f"  [debug] homepage fetch(html) → {profile_url}")
            r1 = requests.get(profile_url, headers=headers, timeout=15)
            if DEBUG_FETCH:
                print(f"  [debug] homepage html status={r1.status_code}, bytes={len(r1.text or '')}")
            if r1.status_code == 200 and r1.text:
                html = r1.text
                if DEBUG_FETCH and _looks_like_google_signin(r1.text):
                    print("  [debug] warning: homepage html contains sign-in cues, but parsing anyway")
        if not _is_scholar_profile_html(html) and _should_use_jina_reader():
            try:
                scheme_stripped = re.sub(r"^https?://", "", profile_url)
                jina_url = f"https://r.jina.ai/http://{scheme_stripped}"
                if DEBUG_FETCH:
                    print(f"  [debug] homepage fetch(jina) → {jina_url}")
                r2 = requests.get(jina_url, headers=headers, timeout=20)
                if DEBUG_FETCH:
                    print(f"  [debug] homepage jina status={r2.status_code}, bytes={len(r2.text or '')}")
                if r2.status_code == 200 and r2.text and not _looks_like_google_signin(r2.text):
                    html = r2.text
            except Exception:
                pass
        if not html:
            return "N/A"

        # Find the specific 'Homepage' anchor near the profile header
        # Example: <a class="gsc_prf_ila" href="https://...">Homepage</a>
        m = re.search(
            r"<a[^>]*class=\"gsc_prf_ila\"[^>]*?(?:aria-label=\"Homepage\"[^>]*?)?href=\"([^\"]+)\"[^>]*>\s*Homepage\s*</a>",
            html,
            flags=re.IGNORECASE,
        )
        href = None
        if m:
            href = m.group(1)
        else:
            # Some profiles render the link with javascript:void(0) and the real URL in data-href or in onclick
            container = re.search(r"<a[^>]*class=\"gsc_prf_ila\"[^>]*>\s*Homepage\s*</a>", html, flags=re.IGNORECASE)
            if container:
                tag = container.group(0)
                m_data = re.search(r"data-href=\"([^\"]+)\"", tag, flags=re.IGNORECASE)
                if m_data:
                    href = m_data.group(1)
                else:
                    m_onclick = re.search(r"onclick=\"[^\"]*window\.open\(['\"]([^'\"]+)['\"]\)", tag, flags=re.IGNORECASE)
                    if m_onclick:
                        href = m_onclick.group(1)
                if not href:
                    m_href = re.search(r"href=\"([^\"]+)\"", tag, flags=re.IGNORECASE)
                    if m_href:
                        href = m_href.group(1)

        if not href:
            # Text-mode fallback: extract a plausible external URL near 'Homepage' or any non-Scholar external URL
            # Look for explicit "Homepage" label with a URL
            m_txt = re.search(r"(?:Homepage|Home page|Website)\s*[:\-]?\s*(https?://\S+)", html, flags=re.IGNORECASE)
            candidate = None
            if m_txt:
                candidate = m_txt.group(1)
            else:
                # Fallback: grab first plausible external http(s) URL that is not a static/asset/google link
                urls = re.findall(r"https?://[^\s'\"<>]+", html)
                def _is_plausible(u: str) -> bool:
                    lu = u.lower()
                    # Filter out Google/Scholar/static asset URLs
                    if any(bad in lu for bad in [
                        "scholar.google.", "googleusercontent.com", "gstatic.com",
                        "accounts.google.", "/citations?", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif",
                    ]):
                        return False
                    # Filter out PDFs and documents
                    if any(ext in lu for ext in [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]):
                        return False
                    # Filter out news articles, press releases, and non-personal pages
                    if any(bad in lu for bad in [
                        "/news/", "/press/", "/media/", "/article", "/story", "/announcement",
                        "newsroom", "press-release", "mit-news", "harvard-news", "stanford-news",
                        "/honor", "/award", "/recognition", "/tribute", "/memorial"
                    ]):
                        return False
                    # STRICT: Only accept URLs that look like personal/academic pages
                    if any(good in lu for good in [
                        "/faculty/", "/people/", "/professor", "/prof.", "/~", "/user/",
                        "homepage", "personal", "lab", "research", "group", "team",
                        ".edu/~", ".edu/people/", ".edu/faculty/"
                    ]):
                        return True
                    # Reject everything else to avoid random pages
                    return False
                for u in urls:
                    if _is_plausible(u):
                        candidate = u
                        break
            if candidate:
                href = candidate
            else:
                return "N/A"
        href = href.strip()
        if href.lower().startswith("javascript:"):
            return "N/A"
        if href.startswith("/"):
            href = "https://scholar.google.com" + href
        
        # Filter out PDFs and documents
        if any(ext in href.lower() for ext in [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]):
            if DEBUG_FETCH:
                print(f"  [debug] rejected PDF/document URL: {href}")
            return "N/A"
        
        # Filter out news articles, press releases, and non-personal pages
        if any(bad in href.lower() for bad in [
            "/news/", "/press/", "/media/", "/article", "/story", "/announcement",
            "newsroom", "press-release", "mit-news", "harvard-news", "stanford-news",
            "/honor", "/award", "/recognition", "/tribute", "/memorial"
        ]):
            if DEBUG_FETCH:
                print(f"  [debug] rejected news/article URL: {href}")
            return "N/A"
        
        # Only accept URLs that look like personal/academic pages
        if not any(good in href.lower() for good in [
            "/faculty/", "/people/", "/professor", "/prof.", "/~", "/user/",
            "homepage", "personal", "lab", "research", "group", "team",
            ".edu/~", ".edu/people/", ".edu/faculty/"
        ]):
            if DEBUG_FETCH:
                print(f"  [debug] rejected non-academic URL: {href}")
            return "N/A"
        
        if DEBUG_FETCH:
            print(f"  [debug] parsed homepage → {href}")
        return href
    except Exception:
        return "N/A"

# ---------------- Wikipedia via MediaWiki API ----------------

def _clean_name_basic(name: str) -> str:
    n = name.lower().strip()
    n = re.sub(r"\b(dr|prof|professor)\.?\s+", "", n)
    n = re.sub(r"\s+", " ", n)
    return n


def fetch_wikipedia_via_mediawiki(person_name: str) -> str:
    """Use MediaWiki API (free) to find a likely Wikipedia page for the person."""
    try:
        # Use cleaned first+last as cache/search key
        person_clean_all = clean_name_for_matching(person_name)
        parts_fl = person_clean_all.split()
        key = (f"{parts_fl[0]} {parts_fl[-1]}" if len(parts_fl) >= 2 else person_clean_all).strip()
        if key in WIKI_CACHE:
            return WIKI_CACHE[key]

        import requests
        # Unquoted first pass with first+last
        params = {
            "action": "query",
            "list": "search",
            "srsearch": key,
            "srenablerewrites": 1,
            "srlimit": 10,
            "srwhat": "nearmatch",
            "utf8": 1,
            "format": "json",
        }
        headers = {
            "User-Agent": f"WikiCheck/1.0 (mailto:{WIKI_MAILTO})",
            "Accept": "application/json",
        }
        r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=20)
        if r.status_code != 200:
            WIKI_CACHE[key] = "N/A"
            return "N/A"
        data = r.json()
        hits = (data.get("query") or {}).get("search") or []
        
        if not hits:
            # Quoted cleaned retry
            params_q = dict(params)
            params_q["srsearch"] = f'"{key}"'
            r_q = requests.get("https://en.wikipedia.org/w/api.php", params=params_q, headers=headers, timeout=20)
            if r_q.status_code == 200:
                dq = r_q.json() or {}
                hits = (dq.get("query") or {}).get("search") or []

        if not hits:
            # Retry with alias variants (e.g., Abraham -> Avi)
            base_clean = key
            def _gen_aliases(clean_name: str) -> List[str]:
                aliases = {
                    "abraham": ["avi", "avraham"],
                    "avraham": ["avi", "abraham"],
                    "avi": ["abraham", "avraham"],
                }
                parts = clean_name.split()
                if not parts:
                    return []
                first = parts[0]
                out: List[str] = []
                if first in aliases:
                    for alt in aliases[first]:
                        out.append(" ".join([alt] + parts[1:]))
                return out
            alt_names = _gen_aliases(base_clean)
            for alt in alt_names:
                try:
                    alt_params = {
                        "action": "query",
                        "list": "search",
                        "srsearch": f'"{alt}"',
                        "srenablerewrites": 1,
                        "srlimit": 10,
                        "srwhat": "nearmatch",
                        "utf8": 1,
                        "format": "json",
                    }
                    r_alt = requests.get("https://en.wikipedia.org/w/api.php", params=alt_params, headers=headers, timeout=20)
                    if r_alt.status_code != 200:
                        continue
                    data_alt = r_alt.json()
                    hits = (data_alt.get("query") or {}).get("search") or []
                    if hits:
                        break
                except Exception:
                    continue
            if not hits:
                WIKI_CACHE[key] = "N/A"
                return "N/A"
        
        # Check if we found disambiguation pages and try alternative searches
        disambiguation_found = False
        for hit in hits:
            title = hit.get("title", "")
            if title:
                # Check if this is a disambiguation page
                resolve_params = {
                    "action": "query",
                    "prop": "info|pageprops",
                    "titles": title,
                    "redirects": 1,
                    "format": "json",
                    "utf8": 1,
                }
                try:
                    r_resolve = requests.get("https://en.wikipedia.org/w/api.php", params=resolve_params, headers=headers, timeout=15)
                    if r_resolve.status_code == 200:
                        data_resolve = r_resolve.json()
                        pages_resolve = (data_resolve.get("query") or {}).get("pages") or {}
                        for _, pg in pages_resolve.items():
                            pp = pg.get("pageprops") or {}
                            if "disambiguation" in pp:
                                disambiguation_found = True
                                break
                except Exception:
                    continue
            if disambiguation_found:
                break
        
        # If we found disambiguation pages, try alternative searches
        if disambiguation_found:
            # Try name variations first (most likely to work)
            name_parts = key.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = name_parts[-1]
                alternative_searches = [
                    f"{first_name} M {last_name}",
                    f"{first_name} McDonald {last_name}",
                    f"{first_name} {last_name} scientist",
                    f"{first_name} {last_name} professor", 
                    f"{first_name} {last_name} geneticist",
                    f"{first_name} {last_name} physicist",
                    f"{first_name} {last_name} biologist",
                    f"{first_name} {last_name} chemist",
                    f"{first_name} {last_name} engineer",
                    f"{first_name} {last_name} economist",
                    f"{first_name} {last_name} computer scientist",
                    f"{first_name} {last_name} Harvard",
                    f"{first_name} {last_name} MIT",
                    f"{first_name} {last_name} Stanford",
                    f"{first_name} {last_name} university"
                ]
            else:
                alternative_searches = [
                    f"{key} scientist",
                    f"{key} professor", 
                    f"{key} geneticist",
                    f"{key} physicist",
                    f"{key} biologist",
                    f"{key} chemist",
                    f"{key} engineer",
                    f"{key} economist",
                    f"{key} computer scientist",
                    f"{key} Harvard",
                    f"{key} MIT",
                    f"{key} Stanford",
                    f"{key} university"
                ]
            
            for alt_search in alternative_searches:
                try:
                    alt_params = {
                        "action": "query",
                        "list": "search",
                        "srsearch": alt_search,
                        "srenablerewrites": 1,
                        "srlimit": 5,
                        "srwhat": "nearmatch",
                        "utf8": 1,
                        "format": "json",
                    }
                    r_alt = requests.get("https://en.wikipedia.org/w/api.php", params=alt_params, headers=headers, timeout=20)
                    if r_alt.status_code == 200:
                        data_alt = r_alt.json()
                        hits_alt = (data_alt.get("query") or {}).get("search") or []
                        if hits_alt:
                            # Check if any of these are non-disambiguation pages
                            for hit_alt in hits_alt:
                                title_alt = hit_alt.get("title", "")
                                if title_alt:
                                    resolve_params = {
                                        "action": "query",
                                        "prop": "info|pageprops",
                                        "titles": title_alt,
                                        "redirects": 1,
                                        "format": "json",
                                        "utf8": 1,
                                    }
                                    try:
                                        r_resolve_alt = requests.get("https://en.wikipedia.org/w/api.php", params=resolve_params, headers=headers, timeout=15)
                                        if r_resolve_alt.status_code == 200:
                                            data_resolve_alt = r_resolve_alt.json()
                                            pages_resolve_alt = (data_resolve_alt.get("query") or {}).get("pages") or {}
                                            for _, pg in pages_resolve_alt.items():
                                                pp = pg.get("pageprops") or {}
                                                if "disambiguation" not in pp:
                                                    # Found a non-disambiguation page, use these hits instead
                                                    hits = hits_alt
                                                    break
                                    except Exception:
                                        continue
                            if hits != hits_alt:  # We found a non-disambiguation page
                                break
                except Exception:
                    continue
        
        # Helper: resolve redirects and reject disambiguation
        def resolve_canonical(title: str) -> str:
            q_params = {
                "action": "query",
                "prop": "info|pageprops",
                "titles": title,
                "redirects": 1,
                "format": "json",
                "utf8": 1,
            }
            r2 = requests.get("https://en.wikipedia.org/w/api.php", params=q_params, headers=headers, timeout=15)
            if r2.status_code != 200:
                return title
            dj = r2.json() or {}
            pages = (dj.get("query") or {}).get("pages") or {}
            for _, pg in pages.items():
                pp = pg.get("pageprops") or {}
                # If disambiguation, reject by returning empty
                if "disambiguation" in pp:
                    return ""
                return pg.get("title") or title
            return title

        # Score hits: prefer parenthetical academic topics and exact first+last base match
        def score_hit(title: str, snippet: str) -> int:
            s = 0
            t_low = title.lower()
            # Prefer titles with parentheses (often biographies disambiguated by field)
            if "(" in title and ")" in title:
                s += 2
            # Prefer field keywords gleaned from snippet
            kw = ["professor", "geneticist", "physicist", "roboticist", "biologist", "chemist", "economist", "engineer", "computer scientist"]
            s += sum(1 for k in kw if k in snippet.lower())
            # First+last match against base title (strip parens)
            base = re.sub(r"\s*\([^)]*\)\s*$", "", t_low)
            person_base = clean_name_for_matching(person_name)
            # keep only first+last
            pb_parts = person_base.split()
            if len(pb_parts) >= 2:
                pb = f"{pb_parts[0]} {pb_parts[-1]}"
                if pb in base:
                    s += 3
            return s

        # Sort hits by score descending
        hits_sorted = sorted(hits, key=lambda h: score_hit(h.get("title", ""), h.get("snippet", "")), reverse=True)

        # Helper for base equality: compare first+last to title without parens
        def base_name_equal(pname: str, title: str) -> bool:
            t_base = re.sub(r"\s*\([^)]*\)\s*$", "", title.lower()).strip()
            pn = clean_name_for_matching(pname)
            parts = pn.split()
            if len(parts) < 2:
                return False
            fl = f"{parts[0]} {parts[-1]}"
            return fl == t_base or fl in t_base or t_base in fl

        # Check each result using the improved matching logic, with redirect resolution
        for hit in hits_sorted:
            title = hit.get("title", "")
            snippet = hit.get("snippet", "")
            if not title:
                continue
            resolved = resolve_canonical(title)
            if not resolved:
                continue  # disambiguation rejected
            candidate_url = "https://en.wikipedia.org/wiki/" + resolved.replace(" ", "_")
            if is_likely_match(person_name, resolved, snippet, candidate_url) or base_name_equal(person_name, resolved):
                url = candidate_url
                WIKI_CACHE[key] = url
                if WIKI_DELAY_MS:
                    time.sleep(WIKI_DELAY_MS / 1000.0)
                return url

        # Fallback: run an unquoted search with first+last only and retry
        try:
            pn_clean = clean_name_for_matching(person_name)
            pn_parts = pn_clean.split()
            if len(pn_parts) >= 2:
                first_last = f"{pn_parts[0]} {pn_parts[-1]}"
                alt_params2 = {
                    "action": "query",
                    "list": "search",
                    "srsearch": first_last,
                    "srenablerewrites": 1,
                    "srlimit": 10,
                    "srwhat": "nearmatch",
                    "utf8": 1,
                    "format": "json",
                }
                r_alt2 = requests.get("https://en.wikipedia.org/w/api.php", params=alt_params2, headers=headers, timeout=20)
                if r_alt2.status_code == 200:
                    d2 = r_alt2.json() or {}
                    hits2 = (d2.get("query") or {}).get("search") or []
                    for hit in hits2:
                        t2 = hit.get("title", "")
                        s2 = hit.get("snippet", "")
                        if not t2:
                            continue
                        resolved2 = resolve_canonical(t2)
                        if not resolved2:
                            continue
                        cand2 = "https://en.wikipedia.org/wiki/" + resolved2.replace(" ", "_")
                        if is_likely_match(person_name, resolved2, s2, cand2) or base_name_equal(person_name, resolved2):
                            url = cand2
                            WIKI_CACHE[key] = url
                            if WIKI_DELAY_MS:
                                time.sleep(WIKI_DELAY_MS / 1000.0)
                            return url
        except Exception:
            pass
        
        # No good match found
        WIKI_CACHE[key] = "N/A"
        if WIKI_DELAY_MS:
            time.sleep(WIKI_DELAY_MS / 1000.0)
        return "N/A"
    except Exception:
        WIKI_CACHE[person_name] = "N/A"
        return "N/A"

def fetch_official_site_from_wikidata(wikipedia_url: str) -> str:
    """Given a Wikipedia article URL, resolve its Wikidata item and return official website (P856) if present."""
    if not wikipedia_url:
        return "N/A"
    try:
        import requests
        # 1) Resolve title
        m = re.search(r"/wiki/([^?#]+)", wikipedia_url)
        if not m:
            return "N/A"
        title = m.group(1).replace("_", " ")
        # 2) Query Wikipedia API to get Wikidata QID
        params = {
            "action": "query",
            "prop": "pageprops",
            "titles": title,
            "format": "json",
            "utf8": 1,
        }
        headers = {
            "User-Agent": f"WikiCheck/1.0 (mailto:{WIKI_MAILTO})",
            "Accept": "application/json",
        }
        r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return "N/A"
        data = r.json() or {}
        pages = (data.get("query") or {}).get("pages") or {}
        qid = None
        for _, page in pages.items():
            pp = page.get("pageprops") or {}
            qid = pp.get("wikibase_item")
            if qid:
                break
        if not qid:
            return "N/A"
        # 3) Query Wikidata for property P856 (official website)
        wd = requests.get(
            f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
            headers=headers,
            timeout=15,
        )
        if wd.status_code != 200:
            return "N/A"
        wj = wd.json() or {}
        ent = (wj.get("entities") or {}).get(qid) or {}
        claims = ent.get("claims") or {}
        p856 = claims.get("P856") or []
        for claim in p856:
            mainsnak = claim.get("mainsnak") or {}
            datav = (mainsnak.get("datavalue") or {}).get("value")
            if isinstance(datav, str) and datav:
                return datav
        return "N/A"
    except Exception:
        return "N/A"

def _heuristic_summary(person_name: str, affiliation_text: str = "", snippet: str = "") -> str:
    """Construct a very short 1–2 sentence heuristic summary without API calls.
    Uses name + affiliation and any academic keywords from snippet. Deterministic, no CSE.
    """
    name = (person_name or "Unknown").strip()
    aff = (affiliation_text or "").strip()
    sn = (snippet or "").strip()
    parts = []
    if aff:
        parts.append(f"{name} is an academic affiliated with {aff}.")
    else:
        parts.append(f"{name} is an academic researcher.")
    # Pull a coarse field hint from snippet if present
    sn_low = sn.lower()
    field = None
    for kw in [
        "computer science", "economics", "biology", "chemistry", "physics",
        "engineering", "neuroscience", "genetics", "medicine", "statistics",
        "mathematics", "psychology", "sociology", "political science"
    ]:
        if kw in sn_low:
            field = kw
            break
    if field:
        parts.append(f"Their work relates to {field}.")
    return " ".join(parts)

def fetch_website_from_wikipedia_extlinks(wikipedia_url: str) -> str:
    """Fetch candidate website from Wikipedia page external links (prop=extlinks)."""
    try:
        m = re.search(r"/wiki/([^?#]+)", wikipedia_url or "")
        if not m:
            return "N/A"
        title = m.group(1)
        import requests
        params = {
            "action": "query",
            "prop": "extlinks",
            "ellimit": 50,
            "titles": title,
            "format": "json",
            "utf8": 1,
        }
        headers = {
            "User-Agent": f"WikiCheck/1.0 (mailto:{WIKI_MAILTO})",
            "Accept": "application/json",
        }
        r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return "N/A"
        data = r.json() or {}
        pages = (data.get("query") or {}).get("pages") or {}
        links: List[str] = []
        for _, page in pages.items():
            for el in (page.get("extlinks") or []):
                url = el.get("*")
                if isinstance(url, str):
                    links.append(url)
        if not links:
            return "N/A"
        # Heuristics: prefer .edu, .ac.* or personal domains containing name parts
        def score(url: str) -> int:
            s = 0
            u = url.lower()
            if any(tld in u for tld in [".edu", ".ac."]):
                s += 3
            if any(k in u for k in ["harvard", "mit", "stanford", "ox.ac.uk", "cam.ac.uk"]):
                s += 2
            if any(k in u for k in ["lab", "group", "people", "faculty", "profile", "~", "home"]):
                s += 1
            return s
        best = max(links, key=score)
        return best or "N/A"
    except Exception:
        return "N/A"

def first_url_from_general_cse(person_name: str) -> str:
    """Perform one general CSE query with 'name email' and return the first valid result URL."""
    if not person_name or not GENERAL_CSE_ID or not API_KEY:
        return "N/A"
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
        q = f'"{person_name}" email'
        if DEBUG_FETCH:
            print(f"  [debug] general CSE first-url: {q}")
        _count_cse_call(f"general first-url q={q} cx={GENERAL_CSE_ID}")
        res = service.cse().list(q=q, cx=GENERAL_CSE_ID, num=10).execute()
        items = res.get("items") or []
        if items:
            # Check all results and return the first valid one
            for item in items:
                url = item.get("link") or ""
                if url and is_valid_homepage_url(url):
                    return url
            # If no valid URLs found, return the first one anyway
            return items[0].get("link") or "N/A"
        return "N/A"
    except Exception:
        return "N/A"

def is_valid_homepage_url(url: str) -> bool:
    """Check if a homepage URL is valid (not PDF, news article, etc.)."""
    if not url or url == "N/A":
        return False
    
    lu = url.lower()
    
    # Check PDFs and documents
    if any(ext in lu for ext in [".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]):
        return False
    
    # Check news articles, press releases, and non-personal pages
    if any(bad in lu for bad in [
        "/news/", "/press/", "/media/", "/article", "/story", "/announcement",
        "newsroom", "press-release", "mit-news", "harvard-news", "stanford-news",
        "/honor", "/award", "/recognition", "/tribute", "/memorial"
    ]):
        return False
    
    # Only accept URLs that look like personal/academic pages
    return any(good in lu for good in [
        "/faculty/", "/people/", "/professor", "/prof.", "/~", "/user/",
        "homepage", "personal", "lab", "research", "group", "team",
        ".edu/~", ".edu/people/", ".edu/faculty/"
    ])

# ---------------- Summarization helpers (OpenAI GPT-4o-mini) ----------------

def _get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    try:
        client = OpenAI()
        return client
    except Exception:
        return None

def fetch_wikipedia_extract(wikipedia_url: str) -> str:
    try:
        m = re.search(r"/wiki/([^?#]+)", wikipedia_url or "")
        if not m:
            return ""
        title = m.group(1).replace("_", " ")
        import requests
        params = {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exsectionformat": "plain",
            "titles": title,
            "format": "json",
            "utf8": 1,
        }
        headers = {
            "User-Agent": f"WikiCheck/1.0 (mailto:{WIKI_MAILTO})",
            "Accept": "application/json",
        }
        r = requests.get("https://en.wikipedia.org/w/api.php", params=params, headers=headers, timeout=20)
        if r.status_code != 200:
            return ""
        data = r.json() or {}
        pages = (data.get("query") or {}).get("pages") or {}
        for _, pg in pages.items():
            ext = pg.get("extract") or ""
            if isinstance(ext, str):
                return ext.strip()
        return ""
    except Exception:
        return ""

def fetch_homepage_text(url: str) -> str:
    if not url or url == "N/A":
        return ""
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200 or not r.text:
            return ""
        html = r.text
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            # Remove script/style
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = soup.get_text(" ")
        else:
            # Fallback: strip tags
            text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text or "").strip()
        # Limit length to keep token usage low
        return text[:5000]
    except Exception:
        return ""

def summarize_with_gpt(source_text: str, mode: str = "wiki") -> str:
    client = _get_openai_client()
    if client is None or not source_text:
        return "N/A"
    try:
        if mode == "wiki":
            sys_msg = (
                "You are an academic summarizer. Output plain text only. No markup. "
                "Summarize the person's biography focusing on field, notable contributions, key works, awards, and current affiliation."
            )
            user_msg = (
                "Summarize the following Wikipedia extract into a concise academic bio (3-6 sentences). "
                "Plain text only, no brackets, no citations, no list formatting.\n\n" + source_text[:8000]
            )
            max_tokens = 250
        else:
            sys_msg = (
                "You are an academic summarizer. Output plain text only. No markup."
            )
            user_msg = (
                "From the following homepage/about text, write a very short 1-2 sentence summary of the person's main field and contributions. "
                "Plain text only, avoid speculation.\n\n" + source_text[:6000]
            )
            max_tokens = 120
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        content = (resp.choices[0].message.content or '').strip()
        # Normalize whitespace
        content = re.sub(r"\s+", " ", content)
        return content if content else "N/A"
    except Exception:
        return "N/A"

def find_email_for_person(person_name: str, homepage_url: str, profile_url: str = None) -> str:
    """Find email for a person using their homepage URL and name."""
    if not person_name:
        return "N/A"
    
    # If homepage URL is invalid, try to find a better one
    if not is_valid_homepage_url(homepage_url) and profile_url:
        print(f"  🔄 Invalid homepage URL detected: {homepage_url}")
        print(f"  🔍 Attempting to find better homepage for {person_name}...")
        
        # Try to fetch a better homepage from the profile
        new_homepage = fetch_homepage_from_profile(profile_url)
        if is_valid_homepage_url(new_homepage):
            print(f"  ✅ Found better homepage: {new_homepage}")
            homepage_url = new_homepage
        else:
            print(f"  ⚠️ Could not find valid homepage, skipping email search...")
            homepage_url = "N/A"
    
    if not homepage_url or homepage_url == "N/A":
        return "N/A"
    
    try:
        print(f"  📧 Searching for email: {person_name} at {homepage_url}")
        
        # Initialize email scraper with conservative settings
        config = {
            'max_urls': 20,  # Limit to avoid too many requests
            'timeout': 10,
            'follow_external_links': True,  # Only scrape the homepage
            'user_agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/126.0.0.0 Safari/537.36'
            )
        }
        
        scraper = EmailScraper(config)
        
        # Scrape emails from the homepage
        if scraper.scrape_emails(homepage_url):
            # Filter to valid emails only
            valid_emails = [e for e in (scraper.emails or []) if is_valid_email(e)]
            if valid_emails:
                print(f"  📧 Found {len(valid_emails)} valid emails, analyzing for {person_name}...")
                scraper.emails = valid_emails
                # Analyze emails to find the best match
                result = scraper.analyze_current_emails_for_person(person_name)
                if result and is_valid_email(result):
                    print(f"  ✅ Found likely email: {result}")
                    return result
                else:
                    print(f"  ⚠️ No matching valid email found for {person_name}")
                    return "Not found"
            else:
                print(f"  ⚠️ No valid emails found on homepage")
                return "Not found"
        else:
            print(f"  ❌ Failed to scrape homepage")
            return "Error"

    except Exception as e:
        print(f"  ❌ Email search error for {person_name}: {e}")
        return "Error"

if __name__ == "__main__":
    
    if not API_KEY:
        print("Error: GOOGLE_API_KEY environment variable must be set.")
        sys.exit(1)
    
    if not SCHOLAR_CSE_ID:
        print("Error: GOOGLE_SCHOLAR_CSE_ID environment variable must be set.")
        print("This should be a CSE configured to search scholar.google.com")
        sys.exit(1)
    
    if not GENERAL_CSE_ID:
        print("Warning: GOOGLE_GENERAL_CSE_ID environment variable not set.")
        print("Email search will be skipped. Set this to a CSE configured to search the entire web.")
    
    # Load query from file if present; fallback to env SEARCH_TERM
    qrec = _load_next_query_from_file(QUERY_LIST_PATH)
    if qrec and qrec.get("term"):
        scholar_search_term = qrec["term"]
        # If file provided affiliation tokens, override AFFILIATION_FILTER for this run
        if qrec.get("aff"):
            AFFILIATION_FILTER[:] = qrec["aff"]
        print(f"Using query from file: '{scholar_search_term}'")
        if AFFILIATION_FILTER:
            print(f"Affiliation filter (from file): {', '.join(AFFILIATION_FILTER)}")
    else:
        # Search term specifically designed to encourage "Cited by" and "h-index" in snippets
        scholar_search_term = os.getenv("SEARCH_TERM", "harvard university professor \"cited by\" \"h-index\"")
        if AFFILIATION_FILTER:
            print(f"Affiliation filter (from env): {', '.join(AFFILIATION_FILTER)}")
    
    min_citations_threshold = int(os.getenv("MIN_CITATIONS_THRESHOLD", "10000"))
    min_h_index_threshold = int(os.getenv("MIN_H_INDEX_THRESHOLD", "40"))
    
    require_h_index = os.getenv("REQUIRE_H_INDEX", "false").lower() == "true"

    print(f"Searching Google Scholar for qualified professors...")
    operator_label = ">=" if require_h_index else "(optional, if present) >="
    print(f"Criteria: citations >= {min_citations_threshold} AND h-index {operator_label} >= {min_h_index_threshold}")
    
    # Search Google Scholar profiles with pagination for bulk results
    all_items = []
    start_page = int(os.getenv("START_PAGE", "1"))
    page = start_page
    max_pages = int(os.getenv("MAX_PAGES", str(CSE_MAX_PAGES)))
    
    print(f"Searching Google Scholar across multiple pages for bulk results...")
    if start_page > 1:
        print(f"Starting from page {start_page} (skipping pages 1-{start_page-1})")
    
    while page <= max_pages:
        start_index = (page - 1) * CSE_NUM_PER_PAGE + 1
        print(f"\n📄 Searching page {page} (results {start_index}-{start_index + CSE_NUM_PER_PAGE - 1})...")
        
        json_result = search_google_custom_search(scholar_search_term, API_KEY, SCHOLAR_CSE_ID, start_index, CSE_NUM_PER_PAGE)
        
        if json_result and "items" in json_result:
            page_items = json_result.get("items", [])
            if not page_items:
                print(f"  ⚠️ No more results found on page {page}")
                break
            
            all_items.extend(page_items)
            print(f"  ✅ Found {len(page_items)} results on page {page}")
            
            # Check if we've reached the end of results
            if len(page_items) < CSE_NUM_PER_PAGE:
                print(f"  ℹ️ Reached end of results (only {len(page_items)} items on this page)")
                break
        else:
            print(f"  ❌ Failed to retrieve results from page {page}")
            break
        
        page += 1
    
    print(f"\n📊 Total results collected: {len(all_items)} from {page-1} pages")
    # If we successfully used a queued query, consume it now so next run uses the next line
    if qrec and qrec.get("rest") is not None:
        _consume_query_file(QUERY_LIST_PATH, qrec["rest"])
    
    if all_items:
        print(f"\nAnalyzing {len(all_items)} total results from Google Scholar...")
        
        qualifying_profiles = []
            
        # Build a set of already-present keys to skip early (reduces wasted work)
        def _load_existing_keys():
            keys = set()
            try:
                for fp in [
                    os.path.join(os.path.dirname(__file__), "qualified_scholar_profiles_with_wikipedia.csv"),
                    os.path.join(os.path.dirname(__file__), "qualified_scholar_profiles_without_wikipedia.csv"),
                    os.path.join(os.path.dirname(__file__), "without_email.csv"),
                ]:
                    if os.path.exists(fp) and os.stat(fp).st_size > 0:
                        with open(fp, "r", newline="", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                n = (row.get("name") or "").lower().strip()
                                purl = (row.get("profile_url") or "").strip()
                                if n:
                                    keys.add((n, purl))
            except Exception:
                pass
            return keys

        existing_keys = _load_existing_keys()
        
        for i, item in enumerate(all_items, start=1):
            title = clean_unicode_text(item.get("title", ""))
            snippet = clean_unicode_text(item.get("snippet", ""))
            link = clean_unicode_text(item.get("link", ""))
            
            print(f"\n--- Result {i} ---")
            print(f"Title: {clean_unicode_text(title)}")
            print(f"Snippet: {clean_unicode_text(snippet[:200])}...") 

            # Early duplicate skip by (name, profile_url) to avoid extra API/scrape work
            early_name = extract_name_from_title(title)
            dup_key = (early_name.lower().strip(), link.strip() if link else "")
            if dup_key in existing_keys:
                print(f"  ℹ️ Skipping already present: {early_name}")
                continue
            
            # Extract metrics from combined item text (snippet + htmlSnippet + title)
            metrics = extract_metrics_from_item(item)
            citations = metrics["citations"]
            h_index = metrics["h_index"]
            
            print(f"Extracted: citations={citations}, h-index={h_index}")
                
            # If snippet shows elision (e.g., 'Cited by ...' or 'h-index, ...') or either missing, try fetching from profile
            needs_fetch = False
            if citations is None or h_index is None:
                needs_fetch = True
            else:
                if re.search(r"Cited by\s*\.\.\.", snippet, flags=re.IGNORECASE) or re.search(r"h[\s\-–—]?index\s*,\s*\.\.\.", snippet, flags=re.IGNORECASE):
                    needs_fetch = True

            aff_text = ""
            if needs_fetch and link and link.startswith("http"):
                print("  Attempting to fetch metrics from profile page...")
                prof = fetch_profile_metrics(link)
                if citations is None and prof.get("citations") is not None:
                    citations = prof["citations"]
                    print(f"  ✅ Filled citations from profile: {citations}")
                if h_index is None and prof.get("h_index") is not None:
                    h_index = prof["h_index"]
                    print(f"  ✅ Filled h-index from profile: {h_index}")
                aff_text = (prof.get("affiliation_text") or "")
                # Affiliation filtering
                if AFFILIATION_FILTER:
                    aff_text = (prof.get("affiliation_text") or "").lower()
                    homepage_probe = fetch_homepage_from_profile(link)
                    homepage_l = (homepage_probe or "").lower()
                    match_aff = any(t in aff_text for t in AFFILIATION_FILTER)
                    match_dom = any(t in homepage_l for t in AFFILIATION_FILTER)
                    if not (match_aff or match_dom):
                        print("  🚫 Skipping due to AFFILIATION_FILTER mismatch")
                        continue
            # If still missing and we have a profile URL, try a targeted CSE refetch
            if (citations is None or h_index is None) and link and "user=" in link:
                tmetrics = try_cse_refetch_metrics_via_profile_id(API_KEY, SCHOLAR_CSE_ID, link)
                if citations is None and tmetrics["citations"] is not None:
                    citations = tmetrics["citations"]
                    print(f"  ✅ Filled citations via targeted CSE: {citations}")
                if h_index is None and tmetrics["h_index"] is not None:
                    h_index = tmetrics["h_index"]
                    print(f"  ✅ Filled h-index via targeted CSE: {h_index}")
            # OpenAlex fallback by name if still missing
            if (citations is None or h_index is None):
                person_name_fallback = extract_name_from_title(title)
                if person_name_fallback and person_name_fallback != "Unknown":
                    print("  Attempting OpenAlex fallback by name...")
                    oa = fetch_metrics_from_openalex(person_name_fallback, institution_hint="harvard")
                    if citations is None and oa.get("citations") is not None:
                        citations = oa["citations"]
                        print(f"  ✅ Filled citations from OpenAlex: {citations}")
                    if h_index is None and oa.get("h_index") is not None:
                        h_index = oa["h_index"]
                        print(f"  ✅ Filled h-index from OpenAlex: {h_index}")
            
            # qualified leads (both thresholds if available)
            qualifies = False
            if citations is not None and citations >= min_citations_threshold:
                if require_h_index:
                    qualifies = (h_index is not None and h_index >= min_h_index_threshold)
                else:
                    qualifies = (h_index is None or h_index >= min_h_index_threshold)
                
            if qualifies:
                print(f"✅ QUALIFIES!")
                
                # Extract and clean name
                person_name = extract_name_from_title(title)
                print(f"Name: {person_name}")
                
                # Fetch homepage from profile
                homepage_url = "N/A"
                if link and link.startswith("http"):
                    homepage_url = fetch_homepage_from_profile(link)
                
                # Wikipedia via MediaWiki API (free)
                wikipedia_url = fetch_wikipedia_via_mediawiki(person_name)
                
                profile_data = {
                    "name": person_name,
                    "citations": citations,
                    "h_index": h_index if h_index is not None else "N/A",
                    "profile_url": clean_unicode_text(link) if link else link,
                    "homepage_url": homepage_url,
                    "wikipedia_url": clean_unicode_text(wikipedia_url) if wikipedia_url else wikipedia_url,
                    "affiliation_text": aff_text or "",
                }
                
                # Enrich homepage_url based on Wikipedia or general CSE
                if profile_data["wikipedia_url"] and profile_data["wikipedia_url"] != "N/A":
                    site = fetch_official_site_from_wikidata(profile_data["wikipedia_url"])
                    if site and site != "N/A" and is_valid_homepage_url(site):
                        profile_data["homepage_url"] = site
                        if DEBUG_FETCH:
                            print(f"  [debug] homepage from Wikidata: {site}")
                    elif (not profile_data["homepage_url"]) or profile_data["homepage_url"] == "N/A":
                        # Fallback: external links from Wikipedia page
                        site2 = fetch_website_from_wikipedia_extlinks(profile_data["wikipedia_url"])
                        if site2 and site2 != "N/A" and is_valid_homepage_url(site2):
                            profile_data["homepage_url"] = site2
                            if DEBUG_FETCH:
                                print(f"  [debug] homepage from Wikipedia extlinks: {site2}")
                
                # If still no valid homepage, try ONE conservative CSE search
                if (not profile_data["homepage_url"]) or profile_data["homepage_url"] == "N/A" or not is_valid_homepage_url(profile_data["homepage_url"]):
                    print(f"  🔍 Searching for better homepage for {person_name}...")
                    
                    # Try ONE targeted search: name + "homepage site:edu"
                    query = f'"{person_name}" homepage site:edu'
                    url = first_url_from_general_cse(query)
                    if url and url != "N/A" and is_valid_homepage_url(url):
                        profile_data["homepage_url"] = url
                        if DEBUG_FETCH:
                            print(f"  [debug] homepage from CSE query '{query}': {url}")
                    else:
                        # If that fails, try ONE general search without site restriction
                        url = first_url_from_general_cse(person_name)
                        if url and url != "N/A" and is_valid_homepage_url(url):
                            profile_data["homepage_url"] = url
                            if DEBUG_FETCH:
                                print(f"  [debug] homepage from general CSE: {url}")
                        else:
                            profile_data["homepage_url"] = "N/A"
                
                # Find email for this person using their homepage URL
                email = find_email_for_person(person_name, profile_data["homepage_url"], profile_data["profile_url"])
                # If no email and we have a Wikipedia page but no good homepage, try external links site directly
                if (not email or email.strip().lower() in {"n/a", "not found", "error", ""}) and \
                   (profile_data.get("wikipedia_url") and str(profile_data.get("wikipedia_url")).strip().upper() != "N/A"):
                    try:
                        site_any = fetch_website_from_wikipedia_extlinks(profile_data["wikipedia_url"]) or ""
                        if site_any:
                            alt_email = find_email_for_person(person_name, site_any, profile_data["profile_url"])  # may or may not pass strict URL check
                            if alt_email and alt_email.strip().lower() not in {"n/a", "not found", "error", ""}:
                                email = alt_email
                    except Exception:
                        pass
                profile_data["email"] = email

                # Generate summary with no-CSE fallback chain
                summary_text = "N/A"
                wiki_url_local = profile_data.get("wikipedia_url") or ""
                homepage_local = profile_data.get("homepage_url") or ""

                # 1) Wikipedia extract
                if wiki_url_local and wiki_url_local != "N/A":
                    wiki_extract = fetch_wikipedia_extract(wiki_url_local)
                    if wiki_extract:
                        summary_text = summarize_with_gpt(wiki_extract, mode="wiki")

                # 2) Homepage text (if summary still N/A)
                if (not summary_text or summary_text == "N/A") and is_valid_homepage_url(homepage_local):
                    htxt = fetch_homepage_text(homepage_local)
                    if htxt:
                        summary_text = summarize_with_gpt(htxt, mode="home")

                # 3) Wikipedia external links → homepage text (no CSE)
                if (not summary_text or summary_text == "N/A") and wiki_url_local and wiki_url_local != "N/A":
                    site_from_ext = fetch_website_from_wikipedia_extlinks(wiki_url_local)
                    if site_from_ext and is_valid_homepage_url(site_from_ext):
                        htxt2 = fetch_homepage_text(site_from_ext)
                        if htxt2:
                            summary_text = summarize_with_gpt(htxt2, mode="home")

                # 4) Heuristic 1–2 sentence if everything else failed
                if not summary_text or summary_text == "N/A":
                    summary_text = _heuristic_summary(
                        person_name,
                        (profile_data.get("affiliation_text") or ""),
                        snippet,
                    )
                profile_data["summary"] = summary_text
                
                qualifying_profiles.append(profile_data)
                print(f"✅ Added to qualified list.")
            else:
                if citations is None:
                    print(f"⚠️ Could not extract citations from snippet or profile.")
                elif citations < min_citations_threshold:
                    print(f"❌ Does not qualify (citations: {citations} < {min_citations_threshold})")
                elif require_h_index and (h_index is None or h_index < min_h_index_threshold):
                    print(f"❌ Does not qualify (h-index: {h_index} < {min_h_index_threshold})")
            
        # After processing all items, write qualifying profiles to CSV, handling uniqueness
        output_file_wiki = "qualified_scholar_profiles_with_wikipedia.csv"
        output_file_no_wiki = "qualified_scholar_profiles_without_wikipedia.csv"
        NEW_FIELDNAMES = ["Name", "email", "wikipedia_url", "info", "is_wiki"]

        # Split by email availability first (treat N/A, Not found, Error, empty as no email)
        def _is_missing_email(val: str) -> bool:
            if not isinstance(val, str):
                return True
            v = val.strip().lower()
            return (v == "n/a") or (v == "not found") or (v == "error") or (v == "")

        profiles_without_email = [p for p in qualifying_profiles if _is_missing_email(p.get("email", ""))]
        profiles_with_email = [p for p in qualifying_profiles if not _is_missing_email(p.get("email", ""))]

        # From those that have emails, separate by Wikipedia presence
        profiles_with_wiki = [
            p for p in profiles_with_email
            if p.get("wikipedia_url") and str(p.get("wikipedia_url")).strip().upper() != "N/A"
        ]
        profiles_without_wiki = [
            p for p in profiles_with_email
            if (not p.get("wikipedia_url")) or str(p.get("wikipedia_url")).strip().upper() == "N/A"
        ]

        # Reduce to new schema rows
        def to_new_schema_row(p: dict, is_wiki_flag: int) -> dict:
            return {
                "Name": p.get("name") or p.get("Name") or "Unknown",
                "email": p.get("email") or "N/A",
                "wikipedia_url": p.get("wikipedia_url") or "N/A",
                "info": p.get("summary") or p.get("info") or "N/A",
                "is_wiki": str(is_wiki_flag),
            }

        rows_with_wiki_new = [to_new_schema_row(p, 1) for p in profiles_with_wiki]
        rows_without_wiki_new = [to_new_schema_row(p, 0) for p in profiles_without_wiki]

        # Function to write to CSV, including header check
        def write_profiles_to_csv(file_path, profiles_list, fieldnames):
            existing_profiles = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", newline="", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            existing_profiles.append(row)
                except Exception as e:
                    print(f"Warning: Could not read existing CSV {file_path}: {e}")
            
            new_profiles = []
            # De-duplicate by (Name, wikipedia_url) - prioritize Wikipedia URL for uniqueness
            existing_keys_local = set()
            for p in existing_profiles:
                nm = (p.get("Name") or p.get("name") or "").lower().strip()
                wurl = (p.get("wikipedia_url") or "").strip().lower()
                # Use Wikipedia URL if available, otherwise fall back to email
                unique_id = wurl if wurl and wurl != "n/a" else (p.get("email") or "").strip().lower()
                key = (nm, unique_id)
                existing_keys_local.add(key)

            for profile in profiles_list:
                profile_name_lower = (profile.get("Name") or profile.get("name") or "").lower().strip()
                wurl = (profile.get("wikipedia_url") or "").strip().lower()
                eml = (profile.get("email") or "").strip().lower()
                # Use Wikipedia URL if available, otherwise fall back to email
                unique_id = wurl if wurl and wurl != "n/a" else eml
                key_local = (profile_name_lower, unique_id)
                if key_local not in existing_keys_local:
                    # Final Unicode cleaning before CSV storage
                    cleaned_profile = {}
                    for key, value in profile.items():
                        if isinstance(value, str):
                            cleaned_profile[key] = clean_unicode_text(value)
                        else:
                            cleaned_profile[key] = value
                    new_profiles.append(cleaned_profile)
                    existing_keys_local.add(key_local)
                else:
                    print(f"⚠️ Skipping duplicate in {file_path}: {profile.get('Name') or profile.get('name')}")
            
            # Always ensure the file exists with headers, even if no new profiles
            write_header = not os.path.exists(file_path) or os.stat(file_path).st_size == 0
            
            if new_profiles:
                with open(file_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    if write_header:
                        writer.writeheader()
                    writer.writerows(new_profiles)
                print(f"\n✅ Successfully wrote {len(new_profiles)} new qualified profiles to {file_path}")
            else:
                if write_header:
                    with open(file_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                    print(f"\n📄 Created {file_path} with headers (no new profiles to add)")
                else:
                    print(f"\nℹ️ No new qualified profiles to add to {file_path} (all were duplicates).")

        # Always write all files, even if empty
        print(f"\n📁 Creating CSV files...")
        
        # Write profiles WITH Wikipedia pages (new schema)
        write_profiles_to_csv(output_file_wiki, rows_with_wiki_new, NEW_FIELDNAMES)

        # Write profiles WITHOUT Wikipedia pages (new schema)
        write_profiles_to_csv(output_file_no_wiki, rows_without_wiki_new, NEW_FIELDNAMES)
        
        # Write profiles WITHOUT EMAIL to a separate CSV and DO NOT include them in the above two
        output_file_no_email = "without_email.csv"
        # For without_email.csv, keep the new schema with empty email
        rows_no_email_new = [
            {
                "Name": p.get("name") or p.get("Name") or "Unknown",
                "email": "Not found",
                "wikipedia_url": p.get("wikipedia_url") or "N/A",
                "info": p.get("summary") or p.get("info") or "N/A",
                "is_wiki": "1" if (p.get("wikipedia_url") and str(p.get("wikipedia_url")).strip().upper() != "N/A") else "0",
            }
            for p in profiles_without_email
        ]
        write_profiles_to_csv(output_file_no_email, rows_no_email_new, NEW_FIELDNAMES)
        
        # Show file creation summary
        print(f"\n📊 CSV Files Created:")
        print(f"   • {output_file_wiki}: {len(rows_with_wiki_new)} profiles with Wikipedia pages (emails present)")
        print(f"   • {output_file_no_wiki}: {len(rows_without_wiki_new)} profiles without Wikipedia pages (emails present)")
        print(f"   • {output_file_no_email}: {len(rows_no_email_new)} profiles without email")
        
        # Debug: Show what's happening with Wikipedia URLs
        print(f"\n🔍 Debug - Wikipedia URL status:")
        for i, prof in enumerate(qualifying_profiles, 1):
            has_wiki = bool(prof.get("wikipedia_url")) and str(prof.get("wikipedia_url")).strip().upper() != "N/A"
            wiki_status = "✅ Found" if has_wiki else "❌ Not found"
            print(f"   {i}. {prof['name']}: {wiki_status}")
            if has_wiki:
                print(f"      URL: {prof['wikipedia_url']}")
            # New schema preview: show info + wiki flag
            is_wiki_flag = "1" if has_wiki else "0"
            print(f"   Wikipedia: {prof['wikipedia_url'] if prof['wikipedia_url'] else 'N/A'}")
            print(f"   Email: {prof['email'] if prof['email'] else 'N/A'} | is_wiki={is_wiki_flag}")
            print()
                        
        # Final total CSE calls
        print(f"\nTotal Google CSE calls: {CSE_CALL_COUNT}")
    else:
        print(f"\n❌ No profiles found meeting the criteria in this search.")
        print("Consider:")
        print("1. Adjusting the search term")
        print("2. Lowering the thresholds")
        print("3. Checking if your Scholar CSE is properly configured")
        # Final total CSE calls
        print(f"\nTotal Google CSE calls: {CSE_CALL_COUNT}")
    
