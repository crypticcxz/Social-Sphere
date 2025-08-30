import os
import sys
import re
import csv
from typing import Optional, Dict, List
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") 
SCHOLAR_CSE_ID = os.getenv("GOOGLE_SCHOLAR_CSE_ID")  
GENERAL_CSE_ID = os.getenv("GOOGLE_GENERAL_CSE_ID")

def search_google_custom_search(query: str, api_key: str, cx_id: str, start_index: int = 1) -> Optional[Dict]:
    """Performs a Google Custom Search and returns the JSON response."""
    if not api_key or not cx_id:
        print("Error: API key or CSE ID not provided.")
        return None

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(
            q=query,
            cx=cx_id,
            num=10, 
            start=start_index
        ).execute()
        return res
    except Exception as e:
        print(f"An error occurred during custom search: {e}")
        return None

def extract_metrics_from_snippet(snippet: str) -> Dict[str, Optional[int]]:
    """Extract citations and h-index from snippet text."""
    metrics = {"citations": None, "h_index": None}
    
    # Citations: support both "Cited by 12,345" and "Citations, 12345"
    citations_match = re.search(r"(?:Cited by|Citations?)\s*[,:]\s*([0-9,]+)", snippet, re.IGNORECASE)
    if citations_match:
        try: 
            metrics["citations"] = int(citations_match.group(1).replace(",", ""))
        except ValueError:
            pass
    
    # h-index: support "h-index: 45", "h-index, 45", and "h index 45"
    h_index_match = re.search(r"h[\s\-–—]?index\s*[,:]?\s*([0-9]{1,4})", snippet, re.IGNORECASE)
    if h_index_match:
        try:
            metrics["h_index"] = int(h_index_match.group(1))
        except ValueError:
            pass
    
    return metrics


def fetch_h_index_from_profile(profile_url: str) -> Optional[int]:
    """Best-effort attempt to fetch h-index from the Google Scholar profile page.
    Returns None if not found or request fails."""
    try:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(profile_url, headers=headers, timeout=15)
        if resp.status_code != 200 or not resp.text:
            return None
        html = resp.text
        
        match = re.search(r"h[\s\-–—]?index\s*[,:]?\s*([0-9]{1,4})", html, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None
    except Exception:
        return None

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
    """Searches general Google for a person's Wikipedia page and returns the URL if found."""
    if not person_name or person_name == "Unknown":
        return None

    if not general_cx_id:
        print("  ⚠️ General CSE ID not configured for Wikipedia search.")
        return None

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        
        # Try multiple search strategies for better Wikipedia discovery
        search_queries = [
            f'"{person_name}" wikipedia',
            f'"{person_name}" site:wikipedia.org',
            f'"{person_name}" "wikipedia" "professor"',
            f'"{person_name}" "wikipedia" "harvard"',
            f'"{person_name}" "wikipedia" "academic"',
            f'"{person_name}" "wikipedia" "researcher"'
        ]
        
        for query in search_queries:
            print(f"  🔍 Wikipedia search: {query}")
            res = service.cse().list(q=query, cx=general_cx_id, num=5).execute()

            if "items" in res:
                for item in res["items"]:
                    link = item.get("link", "")
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    
                    # Check if it's a Wikipedia page
                    if "wikipedia.org" in link.lower():
                        print(f"  📖 Found Wikipedia page: {link}")
                        print(f"     Title: {title}")
                        
                        # Intelligent name matching with multiple strategies
                        if is_likely_match(person_name, title, snippet, link):
                            print(f"  ✅ Confirmed match for: {person_name}")
                            return link
                        else:
                            print(f"  ⚠️ Wikipedia page found but name doesn't match: {title}")
        
        print(f"  ❌ No Wikipedia page found for {person_name} after trying {len(search_queries)} search strategies")
        return None

    except Exception as e:
        print(f"  ❌ Wikipedia search error for {person_name}: {e}")
        return None

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
    
    # Strategy 1: Exact match (after cleaning)
    if person_clean == title_clean:
        print(f"     🎯 Exact name match: '{person_clean}' == '{title_clean}'")
        return True
    
    # Strategy 2: Person name is contained in title
    if person_clean in title_clean:
        print(f"     🎯 Person name contained in title: '{person_clean}' in '{title_clean}'")
        return True
    
    # Strategy 3: Title is contained in person name (for cases like "Jeff W. Litchman" vs "Jeff Litchman")
    if title_clean in person_clean:
        print(f"     🎯 Title contained in person name: '{title_clean}' in '{person_clean}'")
        return True
    
    # Strategy 4: Check if at least 2 significant name parts match
    person_parts = [part for part in person_clean.split() if len(part) > 2]  # Ignore initials
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
    
    # Search term specifically designed to encourage "Cited by" and "h-index" in snippets
    scholar_search_term = "harvard university professor \"cited by\" \"h-index\""
    
    min_citations_threshold = int(os.getenv("MIN_CITATIONS_THRESHOLD", "10000"))
    min_h_index_threshold = int(os.getenv("MIN_H_INDEX_THRESHOLD", "40"))
    
    require_h_index = os.getenv("REQUIRE_H_INDEX", "false").lower() == "true"

    print(f"Searching Google Scholar for qualified professors...")
    operator_label = ">=" if require_h_index else "(optional, if present) >="
    print(f"Criteria: citations >= {min_citations_threshold} AND h-index {operator_label} >= {min_h_index_threshold}")
    
    # Search Google Scholar profiles with pagination for bulk results
    all_items = []
    page = 1
    max_pages = 10  # Search up to 10 pages (100 results total)
    
    print(f"Searching Google Scholar across multiple pages for bulk results...")
    
    while page <= max_pages:
        start_index = (page - 1) * 10 + 1
        print(f"\n📄 Searching page {page} (results {start_index}-{start_index + 9})...")
        
        json_result = search_google_custom_search(scholar_search_term, API_KEY, SCHOLAR_CSE_ID, start_index)
        
        if json_result and "items" in json_result:
            page_items = json_result.get("items", [])
            if not page_items:
                print(f"  ⚠️ No more results found on page {page}")
                break
            
            all_items.extend(page_items)
            print(f"  ✅ Found {len(page_items)} results on page {page}")
            
            # Check if we've reached the end of results
            if len(page_items) < 10:
                print(f"  ℹ️ Reached end of results (only {len(page_items)} items on this page)")
                break
        else:
            print(f"  ❌ Failed to retrieve results from page {page}")
            break
        
        page += 1
    
    print(f"\n📊 Total results collected: {len(all_items)} from {page-1} pages")
    
    if all_items:
        print(f"\nAnalyzing {len(all_items)} total results from Google Scholar...")
        
        qualifying_profiles = []
        
        for i, item in enumerate(all_items, start=1):
            title = clean_unicode_text(item.get("title", ""))
            snippet = clean_unicode_text(item.get("snippet", ""))
            link = clean_unicode_text(item.get("link", ""))
            
            print(f"\n--- Result {i} ---")
            print(f"Title: {clean_unicode_text(title)}")
            print(f"Snippet: {clean_unicode_text(snippet[:200])}...") 
            
            # Extract metrics
            metrics = extract_metrics_from_snippet(snippet)
            citations = metrics["citations"]
            h_index = metrics["h_index"]
            
            print(f"Extracted: citations={citations}, h-index={h_index}")
            
            # qualified leads
            qualifies = False
            if citations is not None and citations >= min_citations_threshold:
                
                if h_index is not None:
                    qualifies = h_index >= min_h_index_threshold
                else:
                    qualifies = True  # Qualify on citations alone if h-index not found
            
            if qualifies:
                print(f"✅ QUALIFIES!")
                
                # Extract and clean name
                person_name = extract_name_from_title(title)
                print(f"Name: {person_name}")
                
                # If h-index missing, try to fetch from profile page as a best-effort
                if h_index is None and link:
                    print("  Attempting to fetch h-index from profile page...")
                    fetched_h = fetch_h_index_from_profile(link)
                    if fetched_h is not None:
                        print(f"  ✅ Fetched h-index from profile: {fetched_h}")
                        h_index = fetched_h
                    else:
                        print("  ⚠️ Could not fetch h-index from profile.")
                
                # web search
                email = "Not searched"
                if GENERAL_CSE_ID:
                    print(f"Searching for email for {person_name}...")
                    email = search_for_email(person_name, API_KEY, GENERAL_CSE_ID)
                    wikipedia_url = search_for_wikipedia_page(person_name, API_KEY, GENERAL_CSE_ID)
                else:
                    print("  ⚠️ Skipping email search (GENERAL_CSE_ID not configured).")
                    wikipedia_url = None
                
                profile_data = {
                    "name": person_name,
                    "citations": citations,
                    "h_index": h_index if h_index is not None else "N/A",
                    "email": clean_unicode_text(email) if email else email,
                    "profile_url": clean_unicode_text(link) if link else link,
                    "wikipedia_url": clean_unicode_text(wikipedia_url) if wikipedia_url else wikipedia_url
                }
                
                qualifying_profiles.append(profile_data)
                print(f"✅ Added to qualified list.")
            else:
                if citations is None:
                    print(f"⚠️ Could not extract citations from snippet.")
                elif citations < min_citations_threshold:
                    print(f"❌ Does not qualify (citations: {citations} < {min_citations_threshold})")
                elif h_index is not None and h_index < min_h_index_threshold:
                    print(f"❌ Does not qualify (h-index: {h_index} < {min_h_index_threshold})")
        
        # Write qualifying profiles to CSV, handling uniqueness
        if qualifying_profiles:
            output_file_wiki = "qualified_scholar_profiles_with_wikipedia.csv"
            output_file_no_wiki = "qualified_scholar_profiles_without_wikipedia.csv"
            fieldnames = ["name", "citations", "h_index", "email", "profile_url", "wikipedia_url"]
            
            # Separate profiles based on Wikipedia presence
            profiles_with_wiki = [p for p in qualifying_profiles if p["wikipedia_url"]]
            profiles_without_wiki = [p for p in qualifying_profiles if not p["wikipedia_url"]]

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
                existing_names = {p["name"].lower().strip() for p in existing_profiles if p.get("name")}

                for profile in profiles_list:
                    profile_name_lower = profile["name"].lower().strip()
                    if profile_name_lower not in existing_names:
                        # Final Unicode cleaning before CSV storage
                        cleaned_profile = {}
                        for key, value in profile.items():
                            if isinstance(value, str):
                                cleaned_profile[key] = clean_unicode_text(value)
                            else:
                                cleaned_profile[key] = value
                        
                        new_profiles.append(cleaned_profile)
                        existing_names.add(profile_name_lower)
                    else:
                        print(f"⚠️ Skipping duplicate in {file_path}: {profile['name']}")
                
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
                    # Create file with just headers if it doesn't exist
                    if write_header:
                        with open(file_path, "w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                        print(f"\n📄 Created {file_path} with headers (no new profiles to add)")
                    else:
                        print(f"\nℹ️ No new qualified profiles to add to {file_path} (all were duplicates).")

            # Always write both files, even if empty
            print(f"\n📁 Creating CSV files...")
            
            # Write profiles WITH Wikipedia pages
            write_profiles_to_csv(output_file_wiki, profiles_with_wiki, fieldnames)
            
            # Write profiles WITHOUT Wikipedia pages  
            write_profiles_to_csv(output_file_no_wiki, profiles_without_wiki, fieldnames)
            
            # Show file creation summary
            print(f"\n📊 CSV Files Created:")
            print(f"   • {output_file_wiki}: {len(profiles_with_wiki)} profiles with Wikipedia pages")
            print(f"   • {output_file_no_wiki}: {len(profiles_without_wiki)} profiles without Wikipedia pages")
            
            # Debug: Show what's happening with Wikipedia URLs
            print(f"\n🔍 Debug - Wikipedia URL status:")
            for i, prof in enumerate(qualifying_profiles, 1):
                wiki_status = "✅ Found" if prof["wikipedia_url"] else "❌ Not found"
                print(f"   {i}. {prof['name']}: {wiki_status}")
                if prof["wikipedia_url"]:
                    print(f"      URL: {prof['wikipedia_url']}")
            
            # Show summary of all qualified profiles found in this run
            print("\n=== SUMMARY OF QUALIFIED PROFILES ===")
            for i, prof in enumerate(qualifying_profiles, 1):
                print(f"{i}. {prof['name']}")
                print(f"   Citations: {prof['citations']:,}")
                print(f"   H-index: {prof['h_index']}")
                print(f"   Email: {prof['email']}")
                print(f"   Profile: {prof['profile_url']}")
                print(f"   Wikipedia: {prof['wikipedia_url'] if prof['wikipedia_url'] else 'N/A'}")
                print()
                    
        else:
            print(f"\n❌ No profiles found meeting the criteria in this search.")
            print("Consider:")
            print("1. Adjusting the search term")
            print("2. Lowering the thresholds")
            print("3. Checking if your Scholar CSE is properly configured")
    else:
        print("Failed to retrieve search results from Google Scholar.")
        print("Check your API key and Scholar CSE ID configuration.")
