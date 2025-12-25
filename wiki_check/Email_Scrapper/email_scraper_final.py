#!/usr/bin/env python3
"""
Email Scraper and Analyzer - Final Version
==========================================

A streamlined tool that takes a URL, scrapes emails, saves to CSV, 
then performs TF-IDF analysis to find the email that matches closest to a given name.

Primary Workflow:
1. Input URL → Scrape emails → Save to CSV
2. Input person name → TF-IDF analysis → Find best match

Features:
- Web scraping with email extraction
- Advanced TF-IDF analysis for name matching
- Pattern matching and similarity scoring
- CSV export with timestamps
- Comprehensive logging and error handling
- Configurable parameters

Author: Email Scraper Tool
Version: 2.0.0
"""

import pandas as pd
import re
import requests
import requests.exceptions
import urllib.parse
from collections import deque, Counter
import sys
import csv
import logging
import argparse
import json
from datetime import datetime
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import os
import glob
import urllib3
import html
import urllib.parse as _urlparse

# Disable SSL warnings for better compatibility
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class EmailScraper:
    """Main email scraper class with comprehensive functionality"""
    
    def __init__(self, config=None):
        """Initialize the email scraper with configuration"""
        self.config = config or self._default_config()
        self.scraped_urls = set()
        self.emails = set()
        self.target_domain = None
        
    def _default_config(self):
        """Default configuration settings"""
        return {
            'max_urls': 50,
            'timeout': 15,  # Increased timeout for better reliability
            # Realistic recent Chrome desktop UA to help avoid 403s
            'user_agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/126.0.0.0 Safari/537.36'
            ),
            'follow_external_links': False,
            'save_results': True,
            'analysis_methods': ['pattern', 'tfidf', 'similarity']
        }

    def _build_request_headers(self) -> dict:
        """Return browser-like headers with the configured Chrome UA."""
        return {
            'User-Agent': self.config.get('user_agent'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def is_valid_url(self, url):
        """Check if URL is valid and has proper scheme"""
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def get_domain(self, url):
        """Extract domain from URL"""
        try:
            return urllib.parse.urlparse(url).netloc
        except:
            return None
    
    def clean_email_for_analysis(self, email):
        """Clean email address for analysis"""
        local_part = email.split('@')[0].lower()
        
        # Remove common email patterns that aren't names
        if re.match(r'^[0-9a-f]{32}$', local_part):  # MD5 hashes
            return ""
        if re.match(r'^[0-9]+$', local_part):  # Pure numbers
            return ""
        if len(local_part) <= 2:  # Very short emails
            return ""
        if re.match(r'^[^a-z]*$', local_part):  # No letters
            return ""
        
        # Replace common separators with spaces
        local_part = re.sub(r'[._-]', ' ', local_part)
        
        return local_part
    def _extract_emails(self, html_text: str, soup: BeautifulSoup = None) -> set:
        """Extract emails from raw HTML and parsed soup with multiple strategies.
        If soup is None, strategies that require it are skipped.
        """
        emails_found = set()
        # 1) Raw regex on original HTML
        raw_regex = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}', html_text)
        emails_found.update(raw_regex)

        # 2) Regex on unescaped HTML (handles &#64; etc.)
        unescaped = html.unescape(html_text)
        unescaped_regex = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}', unescaped)
        emails_found.update(unescaped_regex)

        # 3) Pull text content and run regex
        page_text = ''
        if soup is not None:
            try:
                page_text = soup.get_text(" ", strip=True)
                text_regex = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}', page_text)
                emails_found.update(text_regex)
            except Exception:
                page_text = ''

        # 4) Capture from mailto links
        if soup is not None:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('mailto:'):
                    addr = href[len('mailto:'):]
                    addr = _urlparse.unquote(addr)
                    # mailto can contain multiple addresses separated by , or ;
                    for part in re.split(r'[;,]', addr):
                        part = part.strip()
                        if not part:
                            continue
                        # Remove query params like ?subject=
                        part = part.split('?')[0]
                        if re.match(r'^[^@]+@[^@]+\.[A-Za-z]{2,}$', part):
                            emails_found.add(part)

        # 5) Handle simple obfuscations in text like ' at ' and ' dot '
        def deobfuscate(text: str) -> str:
            replacements = [
                (r'\s*\(at\)\s*', '@'),
                (r'\s*\[at\]\s*', '@'),
                (r'\s+at\s+', '@'),
                (r'\s*\(dot\)\s*', '.'),
                (r'\s*\[dot\]\s*', '.'),
                (r'\s+dot\s+', '.'),
            ]
            t = text
            for pattern, repl in replacements:
                t = re.sub(pattern, repl, t, flags=re.IGNORECASE)
            return t

        for source in (unescaped, page_text or ''):
            candidate_text = deobfuscate(source)
            obf_regex = re.findall(r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\s*\.[A-Za-z]{2,}', candidate_text)
            cleaned = {re.sub(r'\s+', '', e) for e in obf_regex}
            emails_found.update(cleaned)

        return {e.strip() for e in emails_found if len(e) <= 254}
    
    def calculate_name_similarity(self, email_local, target_name):
        """Calculate similarity between email local part and target name"""
        target_words = target_name.lower().split()
        
        # Check for exact matches
        exact_first_name = target_words[0] in email_local
        exact_last_name = target_words[-1] in email_local if len(target_words) > 1 else False
        
        # Check for partial matches (substring)
        partial_first_name = any(target_words[0] in word or word in target_words[0] for word in email_local.split())
        partial_last_name = any(target_words[-1] in word or word in target_words[-1] for word in email_local.split()) if len(target_words) > 1 else False
        
        # Check for initials
        first_initial = email_local.startswith(target_words[0][0])
        last_initial = any(word.startswith(target_words[-1][0]) for word in email_local.split()) if len(target_words) > 1 else False
        
        # Calculate score
        score = 0
        if exact_first_name:
            score += 10
        elif partial_first_name:
            score += 5
        elif first_initial:
            score += 2
            
        if exact_last_name:
            score += 10
        elif partial_last_name:
            score += 5
        elif last_initial:
            score += 2
        
        # Bonus for having both names
        if (exact_first_name or partial_first_name) and (exact_last_name or partial_last_name):
            score += 5
        
        # Bonus for exact full name match
        if all(word in email_local for word in target_words):
            score += 15
        
        return score, {
            'exact_first_name': exact_first_name,
            'exact_last_name': exact_last_name,
            'partial_first_name': partial_first_name,
            'partial_last_name': partial_last_name,
            'first_initial': first_initial,
            'last_initial': last_initial
        }
    
    def scrape_emails(self, start_url):
        """Main email scraping function"""
        logger.info(f"Starting email scraping from: {start_url}")
        
        # Validate URL
        if not self.is_valid_url(start_url):
            logger.error("Invalid URL provided")
            return False
        
        # Initialize variables
        # Reset state for a fresh search (temporary storage behavior)
        self.scraped_urls = set()
        self.emails = set()
        urls = deque([start_url])
        self.target_domain = self.get_domain(start_url)
        
        if not self.target_domain:
            logger.error("Could not extract domain from URL")
            return False
        
        logger.info(f"Target domain: {self.target_domain}")
        logger.info(f"Max URLs to process: {self.config['max_urls']}")
        
        count = 0
        
        try:
            while urls and count < self.config['max_urls']:
                count += 1
                url = urls.popleft()
                
                # Skip if already scraped
                if url in self.scraped_urls:
                    continue
                    
                self.scraped_urls.add(url)
                
                logger.info(f"[{count:3d}] Processing: {url}")
                
                # Parse URL components
                try:
                    parts = urllib.parse.urlsplit(url)
                    base_url = '{0.scheme}://{0.netloc}'.format(parts)
                    path = url[:url.rfind('/')+1] if '/' in parts.path else url
                except Exception as e:
                    logger.error(f"Error parsing URL {url}: {e}")
                    continue
                
                # Make HTTP request with better error handling
                try:
                    response = requests.get(
                        url, 
                        timeout=int(self.config['timeout']), 
                        headers=self._build_request_headers(),
                        allow_redirects=True,
                        verify=False  # Skip SSL verification for problematic sites
                    )
                    response.raise_for_status()
                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout fetching {url} (timeout: {self.config['timeout']}s)")
                    continue
                except requests.exceptions.ConnectionError:
                    logger.warning(f"Connection error fetching {url}")
                    continue
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Failed to fetch {url}: {e}")
                    continue
                
                # Parse HTML first
                try:
                    soup = BeautifulSoup(response.text, features="lxml")
                except Exception as e:
                    logger.error(f"Error parsing HTML for {url}: {e}")
                    soup = None

                # Extract emails from response using robust extractor
                new_emails = self._extract_emails(response.text, soup)
                self.emails.update(new_emails)
                if new_emails:
                    logger.info(f"Found {len(new_emails)} new emails")
                
                # Find and process links
                if soup is None:
                    continue
                for anchor in soup.find_all("a"):
                    link = anchor.attrs.get('href', '')
                    if not link:
                        continue
                    
                    # Convert relative URLs to absolute
                    if link.startswith('/'):
                        link = base_url + link
                    elif not link.startswith('http'):
                        link = urllib.parse.urljoin(path, link)
                    
                    # Validate the link
                    if not self.is_valid_url(link):
                        continue
                    
                    # Check domain restrictions
                    link_domain = self.get_domain(link)
                    if not self.config['follow_external_links'] and link_domain != self.target_domain:
                        continue
                    
                    # Add to queue if not already processed
                    if link not in urls and link not in self.scraped_urls:
                        urls.append(link)
                        
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}")
            # Don't return False for unexpected errors, still try to save what we found
        
        logger.info(f"Scraping completed. Processed {count} URLs, found {len(self.emails)} emails")
        
        # Return True if we found any emails or processed any URLs successfully
        return len(self.emails) > 0 or count > 0
    
    def save_emails_to_csv(self):
        """Save found emails to a CSV file"""
        if not self.emails:
            logger.warning("No emails to save")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"emails_{self.target_domain}_{timestamp}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Email Address', 'Domain', 'Date Found'])
                
                for email in sorted(self.emails):
                    writer.writerow([email, self.target_domain, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            
            logger.info(f"Emails saved to: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return None
    
    def analyze_emails_for_person(self, csv_file, target_person_name):
        """Backwards-compatible analysis from a CSV file (legacy)."""
        try:
            df = pd.read_csv(csv_file)
            emails = df['Email Address'].tolist()
            logger.info(f"Loaded {len(emails)} emails from {csv_file}")
            return self.analyze_emails_list_for_person(emails, target_person_name)
        except Exception as e:
            logger.error(f"Error during CSV email analysis: {e}")
            return None

    def analyze_emails_list_for_person(self, emails, target_person_name):
        """Analyze a provided list of emails to find a specific person's email."""
        logger.info(f"Analyzing emails for: {target_person_name}")
        try:
            target_name = target_person_name.lower()
            # Method 1: Pattern-based analysis
            pattern_results = self._pattern_analysis(emails, target_name)
            # Method 2: TF-IDF analysis
            tfidf_results = self._tfidf_analysis(emails, target_name)
            # Method 3: Similarity analysis
            similarity_results = self._similarity_analysis(emails, target_name)
            # Combine results
            final_results = self._combine_analysis_results(
                pattern_results, tfidf_results, similarity_results, target_person_name
            )
            return final_results
        except Exception as e:
            logger.error(f"Error during list-based email analysis: {e}")
            return None

    def analyze_current_emails_for_person(self, target_person_name):
        """Analyze the currently scraped emails stored in memory (temporary list)."""
        emails_list = sorted(self.emails)
        return self.analyze_emails_list_for_person(emails_list, target_person_name)
    
    def _pattern_analysis(self, emails, target_name):
        """Pattern-based email analysis"""
        results = []
        
        for email in emails:
            cleaned = self.clean_email_for_analysis(email)
            if not cleaned:
                continue
                
            score, details = self.calculate_name_similarity(cleaned, target_name)
            
            results.append({
                'Email': email,
                'Cleaned': cleaned,
                'Score': score,
                'Details': details,
                'Method': 'Pattern'
            })
        
        return sorted(results, key=lambda x: x['Score'], reverse=True)
    
    def _tfidf_analysis(self, emails, target_name):
        """TF-IDF based email analysis"""
        try:
            # Clean emails for analysis
            cleaned_emails = []
            valid_emails = []
            
            for email in emails:
                cleaned = self.clean_email_for_analysis(email)
                if cleaned:
                    cleaned_emails.append(cleaned)
                    valid_emails.append(email)
            
            if not cleaned_emails:
                return []
            
            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(
                analyzer='word',
                ngram_range=(1, 2),
                min_df=1,
                max_df=0.9,
                stop_words=None
            )
            
            # Add target name to the corpus
            corpus = cleaned_emails + [target_name]
            
            # Fit and transform
            tfidf_matrix = vectorizer.fit_transform(corpus)
            
            # Calculate similarity
            target_vector = tfidf_matrix[-1]
            similarities = cosine_similarity(target_vector, tfidf_matrix[:-1]).flatten()
            
            # Create results
            results = []
            for i, (email, similarity) in enumerate(zip(valid_emails, similarities)):
                results.append({
                    'Email': email,
                    'Cleaned': cleaned_emails[i],
                    'Score': similarity * 100,  # Convert to 0-100 scale
                    'Details': {'tfidf_similarity': similarity},
                    'Method': 'TF-IDF'
                })
            
            return sorted(results, key=lambda x: x['Score'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error in TF-IDF analysis: {e}")
            return []
    
    def _similarity_analysis(self, emails, target_name):
        """Advanced similarity analysis"""
        results = []
        target_words = target_name.split()
        
        for email in emails:
            local_part = email.split('@')[0].lower()
            
            # Calculate various similarity metrics
            score = 0
            details = {}
            
            # Check for name components
            for word in target_words:
                if word in local_part:
                    score += 10
                    details[f'contains_{word}'] = True
                elif word[0] in local_part:
                    score += 3
                    details[f'initial_{word[0]}'] = True
            
            # Check for common patterns
            if any(word in local_part for word in target_words):
                score += 5
                details['has_name_component'] = True
            
            if score > 0:
                results.append({
                    'Email': email,
                    'Cleaned': local_part,
                    'Score': score,
                    'Details': details,
                    'Method': 'Similarity'
                })
        
        return sorted(results, key=lambda x: x['Score'], reverse=True)
    
    def _combine_analysis_results(self, pattern_results, tfidf_results, similarity_results, target_person):
        """Combine results from all analysis methods"""
        print("\n" + "="*80)
        print(f"🔍 COMPREHENSIVE EMAIL ANALYSIS FOR {target_person.upper()}")
        print("="*80)
        
        # Display results from each method
        print("\n[+] PATTERN-BASED ANALYSIS (Top 5):")
        print("-" * 60)
        for i, result in enumerate(pattern_results[:5], 1):
            print(f"{i}. {result['Email']:<35} | Score: {result['Score']:2d}")
            if result['Score'] > 0:
                print(f"   Details: {result['Details']}")
        
        print("\n[+] TF-IDF ANALYSIS (Top 5):")
        print("-" * 60)
        for i, result in enumerate(tfidf_results[:5], 1):
            print(f"{i}. {result['Email']:<35} | Score: {result['Score']:.1f}")
        
        print("\n[+] SIMILARITY ANALYSIS (Top 5):")
        print("-" * 60)
        for i, result in enumerate(similarity_results[:5], 1):
            print(f"{i}. {result['Email']:<35} | Score: {result['Score']:2d}")
        
        # Find best overall match
        all_results = pattern_results + tfidf_results + similarity_results
        if not all_results:
            print("\n❌ No suitable candidates found.")
            return None
        
        # Simple scoring system to find best match
        email_scores = {}
        for result in all_results:
            email = result['Email']
            if email not in email_scores:
                email_scores[email] = 0
            email_scores[email] += result['Score']
        
        # Get best match
        best_email = max(email_scores.items(), key=lambda x: x[1])
        
        print("\n" + "="*80)
        print("🎯 FINAL RECOMMENDATION")
        print("="*80)
        print(f"📧 MOST LIKELY EMAIL: {best_email[0]}")
        print(f"📊 Combined Score: {best_email[1]:.1f}")
        print(f"✅ CONCLUSION: This is most likely {target_person}'s email address.")
        
        return best_email[0]

def main():
    """Main function with streamlined workflow"""
    parser = argparse.ArgumentParser(description='Email Scraper and Analyzer - URL to Email Finder')
    parser.add_argument('--url', '-u', help='Target URL to scrape (primary mode)')
    parser.add_argument('--person', '-p', help='Person name to find email for (optional, will prompt if not provided)')
    parser.add_argument('--csv', '-c', help='CSV file to analyze (analysis-only mode)')
    parser.add_argument('--max-urls', type=int, default=20, help='Maximum URLs to scrape')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--no-analysis', action='store_true', help='Skip analysis after scraping')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration - start with defaults
    scraper_temp = EmailScraper()  # Get default config
    config = scraper_temp.config.copy()
    
    # Load from file if provided
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            file_config = json.load(f)
            config.update(file_config)  # Merge with defaults
    
    # Override with command line arguments
    if args.max_urls:
        config['max_urls'] = args.max_urls
    
    # Initialize scraper
    scraper = EmailScraper(config)
    
    # Determine mode
    if args.csv:
        # Analysis-only mode
        if not args.person:
            print("Error: Person name required for analysis mode")
            return
        
        result = scraper.analyze_emails_for_person(args.csv, args.person)
        if result:
            print(f"\n🎉 SUCCESS: {args.person}'s email is likely {result}")
        
    elif args.url:
        # Primary mode: URL scraping with optional analysis (in-memory list)
        print("🚀 Email Scraper and Analyzer")
        print("=" * 50)
        print(f"📡 Target URL: {args.url}")
        print(f"🔍 Max URLs to scan: {config['max_urls']}")
        print("-" * 50)
        
        if scraper.scrape_emails(args.url):
            # Display results
            print(f"\n✅ Scraping completed!")
            print(f"📊 URLs processed: {len(scraper.scraped_urls)}")
            print(f"📧 Emails found: {len(scraper.emails)}")
            
            if scraper.emails:
                print(f"\n📋 Found emails:")
                for i, email in enumerate(sorted(scraper.emails), 1):
                    print(f"{i:2d}. {email}")
                
                # Ask for person name if not provided and analysis not disabled
                if not args.no_analysis:
                    if args.person:
                        person_name = args.person
                        print(f"\n🔍 Analyzing for: {person_name}")
                    else:
                        person_name = input(f"\n👤 Enter person name to find email for (or press Enter to skip): ").strip()
                    
                    if person_name:
                        print(f"\n🧠 Performing TF-IDF analysis...")
                        result = scraper.analyze_current_emails_for_person(person_name)
                        if result:
                            print(f"\n🎉 SUCCESS: {person_name}'s email is likely {result}")
                    elif not person_name:
                        print(f"\n⏭️  Analysis skipped.")
                else:
                    print(f"\n⏭️  Analysis disabled.")
            else:
                print("\n❌ No emails found on the target website")
        else:
            print("❌ Scraping failed")
    
    else:
        # Interactive mode - streamlined workflow
        print("🚀 Email Scraper and Analyzer - Interactive Mode")
        print("=" * 60)
        
        # Get target URL
        url = input("🌐 Enter target URL to scrape: ").strip()
        if not url:
            print("❌ No URL provided")
            return
        
        print(f"\n📡 Starting email extraction from: {url}")
        print("-" * 60)
        
        # Scrape emails (in-memory list)
        if scraper.scrape_emails(url):
            print(f"\n✅ Scraping completed!")
            print(f"📊 URLs processed: {len(scraper.scraped_urls)}")
            print(f"📧 Emails found: {len(scraper.emails)}")
            
            if scraper.emails:
                print(f"\n📋 Found emails:")
                for i, email in enumerate(sorted(scraper.emails), 1):
                    print(f"{i:2d}. {email}")
                
                # Ask for person name for analysis
                person_name = input(f"\n👤 Enter person name to find email for (or press Enter to skip): ").strip()
                if person_name:
                    print(f"\n🧠 Performing TF-IDF analysis for: {person_name}")
                    result = scraper.analyze_current_emails_for_person(person_name)
                    if result:
                        print(f"\n🎉 SUCCESS: {person_name}'s email is likely {result}")
                elif not person_name:
                    print(f"\n⏭️  Analysis skipped.")
            else:
                print("\n❌ No emails found on the target website")
        else:
            print("❌ Scraping failed")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[-] Operation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"[-] Error: {e}")

