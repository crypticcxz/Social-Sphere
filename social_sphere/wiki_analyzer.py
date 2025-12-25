import os
import csv
import re
import time
import requests
import argparse
from typing import Dict, List, Optional
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WIKI_MAILTO = os.getenv("WIKI_MAILTO", "your-email@example.com")
WIKI_DELAY_MS = int(os.getenv("WIKI_DELAY_MS", "200"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

# Set OpenAI API key
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

class WikipediaAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"WikiAnalyzer/1.0 (mailto:{WIKI_MAILTO})",
            "Accept": "application/json",
        })
    
    def search_wikipedia_by_title(self, title: str) -> Optional[str]:
        """
        Search for a Wikipedia page by title using MediaWiki API.
        Returns the actual page title if found, None otherwise.
        """
        try:
            # First try exact match
            params = {
                "action": "query",
                "format": "json",
                "titles": title,
                "utf8": 1,
            }
            
            response = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                pages = data.get("query", {}).get("pages", {})
                
                # Check if we found a page (not -1 which means "missing")
                for page_id, page_data in pages.items():
                    if page_id != "-1" and "title" in page_data:
                        return page_data["title"]
            
            # If exact match failed, try search
            search_params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": f'"{title}"',
                "srnamespace": "0",
                "srlimit": "5",
                "utf8": 1,
            }
            
            search_response = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params=search_params,
                timeout=REQUEST_TIMEOUT
            )
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                search_results = search_data.get("query", {}).get("search", [])
                
                # Return the first result if any
                if search_results:
                    return search_results[0]["title"]
            
            return None
            
        except Exception as e:
            print(f"Error searching for Wikipedia page '{title}': {e}")
            return None
    
    def fetch_wikipedia_content(self, wikipedia_url_or_title: str) -> Optional[Dict[str, str]]:
        """
        Fetch Wikipedia page content including wikitext and parsed content.
        Returns dict with 'wikitext', 'parsed_content', and 'warnings'.
        
        Args:
            wikipedia_url_or_title: Either a full Wikipedia URL or just a page title
        """
        if not wikipedia_url_or_title:
            return None
        
        # Check if it's a URL or just a title
        if "wikipedia.org" in wikipedia_url_or_title:
            # It's a URL, extract the title
            title_match = re.search(r"/wiki/([^?#]+)", wikipedia_url_or_title)
            if not title_match:
                return None
            title = title_match.group(1).replace("_", " ")
        else:
            # It's just a title, clean it up
            title = wikipedia_url_or_title.strip()
            # Remove common suffixes like " - Wikipedia"
            title = re.sub(r'\s*-\s*Wikipedia\s*$', '', title, flags=re.IGNORECASE)
            title = title.strip()
            
            # Search for the actual Wikipedia page title
            actual_title = self.search_wikipedia_by_title(title)
            if not actual_title:
                print(f"Could not find Wikipedia page for: {title}")
                return None
            title = actual_title
        
        try:
            
            # Fetch wikitext content
            params = {
                "action": "query",
                "format": "json",
                "prop": "revisions|wikitext|pageprops",
                "titles": title,
                "rvprop": "content",
                "rvslots": "main",
                "utf8": 1,
            }
            
            response = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params=params,
                timeout=REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            pages = data.get("query", {}).get("pages", {})
            
            if not pages:
                return None
            
            page_data = list(pages.values())[0]
            
            # Get wikitext content
            wikitext = ""
            if "revisions" in page_data:
                wikitext = page_data["revisions"][0].get("slots", {}).get("main", {}).get("*", "")
            
            # Get parsed content (HTML)
            parsed_params = {
                "action": "parse",
                "format": "json",
                "page": title,
                "prop": "text|sections",
                "utf8": 1,
            }
            
            parsed_response = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params=parsed_params,
                timeout=REQUEST_TIMEOUT
            )
            
            parsed_content = ""
            sections = []
            if parsed_response.status_code == 200:
                parsed_data = parsed_response.json()
                parsed_content = parsed_data.get("parse", {}).get("text", {}).get("*", "")
                sections = parsed_data.get("parse", {}).get("sections", [])
            
            # Extract warnings/tags from wikitext
            warnings = self.extract_warnings(wikitext)
            
            # Rate limiting
            time.sleep(WIKI_DELAY_MS / 1000.0)
            
            return {
                "wikitext": wikitext,
                "parsed_content": parsed_content,
                "sections": sections,
                "warnings": warnings,
                "title": title
            }
            
        except Exception as e:
            print(f"Error fetching Wikipedia content: {e}")
            return None
    
    def extract_warnings(self, wikitext: str) -> List[str]:
        """Extract warning templates and tags from wikitext."""
        warnings = []
        
        # Common warning templates
        warning_patterns = [
            r'\{\{[^}]*notability[^}]*\}\}',
            r'\{\{[^}]*advert[^}]*\}\}',
            r'\{\{[^}]*refimprove[^}]*\}\}',
            r'\{\{[^}]*cleanup[^}]*\}\}',
            r'\{\{[^}]*unreferenced[^}]*\}\}',
            r'\{\{[^}]*primarysources[^}]*\}\}',
            r'\{\{[^}]*originalresearch[^}]*\}\}',
            r'\{\{[^}]*peacock[^}]*\}\}',
            r'\{\{[^}]*weasel[^}]*\}\}',
            r'\{\{[^}]*inappropriate[^}]*\}\}',
            r'\{\{[^}]*disputed[^}]*\}\}',
            r'\{\{[^}]*npov[^}]*\}\}',
            r'\{\{[^}]*merge[^}]*\}\}',
            r'\{\{[^}]*delete[^}]*\}\}',
            r'\{\{[^}]*redirect[^}]*\}\}',
            r'\{\{[^}]*stub[^}]*\}\}',
            r'\{\{[^}]*outdated[^}]*\}\}',
            r'\{\{[^}]*update[^}]*\}\}',
            r'\{\{[^}]*citation[^}]*\}\}',
            r'\{\{[^}]*verify[^}]*\}\}',
            r'\{\{[^}]*reliable[^}]*\}\}',
            r'\{\{[^}]*independence[^}]*\}\}',
            r'\{\{[^}]*bias[^}]*\}\}',
            r'\{\{[^}]*unbalanced[^}]*\}\}',
            r'\{\{[^}]*reorganize[^}]*\}\}',
            r'\{\{[^}]*layout[^}]*\}\}',
            r'\{\{[^}]*wordiness[^}]*\}\}',
            r'\{\{[^}]*factual[^}]*\}\}',
        ]
        
        for pattern in warning_patterns:
            matches = re.findall(pattern, wikitext, re.IGNORECASE)
            for match in matches:
                # Clean up the template
                clean_match = re.sub(r'\{\{|\}\}', '', match)
                clean_match = re.sub(r'\|.*', '', clean_match)
                if clean_match and clean_match not in warnings:
                    warnings.append(clean_match.strip())
        
        return warnings
    
    def analyze_with_openai(self, name: str, content_data: Dict[str, str]) -> Dict[str, str]:
        """
        Analyze Wikipedia content using OpenAI API.
        Returns analysis with summary and missing sections.
        """
        if not content_data:
            return {
                "summary": "Could not fetch Wikipedia content",
                "missing_sections": "Unable to analyze",
                "warnings": "Unable to fetch page",
                "overall_assessment": "Error fetching content"
            }
        
        wikitext = content_data.get("wikitext", "")
        warnings = content_data.get("warnings", [])
        
        # Create prompt for OpenAI
        prompt = f"""
Analyze the following Wikipedia page for {name} and provide a structured assessment.

Required sections to check for:
1. Introduction Paragraph
2. Early Life & Education section
3. Career Section
4. Research Section
5. Awards & Honors Section
6. Selected Publications section
7. Books (if available)
8. References
9. InfoBox with photo & basic info

Wikipedia content (first 8000 characters):
{wikitext[:8000]}

Please provide your analysis in the following format:

SUMMARY: [Provide a 2-3 sentence summary of this person in plain text - NO Wikipedia markup, citations, or templates]

MISSING_SECTIONS: [List any missing sections from the required list above, or write "All sections present" if none are missing]

WARNINGS: [List any Wikipedia warning templates found, or write "No warnings detected" if none found]

OVERALL_ASSESSMENT: [If all sections are present AND no warnings detected, write "Perfect profile - no improvements possible". Otherwise, provide specific recommendations for improvement]

CRITICAL FORMATTING RULES:
- Do not use commas or semicolons in your responses as this will break CSV formatting
- Use "and" to connect items in lists
- Write in plain text only - NO Wikipedia markup like [[links]], {{templates}}, or citation patterns
- Do not include any technical Wikipedia formatting or markup
- Keep responses clean and readable for AI processing
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert Wikipedia analyst. Analyze the provided content and give structured feedback. CRITICAL: Write in plain text only - NO Wikipedia markup, citations, templates, or formatting. Never use commas or semicolons in your responses as this will break CSV formatting. Use 'and' to connect items in lists. Your output will be processed by another AI system, so keep it clean and readable."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            analysis_text = response.choices[0].message.content
            
            # Parse the structured response
            result = self.parse_analysis_response(analysis_text)
            
            # Add warnings from wikitext extraction
            if warnings:
                existing_warnings = result.get("warnings", "")
                if existing_warnings and existing_warnings != "No warnings detected":
                    result["warnings"] = f"{existing_warnings}; Additional templates: {', '.join(warnings)}"
                else:
                    result["warnings"] = f"Wikipedia templates detected: {', '.join(warnings)}"
            
            return result
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return {
                "summary": "Error analyzing with OpenAI",
                "missing_sections": "API error",
                "warnings": f"Wikipedia templates: {', '.join(warnings)}" if warnings else "No warnings detected",
                "overall_assessment": "API analysis failed"
            }
    
    def parse_analysis_response(self, text: str) -> Dict[str, str]:
        """Parse the structured OpenAI response."""
        result = {
            "summary": "",
            "missing_sections": "",
            "warnings": "",
            "overall_assessment": ""
        }
        
        # Split by sections
        sections = text.split('\n')
        current_section = None
        
        for line in sections:
            line = line.strip()
            if line.startswith('SUMMARY:'):
                result["summary"] = line.replace('SUMMARY:', '').strip()
            elif line.startswith('MISSING_SECTIONS:'):
                result["missing_sections"] = line.replace('MISSING_SECTIONS:', '').strip()
            elif line.startswith('WARNINGS:'):
                result["warnings"] = line.replace('WARNINGS:', '').strip()
            elif line.startswith('OVERALL_ASSESSMENT:'):
                result["overall_assessment"] = line.replace('OVERALL_ASSESSMENT:', '').strip()
        
        return result

def process_full_name_csv(input_csv: str, output_csv: str, max_entries: Optional[int] = None, force: bool = False):
    """Process the full_name.csv file and add analysis results.
    
    Args:
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file
        max_entries: Maximum number of entries to process (None for all)
    """
    analyzer = WikipediaAnalyzer()
    
    # Read the input CSV
    rows = []
    with open(input_csv, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        rows = list(reader)
    
    # Check if output file exists and load existing processed entries
    existing_processed = set()
    if os.path.exists(output_csv) and not force:
        print(f"📁 Found existing output file: {output_csv}")
        try:
            with open(output_csv, 'r', encoding='utf-8') as file:
                existing_reader = csv.DictReader(file)
                for row in existing_reader:
                    # Create a unique key based on name and email
                    key = f"{row.get('Name', '')}|{row.get('email', '')}"
                    existing_processed.add(key)
            print(f"✅ Found {len(existing_processed)} already processed entries")
        except Exception as e:
            print(f"⚠️ Could not read existing file: {e}")
            existing_processed = set()
    
    # Filter out already processed entries
    rows_to_process = []
    skipped_count = 0
    
    for row in rows:
        key = f"{row.get('Name', '')}|{row.get('email', '')}"
        if key in existing_processed:
            skipped_count += 1
        else:
            rows_to_process.append(row)
    
    if skipped_count > 0:
        print(f"⏭️ Skipping {skipped_count} already processed entries")
    
    # Limit entries if specified (only applies to unprocessed entries)
    original_count = len(rows_to_process)
    if max_entries and max_entries < len(rows_to_process):
        rows_to_process = rows_to_process[:max_entries]
        print(f"Processing {len(rows_to_process)} entries (limited from {original_count} unprocessed) from {input_csv}...")
    else:
        print(f"Processing {len(rows_to_process)} entries from {input_csv}...")
    
    if len(rows_to_process) == 0:
        print("✅ All entries have already been processed!")
        return
    
    # Load existing data if file exists
    existing_data = []
    if os.path.exists(output_csv) and not force:
        try:
            with open(output_csv, 'r', encoding='utf-8') as file:
                existing_reader = csv.DictReader(file)
                existing_data = list(existing_reader)
        except Exception as e:
            print(f"⚠️ Could not load existing data: {e}")
            existing_data = []
    
    # Clean text function (defined once to avoid repetition)
    def clean_for_csv(text):
        if not text:
            return ""
        
        text = str(text)
        
        # Remove Wikipedia markup
        text = re.sub(r'\[\[([^|\]]+)(\|[^\]]+)?\]\]', r'\1', text)  # [[Link|Display]] -> Display
        text = re.sub(r'\{\{[^}]*\}\}', '', text)  # Remove all templates {{...}}
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
        text = re.sub(r'==+[^=]+==+', '', text)  # Remove section headers
        text = re.sub(r'\*+', '', text)  # Remove bullet points
        text = re.sub(r'#+', '', text)  # Remove numbered lists
        text = re.sub(r'\|+', ' ', text)  # Remove table separators
        text = re.sub(r'^[\s\-\*#\|]+', '', text, flags=re.MULTILINE)  # Remove leading formatting chars
        
        # Clean up citation patterns
        text = re.sub(r'cite journal|Cite journal|cite book|Cite book|cite web|Cite web', '', text, flags=re.IGNORECASE)
        text = re.sub(r'and cite journal and Cite book and Cite book and Cite web and Cite web and Cite web and Cite web and Cite journal and Cite book and Cite book', '', text)
        
        # Replace commas and semicolons with safe alternatives
        text = text.replace(",", " and")
        text = text.replace(";", " and")
        
        # Clean up extra spaces and normalize
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    # Process each row and write immediately
    processed_count = 0
    for i, row in enumerate(rows_to_process, 1):
        name = row.get('Name', '')
        wikipedia_url = row.get('wikipedia_url', '')
        
        print(f"Processing {i}/{len(rows_to_process)}: {name}")
        
        if not wikipedia_url or wikipedia_url == 'N/A':
            # No Wikipedia URL available
            row['info'] = "No Wikipedia page available"
            row['is_wiki'] = '0'  # No Wikipedia page
        else:
            # Fetch and analyze Wikipedia content
            print(f"  Fetching content for: {wikipedia_url}")
            content_data = analyzer.fetch_wikipedia_content(wikipedia_url)
            
            if not content_data:
                print(f"  ❌ Failed to fetch content for: {wikipedia_url}")
                row['info'] = "Could not fetch Wikipedia content"
                row['is_wiki'] = '0'  # Failed to fetch
            else:
                print(f"  ✅ Successfully fetched content, analyzing...")
                analysis = analyzer.analyze_with_openai(name, content_data)
                
                # Combine analysis into a single string for the CSV
                analysis_text = f"SUMMARY: {clean_for_csv(analysis['summary'])} | MISSING: {clean_for_csv(analysis['missing_sections'])} | WARNINGS: {clean_for_csv(analysis['warnings'])} | ASSESSMENT: {clean_for_csv(analysis['overall_assessment'])}"
                row['info'] = analysis_text
                row['is_wiki'] = '1'  # Successfully analyzed Wikipedia page
        
        # Write this row immediately to the CSV
        try:
            # Check if file exists to determine if we need to write header
            file_exists = os.path.exists(output_csv)
            
            with open(output_csv, 'a', newline='', encoding='utf-8') as file:
                fieldnames = list(row.keys())
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                
                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(row)
            
            processed_count += 1
            print(f"  ✅ Saved to CSV ({processed_count} processed so far)")
            
        except Exception as e:
            print(f"  ❌ Error writing to CSV: {e}")
            continue
        
        # Add delay between requests to be respectful
        time.sleep(1)
    
    print(f"\n🎉 Analysis completed!")
    print(f"📊 Total entries processed: {processed_count}")
    print(f"📁 Results saved to: {output_csv}")

def main():
    """Main function to run the Wikipedia analysis."""
    parser = argparse.ArgumentParser(description="Analyze Wikipedia pages for scholar profiles")
    parser.add_argument(
        "--input", 
        default="full_name.csv", 
        help="Input CSV file path (default: full_name.csv)"
    )
    parser.add_argument(
        "--output", 
        default="full_name_with_analysis.csv", 
        help="Output CSV file path (default: full_name_with_analysis.csv)"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        help="Limit number of entries to process (useful for testing)"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force reprocessing of all entries (ignore existing results)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found in current directory")
        return
    
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not found in environment variables")
        return
    
    if args.force:
        print("🔄 Running in FORCE MODE - reprocessing all entries (ignoring existing results)")
    elif args.limit:
        print(f"🚀 Running in TEST MODE - processing only {args.limit} entries")
        print("💡 To process all entries, run without --limit argument")
    else:
        print(f"🚀 Running in SMART MODE - processing only new entries")
    
    process_full_name_csv(args.input, args.output, args.limit, args.force)

if __name__ == "__main__":
    main()
