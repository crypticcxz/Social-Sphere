# Academic Profile Scraper

A comprehensive Python script that scrapes academic profiles from Google Scholar, extracts contact information, finds Wikipedia pages, and generates AI-powered summaries.

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file with your API keys:
   ```env
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_SCHOLAR_CSE_ID=your_scholar_cse_id
   GOOGLE_GENERAL_CSE_ID=your_general_cse_id
   OPENAI_API_KEY=your_openai_api_key
   ```

3. **Run the script:**
   ```bash
   python wiki.py
   ```

## 📁 Project Structure

```
wiki_check/
├── wiki.py                                    # Main scraper script
├── Email Scrapper/
│   └── email_scraper_final.py                # Email extraction module
├── queries.txt                               # Search queries and affiliations
├── requirements.txt                          # Python dependencies
├── .env                                      # API keys and configuration
├── qualified_scholar_profiles_with_wikipedia.csv    # Output: Profiles with Wikipedia + email
├── qualified_scholar_profiles_without_wikipedia.csv # Output: Profiles without Wikipedia + email
└── without_email.csv                         # Output: Profiles without email
```

## 🔧 How wiki.py Works

### 1. **Search Strategy**
- Uses Google Custom Search Engine (CSE) to search Google Scholar
- Supports pagination for bulk results (configurable via `CSE_MAX_PAGES`)
- Rotates through search queries from `queries.txt` file
- Applies affiliation filtering to target specific institutions

### 2. **Profile Processing Pipeline**

#### **Step 1: Initial Search**
```python
# Searches Google Scholar with terms like:
# "Harvard professor" "cited by" "h-index"
search_google_custom_search(scholar_search_term, API_KEY, SCHOLAR_CSE_ID)
```

#### **Step 2: Metrics Extraction**
- **From snippets**: Extracts citations and h-index from search result snippets
- **From profile pages**: Fetches full profile data if metrics are incomplete
- **Targeted CSE refetch**: Uses specific queries to get missing metrics
- **OpenAlex fallback**: Free API backup for missing data

#### **Step 3: Qualification Filtering**
```python
# Profiles must meet these criteria:
citations >= MIN_CITATIONS_THRESHOLD (default: 10000)
h_index >= MIN_H_INDEX_THRESHOLD (default: 40)  # Optional if REQUIRE_H_INDEX=false
```

#### **Step 4: Data Enrichment**

**Homepage Discovery:**
- Extracts homepage URL from Google Scholar profile
- Falls back to Wikipedia Wikidata (P856 property)
- Uses Wikipedia external links as backup
- Performs targeted CSE search if needed

**Wikipedia Page Finding:**
- Uses MediaWiki API (free) instead of Google CSE
- Handles disambiguation pages intelligently
- Supports name variations and aliases
- Caches results to avoid duplicate API calls

**Email Extraction:**
- Scrapes emails from homepage using `EmailScraper`
- Validates emails with strict regex patterns
- Filters out invalid formats (PDFs, images, etc.)
- Falls back to Wikipedia external links if homepage fails

#### **Step 5: Summary Generation**
Uses a fallback chain to generate AI-powered summaries:

1. **Wikipedia extract** → GPT-4o-mini summary (3-6 sentences)
2. **Homepage text** → GPT-4o-mini summary (1-2 sentences)
3. **Wikipedia external links** → Homepage text → GPT summary
4. **Heuristic summary** → Rule-based fallback (1-2 sentences)

### 3. **Output Organization**

The script creates three CSV files based on email availability:

#### **qualified_scholar_profiles_with_wikipedia.csv**
- Profiles with both email AND Wikipedia page
- Schema: `Name, email, wikipedia_url, info, is_wiki`
- `is_wiki = "1"`

#### **qualified_scholar_profiles_without_wikipedia.csv**
- Profiles with email but NO Wikipedia page
- Schema: `Name, email, wikipedia_url, info, is_wiki`
- `is_wiki = "0"`

#### **without_email.csv**
- Profiles without valid email (regardless of Wikipedia status)
- Schema: `Name, email, wikipedia_url, info, is_wiki`
- `email = "Not found"`

### 4. **Deduplication Logic**

Prevents duplicate entries using intelligent keys:
- **Primary key**: `(name, wikipedia_url)` if Wikipedia URL exists
- **Fallback key**: `(name, email)` if no Wikipedia URL
- **Case-insensitive** name matching
- **Unicode cleaning** for consistent comparison

## ⚙️ Configuration Options

### Environment Variables (.env)

```env
# Required API Keys
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SCHOLAR_CSE_ID=your_scholar_cse_id
GOOGLE_GENERAL_CSE_ID=your_general_cse_id
OPENAI_API_KEY=your_openai_api_key

# Search Configuration
SEARCH_TERM=harvard university professor "cited by" "h-index"
MIN_CITATIONS_THRESHOLD=10000
MIN_H_INDEX_THRESHOLD=40
REQUIRE_H_INDEX=false

# Pagination
CSE_NUM_PER_PAGE=10
CSE_MAX_PAGES=3
START_PAGE=1

# Affiliation Filtering
AFFILIATION_FILTER=harvard,stanford,mit

# Query Rotation
QUERY_LIST_PATH=queries.txt

# Wikipedia API
WIKI_MAILTO=your_email@example.com
WIKI_DELAY_MS=120

# Profile Fetching
PROFILE_FETCH_MODE=auto  # auto, html, jina, none
DEBUG_FETCH=false
```

### Query File Format (queries.txt)

Each line contains a search query and optional affiliation filters:
```
Harvard professor "cited by" "h-index" || harvard,harvard.edu
Stanford professor "cited by" "h-index" || stanford,stanford.edu
MIT professor "cited by" "h-index" || mit,mit.edu
```

## 🔍 Key Functions Explained

### **Search Functions**
- `search_google_custom_search()` - Main CSE search
- `extract_metrics_from_item()` - Extract citations/h-index from snippets
- `fetch_profile_metrics()` - Get full profile data from Scholar page

### **Wikipedia Functions**
- `fetch_wikipedia_via_mediawiki()` - Find Wikipedia pages using MediaWiki API
- `fetch_wikipedia_extract()` - Get Wikipedia page content
- `is_likely_match()` - Intelligent name matching for Wikipedia pages

### **Email Functions**
- `find_email_for_person()` - Main email discovery function
- `EmailScraper` - Custom email extraction from web pages
- `is_valid_email()` - Strict email validation

### **Summary Functions**
- `summarize_with_gpt()` - AI-powered summary generation
- `_heuristic_summary()` - Rule-based fallback summary
- `fetch_homepage_text()` - Extract text from web pages

### **Utility Functions**
- `clean_unicode_text()` - Remove problematic Unicode characters
- `extract_name_from_title()` - Clean names from Scholar titles
- `is_valid_homepage_url()` - Validate homepage URLs

## 📊 Output Schema

All CSV files use the same schema:

| Column | Description | Example |
|--------|-------------|---------|
| `Name` | Professor's full name | "George Church" |
| `email` | Contact email address | "church@harvard.edu" |
| `wikipedia_url` | Wikipedia page URL | "https://en.wikipedia.org/wiki/George_Church" |
| `info` | AI-generated summary | "George Church is a geneticist..." |
| `is_wiki` | Wikipedia flag (1/0) | "1" |

## 🚨 Error Handling

- **API Rate Limits**: Built-in delays and retry logic
- **Network Timeouts**: Graceful fallbacks for failed requests
- **Invalid Data**: Strict validation and cleaning
- **Duplicate Prevention**: Intelligent deduplication system
- **Unicode Issues**: Comprehensive text cleaning

## 🔧 Troubleshooting

### Common Issues

1. **"No profiles found"**
   - Check your Scholar CSE configuration
   - Verify API keys are correct
   - Try lowering citation thresholds

2. **Email extraction fails**
   - Ensure `Email Scrapper` folder is present
   - Check if homepages are accessible
   - Verify email validation regex

3. **Wikipedia pages not found**
   - Check MediaWiki API connectivity
   - Verify name matching logic
   - Try alternative search terms

4. **OpenAI errors**
   - Verify API key is valid
   - Check token limits
   - Ensure model access permissions

### Debug Mode

Enable debug logging:
```env
DEBUG_FETCH=true
```

This will show detailed information about:
- Profile fetching attempts
- Email extraction process
- Wikipedia page matching
- API call details

## 📈 Performance Tips

1. **Batch Processing**: Use `queries.txt` for multiple searches
2. **Caching**: Wikipedia results are cached to avoid duplicates
3. **Rate Limiting**: Built-in delays prevent API overuse
4. **Early Deduplication**: Skips already-processed profiles
5. **Affiliation Filtering**: Reduces irrelevant results

## 🔄 Maintenance Scripts

- `remove_duplicates.py` - Clean duplicate entries from CSV files
- `migrate_to_new_schema.py` - Convert old CSV format to new schema
- `backfill_summaries.py` - Generate missing summaries
- `backfill_emails.py` - Find missing emails

## 📝 License

This project is for academic research purposes. Please respect:
- Google Scholar's terms of service
- Wikipedia's usage policies
- OpenAI's API terms
- Individual privacy and data protection laws

## 🤝 Contributing

When modifying the code:
1. Test with small datasets first
2. Respect API rate limits
3. Update documentation for new features
4. Maintain backward compatibility with CSV schema
5. Add proper error handling for new functions

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Verify your API keys and configuration
3. Test with debug mode enabled
4. Review the error messages in the console output
