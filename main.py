import os
import sys
import re
import csv
from typing import Optional, Dict, List
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") 
CUSTOM_SEARCH_ENGINE_ID = os.getenv("GOOGLE_CSE_ID")

def search_google_custom_search(query, api_key, cx_id):
    if not api_key or not cx_id:
        print("Error: GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables must be set.")
        return None

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        res = service.cse().list(q=query, cx=cx_id, num=10).execute()
        return res
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def extract_metrics_from_snippet(snippet: str) -> Dict[str, Optional[int]]:
    """Extract citations and h-index from snippet text."""
    metrics = {"citations": None, "h_index": None}
    
    # Extract citations: "Citations, 200004" or "Cited by 12,345"
    citations_match = re.search(r"(?:Citations?|Cited by)\s*[,:]\s*([0-9][0-9,]*)", snippet, re.IGNORECASE)
    if citations_match:
        try:
            metrics["citations"] = int(citations_match.group(1).replace(",", ""))
        except ValueError:
            pass
    
    # Extract h-index: "h-index, 217" or "h-index: 45"
    h_index_match = re.search(r"h-index\s*[,:]\s*([0-9]+)", snippet, re.IGNORECASE)
    if h_index_match:
        try:
            metrics["h_index"] = int(h_index_match.group(1))
        except ValueError:
            pass
    
    return metrics

def clean_name(name: str) -> str:
    """Clean and normalize a person's name."""
    if not name:
        return "Unknown"
    
    # Remove special Unicode characters and extra spaces
    name = re.sub(r'[\u202a\u202c\u202b]', '', name)  # Remove directional marks
    name = re.sub(r'\s+', ' ', name)  # Normalize spaces
    name = name.strip()
    
    # Remove trailing dashes or other punctuation
    name = re.sub(r'[-–—]+$', '', name)
    
    return name if name else "Unknown"

def extract_name_from_title(title: str) -> str:
    """Extract person's name from title."""
    if not title:
        return "Unknown"
    
    # Handle Google Scholar profile titles like "‪George Church‬ - ‪Google Scholar‬"
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

def search_for_email(person_name: str, api_key: str, cx_id: str) -> str:
    """Search for person's email using their name + 'email'."""
    if not person_name or person_name == "Unknown":
        return "Not found"
    
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        
        search_queries = [
            f'"{person_name}" email',
            f'"{person_name}" contact email',
            f'"{person_name}" university email',
            f'"{person_name}" faculty email'
        ]
        
        for query in search_queries:
            print(f"  Searching: {query}")
            res = service.cse().list(q=query, cx=cx_id, num=5).execute()
            
            if "items" in res:
                for item in res["items"]:
                    snippet = item.get("snippet", "")
                    title = item.get("title", "")
                    
                    # Look for email pattern in both snippet and title
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', snippet + " " + title)
                    if email_match:
                        found_email = email_match.group(0)
                        print(f"  ✅ Found email: {found_email}")
                        return found_email
        
        print(f"  ❌ No email found after trying {len(search_queries)} search strategies")
        return "Not found"
        
    except Exception as e:
        print(f"  ❌ Email search error for {person_name}: {e}")
        return "Error"

if __name__ == "__main__":
    search_term = "harvard professor citations h-index"
    if len(sys.argv) > 1:
        search_term = " ".join(sys.argv[1:])

    print(f"Searching for '{search_term}' using Google Custom Search API...")
    json_result = search_google_custom_search(search_term, API_KEY, CUSTOM_SEARCH_ENGINE_ID)

    if json_result:
        items = json_result.get("items", [])
        if not items:
            print("No items found in the search results.")
        else:
            print(f"\nAnalyzing {len(items)} results for citations >= 10000 and h-index >= 40...")
            
            qualifying_profiles = []
            
            for i, item in enumerate(items, start=1):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                
                print(f"\nResult {i}: {title}")
                
                # Extract metrics
                metrics = extract_metrics_from_snippet(snippet)
                citations = metrics["citations"]
                h_index = metrics["h_index"]
                
                print(f"Extracted: citations={citations}, h-index={h_index}")
                
                # Check if qualifies
                if citations is not None and h_index is not None:
                    if citations >= 10000 and h_index >= 40:
                        print(f"✅ QUALIFIES!")
                        
                        # Extract and clean name
                        person_name = extract_name_from_title(title)
                        print(f"Name: {person_name}")
                        
                        # Search for email
                        print(f"Searching for email...")
                        email = search_for_email(person_name, API_KEY, CUSTOM_SEARCH_ENGINE_ID)
                        print(f"Email: {email}")
                        
                        profile_data = {
                            "name": person_name,
                            "citations": citations,
                            "h_index": h_index,
                            "email": email,
                            "profile_url": link
                        }
                        
                        qualifying_profiles.append(profile_data)
                        print(f"✅ Added profile")
                    else:
                        print(f"❌ Does not qualify (citations: {citations}, h-index: {h_index})")
                else:
                    print(f"⚠️ Could not extract metrics from snippet")
            
            # Write qualifying profiles to CSV
            if qualifying_profiles:
                output_file = "qualified_profiles.csv"
                try:
                    # Check if file exists to determine if we need to write header
                    file_exists = os.path.exists(output_file)
                    
                    # Read existing profiles to check for duplicates
                    existing_profiles = set()
                    if file_exists:
                        try:
                            with open(output_file, "r", newline="", encoding="utf-8") as f:
                                reader = csv.DictReader(f)
                                for row in reader:
                                    existing_profiles.add(row["name"].lower().strip())
                        except Exception as e:
                            print(f"Warning: Could not read existing CSV: {e}")
                    
                    # Filter out duplicates
                    new_profiles = []
                    for profile in qualifying_profiles:
                        profile_name_lower = profile["name"].lower().strip()
                        if profile_name_lower not in existing_profiles:
                            new_profiles.append(profile)
                            existing_profiles.add(profile_name_lower)
                        else:
                            print(f"⚠️ Skipping duplicate: {profile['name']}")
                    
                    if new_profiles:
                        with open(output_file, "a", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=["name", "citations", "h_index", "email", "profile_url"])
                            
                            # Only write header if file is new
                            if not file_exists:
                                writer.writeheader()
                            
                            writer.writerows(new_profiles)
                        
                        print(f"\n✅ Successfully wrote {len(new_profiles)} new profiles to {output_file}")
                    else:
                        print(f"\nℹ️ All {len(qualifying_profiles)} profiles were duplicates - nothing new to add")
                    
                    # Show summary
                    for profile in qualifying_profiles:
                        print(f"\n{profile['name']}: {profile['citations']} citations, h-index {profile['h_index']}, Email: {profile['email']}")
                        
                except Exception as e:
                    print(f"❌ Error writing CSV: {e}")
            else:
                print("\n❌ No profiles found meeting the criteria (citations >= 10000, h-index >= 40)")
    else:
        print("Failed to retrieve search results.")