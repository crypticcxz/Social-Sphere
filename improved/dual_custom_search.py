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
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

def extract_name_from_title(title: str) -> str:
    """Extract person's name from title."""
    if not title:
        return "Unknown"
    
    # Handle Google Scholar profile titles like "George Church‬ - ‪Google Scholar‬"
    # First remove the special Unicode markers
    name = re.sub(r'[‪‬]', '', title)
    
    # Remove "Google Scholar" suffix (with or without dash)
    name = re.sub(r'\s*-\s*Google Scholar.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Google Scholar.*$', '', name, flags=re.IGNORECASE)
    
    # Clean up extra spaces and dashes
    name = name.strip()
    name = re.sub(r'\s*-\s*$', '', name)  # Remove trailing dash
    name = re.sub(r'\s+', ' ', name)  # Normalize spaces
    
    return name if name else "Unknown"

def search_for_email(person_name: str, api_key: str, general_cx_id: str) -> str:
    """Search for person's email using their name + 'email' on general Google search."""
    if not person_name or person_name == "Unknown":
        return "Not found"
    
    if not general_cx_id:
        print("  ⚠️ General CSE ID not configured for email search.")
        return "CSE not configured"
    
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        
        
        search_queries = [
            f'"{person_name}" email site:.edu',  # University email
            f'"{person_name}" contact email harvard',  # Harvard-specific
            f'"{person_name}" email faculty profile',  # Faculty profile
            f'"{person_name}" email contact information'  # General contact
        ]
        
        for query in search_queries:
            print(f"  Searching for email: {query}")
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
                            if '.edu' in email.lower() or any(part.lower() in email.lower() for part in person_name.lower().split()):
                                print(f"  ✅ Found email: {email}")
                                return email
                        
                        
                        found_email = email_matches[0]
                        print(f"  ✅ Found email: {found_email}")
                        return found_email
        
        print(f"  ❌ No email found after trying {len(search_queries)} search strategies")
        return "Not found"
        
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
    
    # Search term specifically designed to encourage 'Cited by' and 'h-index' in snippets
    scholar_search_term = "harvard university professor \"cited by\" \"h-index\""
    
    
    min_citations_threshold = int(os.getenv("MIN_CITATIONS_THRESHOLD", "10000"))
    min_h_index_threshold = int(os.getenv("MIN_H_INDEX_THRESHOLD", "40"))
    
    require_h_index = os.getenv("REQUIRE_H_INDEX", "false").lower() == "true"

    print(f"Searching Google Scholar for qualified professors...")
    operator_label = ">=" if require_h_index else "(optional, if present) >="
    print(f"Criteria: citations >= {min_citations_threshold} AND h-index {operator_label} {min_h_index_threshold}")
    
    # Search Google Scholar profiles
    json_result = search_google_custom_search(scholar_search_term, API_KEY, SCHOLAR_CSE_ID)

    if json_result:
        items = json_result.get("items", [])
        if not items:
            print("No items found in the Google Scholar search results.")
        else:
            print(f"\nAnalyzing {len(items)} results from Google Scholar...")
            
            qualifying_profiles = []
            
            for i, item in enumerate(items, start=1):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                
                print(f"\n--- Result {i} ---")
                print(f"Title: {title}")
                print(f"Snippet: {snippet[:200]}...") 
                
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
                    else:
                        print("  ⚠️ Skipping email search (GENERAL_CSE_ID not configured)")
                    
                    profile_data = {
                        "name": person_name,
                        "citations": citations,
                        "h_index": h_index if h_index is not None else "N/A",
                        "email": email,
                        "profile_url": link
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
                output_file = "qualified_scholar_profiles.csv"
                fieldnames = ["name", "citations", "h_index", "email", "profile_url"]
                
                # Read existing profiles to check for duplicates
                existing_profiles_names = set()
                if os.path.exists(output_file):
                    try:
                        with open(output_file, "r", newline="", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if "name" in row:
                                    existing_profiles_names.add(row["name"].lower().strip())
                    except Exception as e:
                        print(f"Warning: Could not read existing CSV for duplicate check: {e}")
                
                new_profiles_to_write = []
                for profile in qualifying_profiles:
                    profile_name_lower = profile["name"].lower().strip()
                    if profile_name_lower not in existing_profiles_names:
                        new_profiles_to_write.append(profile)
                        existing_profiles_names.add(profile_name_lower)
                    else:
                        print(f"⚠️ Skipping duplicate: {profile['name']}")
                
                if new_profiles_to_write:
                    # Determine if header needs to be written
                    write_header = not os.path.exists(output_file) or os.stat(output_file).st_size == 0
                    
                    with open(output_file, "a", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        
                        if write_header:
                            writer.writeheader()
                        
                        writer.writerows(new_profiles_to_write)
                    
                    print(f"\n✅ Successfully wrote {len(new_profiles_to_write)} new qualified profiles to {output_file}")
                else:
                    print(f"\nℹ️ No new qualified profiles to add to CSV (all were duplicates).")
                
                # Show summary of all qualified profiles found in this run
                print("\n=== SUMMARY OF QUALIFIED PROFILES ===")
                for i, prof in enumerate(qualifying_profiles, 1):
                    print(f"{i}. {prof['name']}")
                    print(f"   Citations: {prof['citations']:,}")
                    print(f"   H-index: {prof['h_index']}")
                    print(f"   Email: {prof['email']}")
                    print(f"   Profile: {prof['profile_url']}")
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