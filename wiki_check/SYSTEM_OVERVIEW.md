# Academic Profile Scraper System - Complete Technical Overview

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Architecture & Components](#architecture--components)
3. [Data Flow Pipeline](#data-flow-pipeline)
4. [Key Algorithms & Techniques](#key-algorithms--techniques)
5. [API Integrations](#api-integrations)
6. [Error Handling & Edge Cases](#error-handling--edge-cases)
7. [Configuration System](#configuration-system)
8. [Output & Results](#output--results)
9. [Interview Talking Points](#interview-talking-points)

---

## System Overview

### What This System Does
This is a **comprehensive academic profile discovery and enrichment system** that:
1. **Searches** Google Scholar for high-impact professors/researchers
2. **Extracts** academic metrics (citations, h-index) from multiple sources
3. **Filters** profiles based on configurable thresholds
4. **Enriches** profiles with Wikipedia pages, homepages, and contact emails
5. **Generates** AI-powered summaries using GPT-4o-mini
6. **Organizes** results into categorized CSV files

### Core Purpose
Build a database of qualified academic profiles with complete contact information and biographical summaries for outreach, research, or networking purposes.

---

## Architecture & Components

### 1. Main Script: `wiki.py` (2096 lines)
The orchestrator that coordinates all operations.

**Key Responsibilities:**
- Google Scholar search via Custom Search Engine (CSE)
- Metrics extraction from multiple sources
- Profile qualification filtering
- Wikipedia page discovery
- Homepage URL extraction
- Email discovery via EmailScraper integration
- Summary generation with GPT fallback chain
- CSV output management with deduplication

### 2. Email Scraper Module: `Email_Scrapper/email_scraper_final.py`
Specialized email extraction and analysis tool.

**Key Features:**
- Web scraping with configurable depth
- Multi-strategy email extraction (regex, HTML parsing, mailto links, obfuscation handling)
- TF-IDF analysis for name-to-email matching
- Pattern-based scoring
- Similarity analysis
- CSV export with timestamps

**Three Analysis Methods:**
1. **Pattern Analysis**: Exact/partial name matching, initial detection
2. **TF-IDF Analysis**: Vector similarity using scikit-learn
3. **Similarity Analysis**: Advanced pattern matching with scoring

### 3. Deduplication Script: `remove_duplicates.py`
Maintains data integrity by removing duplicate entries.

**Deduplication Strategy:**
- Primary key: `(Name, Wikipedia_URL)` if Wikipedia exists
- Fallback key: `(Name, email)` if no Wikipedia URL
- Case-insensitive matching
- Unicode normalization

### 4. Configuration Files

**`config.json`**: Email scraper settings
- Max URLs to scrape
- Timeout values
- User agent strings
- Analysis method preferences
- Scoring weights

**`queries.txt`**: Search query rotation system
- Format: `search term || affiliation1,affiliation2`
- 248+ pre-configured university queries
- Automatic rotation and consumption
- Per-query affiliation filtering

**`.env`**: Environment variables
- API keys (Google, OpenAI)
- CSE IDs (Scholar, General)
- Thresholds (citations, h-index)
- Pagination settings
- Wikipedia API configuration

---

## Data Flow Pipeline

### Phase 1: Search & Discovery
```
1. Load query from queries.txt (or env SEARCH_TERM)
2. Execute Google Scholar CSE search with pagination
3. Extract results across multiple pages (configurable)
4. Parse titles, snippets, and profile URLs
```

### Phase 2: Metrics Extraction (Multi-Source Fallback Chain)
```
For each profile:
├─ Try: Extract from snippet/htmlSnippet (regex patterns)
├─ Try: Fetch full profile page HTML (with jina.ai fallback)
├─ Try: Targeted CSE refetch using profile user ID
└─ Try: OpenAlex API fallback (free, by name search)
```

**Why Multiple Sources?**
- Google Scholar snippets are often truncated
- Some profiles require full page parsing
- Rate limiting may block direct access
- OpenAlex provides free backup data

### Phase 3: Qualification Filtering
```
Check thresholds:
├─ Citations >= MIN_CITATIONS_THRESHOLD (default: 10,000)
├─ h-index >= MIN_H_INDEX_THRESHOLD (default: 40) [optional]
└─ Affiliation filter match (if configured)
```

**Affiliation Filtering:**
- Checks profile affiliation text
- Checks homepage domain
- Supports multiple tokens (e.g., "harvard,harvard.edu")
- Per-query override from queries.txt

### Phase 4: Data Enrichment

#### 4a. Homepage Discovery (Priority Order)
```
1. Extract from Google Scholar profile page
   └─ Parses HTML for "Homepage" link (handles JavaScript redirects)
2. Fetch from Wikipedia Wikidata (P856 property)
   └─ Official website property
3. Extract from Wikipedia external links
   └─ Scored by domain (.edu preference) and keywords
4. Targeted CSE search
   └─ Query: "name homepage site:edu"
```

#### 4b. Wikipedia Page Finding (MediaWiki API)
```
1. Search MediaWiki API with cleaned name (first+last)
2. Handle disambiguation pages intelligently
3. Try alternative searches with academic keywords
4. Score results (prefer parenthetical titles, academic keywords)
5. Match using intelligent name matching (handles variations)
6. Cache results to avoid duplicate API calls
```

**Name Matching Intelligence:**
- Handles middle initials (e.g., "Donald Ingber" = "Donald E. Ingber")
- Supports aliases (e.g., "Abraham" = "Avi")
- Removes academic titles (Prof., Dr., etc.)
- Parentheses handling ("Gary King (political scientist)")
- Multiple matching strategies (exact, contained, parts match)

#### 4c. Email Extraction
```
1. Validate homepage URL (reject PDFs, news articles, etc.)
2. Scrape homepage using EmailScraper
   ├─ Extract emails via regex, HTML parsing, mailto links
   ├─ Handle obfuscation ("at", "dot", etc.)
   └─ Filter invalid emails (hashes, numbers-only, etc.)
3. Analyze emails using TF-IDF + pattern matching
   └─ Score by name similarity
4. Return best match or "Not found"
```

**Email Validation:**
- Strict regex pattern
- Rejects file extensions (.pdf, .jpg, etc.)
- Requires alphabetic characters in domain
- Filters path-like strings

#### 4d. Summary Generation (Fallback Chain)
```
1. Wikipedia extract → GPT-4o-mini summary (3-6 sentences)
2. Homepage text → GPT-4o-mini summary (1-2 sentences)
3. Wikipedia external links → Homepage → GPT summary
4. Heuristic summary → Rule-based (1-2 sentences)
```

**Heuristic Summary:**
- Uses affiliation text
- Extracts field keywords from snippet
- Deterministic, no API calls

### Phase 5: Output Organization
```
Split profiles by email availability:
├─ WITH email:
│   ├─ WITH Wikipedia → qualified_scholar_profiles_with_wikipedia.csv
│   └─ WITHOUT Wikipedia → qualified_scholar_profiles_without_wikipedia.csv
└─ WITHOUT email → without_email.csv
```

**CSV Schema:**
- `Name`: Professor's full name
- `email`: Contact email or "Not found"
- `wikipedia_url`: Wikipedia page URL or "N/A"
- `info`: AI-generated summary
- `is_wiki`: "1" if Wikipedia exists, "0" otherwise

---

## Key Algorithms & Techniques

### 1. Metrics Extraction Regex Patterns

**Citations:**
```python
patterns = [
    r"(?:Cited by|Citations?)\s*(?:[,:\-]?\s*)?([0-9][0-9,\.]*)",
    r"([0-9][0-9,\.]*)\s*citations?",
    r"Citations\s*,\s*([0-9][0-9,\.]*)",
]
```

**h-index:**
```python
patterns = [
    r"h[\s\-–—]?index\s*(?:[,:\-]?\s*)?([0-9]{1,4})",
    r"([0-9]{1,4})\s*h[\s\-–—]?index",
]
```

**Handles:**
- Unicode variations (en dash, em dash)
- Extra commas and punctuation
- Different word orders

### 2. Name Matching Algorithm

**Multi-Strategy Approach:**
1. **Exact Match**: After Unicode cleaning and normalization
2. **Contained Match**: Person name in title or vice versa
3. **Parentheses Handling**: Strip descriptive text "(scientist)"
4. **Parts Match**: At least 2 significant name parts match
5. **First/Last Match**: Ignore middle names/initials
6. **Alias Support**: Pre-defined nickname mappings
7. **Academic Context**: Check for academic keywords in snippet

**Example:**
- "Donald Ingber" matches "Donald E. Ingber"
- "Abraham Church" matches "Avi Church" (via alias)
- "Jeff W. Litchman" matches "Jeff Litchman"

### 3. Email Scoring Algorithm

**Pattern-Based Scoring:**
```python
exact_first_name: +10 points
exact_last_name: +10 points
partial_first_name: +5 points
partial_last_name: +5 points
first_initial: +2 points
last_initial: +2 points
both_names_bonus: +5 points
full_name_bonus: +15 points
domain_bonus: +5 points
```

**TF-IDF Analysis:**
- Vectorizes email local parts and target name
- Uses n-grams (1-2) for better matching
- Cosine similarity scoring
- Converts to 0-100 scale

**Combined Scoring:**
- Sums scores from all three methods
- Returns highest-scoring email

### 4. Wikipedia Disambiguation Handling

**Strategy:**
1. Detect disambiguation pages via pageprops
2. Try alternative searches with academic keywords:
   - "{name} scientist"
   - "{name} professor"
   - "{name} Harvard"
   - Field-specific terms (geneticist, physicist, etc.)
3. Filter out disambiguation pages
4. Score remaining results
5. Match using intelligent name matching

### 5. Unicode Cleaning

**Problem:** Google Scholar results contain invisible Unicode control characters that break CSV parsing.

**Solution:**
```python
# Remove directional marks, embeddings, overrides
cleaned = re.sub(r'[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\uf8ff]', '', text)
# Normalize whitespace
cleaned = re.sub(r'[\u00a0\u2000-\u200a]', ' ', cleaned)
```

**Why Critical:**
- Prevents CSV corruption
- Ensures consistent name matching
- Fixes display issues

---

## API Integrations

### 1. Google Custom Search Engine (CSE)

**Two CSEs Required:**
- **Scholar CSE**: Searches scholar.google.com only
- **General CSE**: Searches entire web

**Usage:**
- Scholar search for profiles
- Targeted metrics refetch
- Homepage discovery
- Email search (legacy, mostly replaced)

**Rate Limiting:**
- 100 free queries/day per CSE
- Tracks call count globally
- Pagination support (10 results/page, max 3 pages default)

### 2. MediaWiki API (Wikipedia)

**Endpoints Used:**
- `action=query&list=search`: Search for pages
- `action=query&prop=extracts`: Get page content
- `action=query&prop=extlinks`: Get external links
- `action=query&prop=pageprops`: Check disambiguation
- `action=query&prop=info`: Resolve redirects

**Advantages Over CSE:**
- Free, no rate limits (with proper User-Agent)
- More reliable for Wikipedia-specific queries
- Better disambiguation handling
- Direct access to structured data

**Rate Limiting:**
- Configurable delay (default: 120ms)
- Proper User-Agent required (includes mailto)
- Caching prevents duplicate calls

### 3. OpenAI GPT-4o-mini

**Usage:**
- Summary generation from Wikipedia extracts
- Summary generation from homepage text

**Configuration:**
- Model: `gpt-4o-mini` (cost-effective)
- Temperature: 0.2 (deterministic)
- Max tokens: 250 (wiki) or 120 (homepage)
- System prompts for academic focus

**Fallback Chain:**
- If API fails → heuristic summary
- If no text available → "N/A"

### 4. OpenAlex API

**Purpose:** Free fallback for missing metrics

**Usage:**
- Search by author name
- Score results by name token overlap
- Prefer matching institution hints
- Extract citations and h-index from summary_stats

**Advantages:**
- Free, no API key required
- Good coverage of academic authors
- Provides structured data

### 5. Jina.ai Reader (r.jina.ai)

**Purpose:** Bypass Google Scholar blocking

**Usage:**
- Fallback when direct HTML fetch fails
- Returns plain-text version of pages
- Handles JavaScript-rendered content

**Configuration:**
- Enabled via `PROFILE_FETCH_MODE=auto`
- Only used if HTML fetch fails or returns sign-in page

---

## Error Handling & Edge Cases

### 1. Network Errors
- **Timeouts**: Configurable (15s default)
- **Connection Errors**: Graceful fallback to next source
- **HTTP Errors**: Logged, skipped with warning

### 2. API Rate Limiting
- **Google CSE**: Tracks call count, stops at limit
- **Wikipedia**: Built-in delays, caching
- **OpenAI**: Try-catch, fallback to heuristic

### 3. Missing Data Handling
- **No Citations**: Try multiple sources, accept None if all fail
- **No h-index**: Optional requirement (REQUIRE_H_INDEX flag)
- **No Homepage**: Try Wikipedia fallbacks, accept "N/A"
- **No Email**: Separate CSV file, don't block processing

### 4. Invalid Data Filtering
- **Invalid Emails**: Regex validation, extension filtering
- **Invalid URLs**: PDF/document detection, news article filtering
- **Invalid Names**: Unicode cleaning, "Unknown" fallback

### 5. Duplicate Prevention
- **Early Skip**: Check existing CSV files before processing
- **Deduplication**: (Name, Wikipedia_URL) or (Name, email) keys
- **Case-Insensitive**: Normalize before comparison

### 6. Disambiguation Pages
- **Detection**: Check pageprops for "disambiguation"
- **Resolution**: Alternative searches with keywords
- **Rejection**: Skip if only disambiguation found

### 7. Google Sign-In Pages
- **Detection**: Check for "accounts.google.com" or sign-in text
- **Fallback**: Use jina.ai reader
- **Warning**: Logged in debug mode

---

## Configuration System

### Environment Variables (.env)

**Required:**
```env
GOOGLE_API_KEY=your_key
GOOGLE_SCHOLAR_CSE_ID=your_scholar_cse_id
GOOGLE_GENERAL_CSE_ID=your_general_cse_id
OPENAI_API_KEY=your_openai_key
```

**Optional:**
```env
# Search Configuration
SEARCH_TERM="harvard university professor \"cited by\" \"h-index\""
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

**Format:**
```
search term || affiliation1,affiliation2,affiliation3
```

**Example:**
```
Harvard professor "cited by" "h-index" || harvard,harvard.edu,hms.harvard.edu
Stanford professor "cited by" "h-index" || stanford,stanford.edu
```

**Behavior:**
- Reads first line
- Consumes it after use
- Rotates through file
- Supports per-query affiliation filters

### Email Scraper Config (config.json)

```json
{
    "max_urls": 50,
    "timeout": 15,
    "user_agent": "Mozilla/5.0...",
    "follow_external_links": false,
    "save_results": true,
    "analysis_methods": ["pattern", "tfidf", "similarity"],
    "email_patterns": {
        "exclude_hashes": true,
        "exclude_numbers_only": true,
        "min_length": 3,
        "exclude_no_letters": true
    },
    "scoring": {
        "exact_first_name": 10,
        "exact_last_name": 10,
        ...
    }
}
```

---

## Output & Results

### CSV File Structure

**All files use same schema:**
```csv
Name,email,wikipedia_url,info,is_wiki
```

**Three Output Files:**

1. **qualified_scholar_profiles_with_wikipedia.csv**
   - Profiles with email AND Wikipedia page
   - `is_wiki = "1"`

2. **qualified_scholar_profiles_without_wikipedia.csv**
   - Profiles with email but NO Wikipedia page
   - `is_wiki = "0"`

3. **without_email.csv**
   - Profiles without valid email
   - `email = "Not found"`
   - May or may not have Wikipedia

### Data Quality Features

**Deduplication:**
- Prevents duplicate entries
- Uses intelligent keys
- Case-insensitive matching

**Unicode Cleaning:**
- Removes problematic characters
- Normalizes whitespace
- Prevents CSV corruption

**Validation:**
- Email format validation
- URL validation
- Name cleaning

---

## Interview Talking Points

### System Design Decisions

**Q: Why use multiple fallback sources for metrics?**
**A:** 
- Google Scholar snippets are often truncated
- Rate limiting may block direct access
- Different sources have different coverage
- Ensures maximum data completeness
- OpenAlex provides free backup

**Q: Why MediaWiki API instead of Google CSE for Wikipedia?**
**A:**
- Free, no rate limits (with proper User-Agent)
- More reliable for Wikipedia-specific queries
- Better disambiguation handling
- Direct access to structured data (pageprops, extlinks)
- Reduces Google CSE quota usage

**Q: Why separate CSV files by email/Wikipedia status?**
**A:**
- Different use cases (outreach vs. research)
- Easier filtering and analysis
- Clear data quality indicators
- Supports different workflows

**Q: How do you handle rate limiting?**
**A:**
- Track Google CSE call count globally
- Built-in delays for Wikipedia API
- Caching prevents duplicate Wikipedia calls
- Graceful fallbacks when limits hit
- Pagination support for bulk processing

**Q: Why TF-IDF for email matching?**
**A:**
- Handles name variations (dots, underscores, hyphens)
- Considers n-grams for better matching
- Provides similarity scores
- Combines with pattern matching for robustness

### Technical Challenges Solved

**Challenge 1: Unicode Corruption**
- **Problem:** Google Scholar returns invisible Unicode control characters
- **Solution:** Comprehensive Unicode cleaning regex
- **Impact:** Prevents CSV corruption, ensures consistent matching

**Challenge 2: Google Scholar Blocking**
- **Problem:** Direct HTML fetch returns sign-in pages
- **Solution:** Jina.ai reader fallback + targeted CSE refetch
- **Impact:** Maintains high success rate

**Challenge 3: Disambiguation Pages**
- **Problem:** Wikipedia search returns disambiguation pages
- **Solution:** Detect via pageprops, try alternative searches with keywords
- **Impact:** Accurate Wikipedia page matching

**Challenge 4: Email Obfuscation**
- **Problem:** Emails hidden as "name at domain dot com"
- **Solution:** Deobfuscation regex patterns
- **Impact:** Higher email discovery rate

**Challenge 5: Name Variations**
- **Problem:** "Donald Ingber" vs "Donald E. Ingber"
- **Solution:** Multi-strategy name matching (exact, parts, first/last)
- **Impact:** Accurate profile matching

### Performance Optimizations

1. **Early Deduplication**: Skip processing if profile already exists
2. **Caching**: Wikipedia results cached to avoid duplicate API calls
3. **Parallel Fallbacks**: Try multiple sources simultaneously where possible
4. **Selective Fetching**: Only fetch full profile if metrics missing
5. **Query Rotation**: Process multiple universities efficiently

### Scalability Considerations

**Current Limitations:**
- Google CSE: 100 queries/day (free tier)
- Sequential processing (could be parallelized)
- Single-threaded execution

**Potential Improvements:**
- Parallel processing with threading/async
- Database backend instead of CSV
- API key rotation for higher quotas
- Distributed scraping architecture

### Code Quality Features

1. **Error Handling**: Comprehensive try-catch blocks
2. **Logging**: Detailed debug output (configurable)
3. **Configuration**: Environment-based, flexible
4. **Modularity**: Separate concerns (email scraper, Wikipedia, etc.)
5. **Documentation**: Inline comments, README files

### Testing Strategy

**What to Test:**
- Metrics extraction regex patterns
- Name matching algorithm
- Email validation
- Wikipedia disambiguation handling
- Deduplication logic
- Unicode cleaning

**Test Cases:**
- Edge cases (missing data, invalid formats)
- Name variations (middle initials, aliases)
- Different email formats
- Disambiguation pages
- Rate limiting scenarios

---

## Summary

This system demonstrates:
- **Multi-source data aggregation** with intelligent fallbacks
- **Robust error handling** and edge case management
- **Efficient API usage** with caching and rate limiting
- **Advanced text processing** (regex, TF-IDF, name matching)
- **Modular architecture** with clear separation of concerns
- **Production-ready features** (deduplication, validation, logging)

**Key Strengths:**
1. Handles incomplete/missing data gracefully
2. Multiple fallback strategies ensure high success rate
3. Intelligent matching algorithms reduce false positives
4. Well-documented and configurable
5. Handles real-world edge cases (Unicode, obfuscation, disambiguation)

**Interview Focus Areas:**
- Explain the fallback chain strategy
- Discuss name matching algorithm complexity
- Describe API integration patterns
- Explain deduplication strategy
- Discuss scalability improvements



