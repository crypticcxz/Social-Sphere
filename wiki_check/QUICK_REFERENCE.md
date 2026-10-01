# Quick Reference Guide - Interview Prep

## 🎯 System Purpose
Automated academic profile discovery system that finds high-impact professors, extracts their contact info, finds Wikipedia pages, and generates AI summaries.

## 🔄 Main Workflow (5 Phases)

### Phase 1: Search
- Google Scholar CSE search with pagination
- Extract titles, snippets, profile URLs
- Query rotation from `queries.txt`

### Phase 2: Metrics Extraction (4 Fallbacks)
1. Extract from snippet (regex)
2. Fetch full profile HTML
3. Targeted CSE refetch by user ID
4. OpenAlex API fallback

### Phase 3: Qualification
- Citations >= 10,000 (configurable)
- h-index >= 40 (optional)
- Affiliation filter match

### Phase 4: Enrichment
- **Homepage**: Scholar → Wikidata → Wikipedia extlinks → CSE
- **Wikipedia**: MediaWiki API with disambiguation handling
- **Email**: EmailScraper with TF-IDF analysis
- **Summary**: Wikipedia → Homepage → Heuristic

### Phase 5: Output
- Split by email/Wikipedia status
- 3 CSV files with deduplication

## 📁 Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `wiki.py` | Main orchestrator | 2096 |
| `email_scraper_final.py` | Email extraction & analysis | 716 |
| `remove_duplicates.py` | Deduplication utility | 86 |
| `queries.txt` | Search query rotation | 248 queries |
| `config.json` | Email scraper config | JSON |

## 🔑 Key Algorithms

### 1. Metrics Extraction
- Regex patterns for citations/h-index
- Handles Unicode variations, commas, punctuation
- Multiple fallback sources

### 2. Name Matching (7 Strategies)
1. Exact match (normalized)
2. Contained match
3. Parentheses handling
4. Parts match (2+ parts)
5. First/last match (ignore middle)
6. Alias support (Abraham = Avi)
7. Academic context check

### 3. Email Scoring
- Pattern: Exact (+10), Partial (+5), Initial (+2)
- TF-IDF: Vector similarity (0-100 scale)
- Similarity: Advanced pattern matching
- Combined: Sum all scores

### 4. Wikipedia Disambiguation
- Detect via pageprops
- Alternative searches with keywords
- Filter disambiguation pages
- Score and match remaining

## 🌐 API Integrations

| API | Purpose | Rate Limits | Fallback |
|-----|---------|-------------|----------|
| Google Scholar CSE | Profile search | 100/day | OpenAlex |
| Google General CSE | Homepage/email | 100/day | Wikipedia |
| MediaWiki API | Wikipedia search | None (with UA) | N/A |
| OpenAI GPT-4o-mini | Summaries | Per token | Heuristic |
| OpenAlex API | Metrics backup | None | N/A |
| Jina.ai Reader | Bypass blocking | Per request | Direct HTML |

## 🛡️ Error Handling

| Error Type | Handling Strategy |
|------------|-------------------|
| Network timeout | Configurable timeout (15s), skip with warning |
| API rate limit | Track calls, stop at limit, use fallbacks |
| Missing data | Try all fallbacks, accept None if all fail |
| Invalid email | Regex validation, extension filtering |
| Disambiguation | Detect, try alternatives, reject if only disambiguation |
| Google blocking | Jina.ai reader fallback |
| Unicode corruption | Comprehensive cleaning regex |

## 📊 Output Schema

**All CSV files:**
```csv
Name,email,wikipedia_url,info,is_wiki
```

**3 Output Files:**
1. `qualified_scholar_profiles_with_wikipedia.csv` - Email + Wikipedia
2. `qualified_scholar_profiles_without_wikipedia.csv` - Email only
3. `without_email.csv` - No email (may have Wikipedia)

## 💡 Interview Talking Points

### Why Multiple Fallbacks?
- Snippets truncated → Full page fetch
- Rate limiting → Alternative sources
- Different coverage → Maximum completeness
- Free backup → OpenAlex

### Why MediaWiki API?
- Free, no rate limits
- Better disambiguation handling
- Direct structured data access
- Reduces Google CSE quota usage

### Key Challenges Solved
1. **Unicode Corruption**: Cleaning regex prevents CSV issues
2. **Google Blocking**: Jina.ai reader fallback
3. **Disambiguation**: Detect + alternative searches
4. **Email Obfuscation**: Deobfuscation patterns
5. **Name Variations**: Multi-strategy matching

### Performance Optimizations
- Early deduplication (skip existing)
- Wikipedia caching (avoid duplicates)
- Selective fetching (only if needed)
- Query rotation (efficient processing)

### Scalability Considerations
- Current: Sequential, CSV-based, single-threaded
- Improvements: Parallel processing, database backend, API rotation

## 🎓 Technical Concepts

### TF-IDF Analysis
- Vectorizes email local parts and target name
- Uses n-grams (1-2) for better matching
- Cosine similarity scoring
- Converts to 0-100 scale

### Deduplication Strategy
- Primary: `(Name, Wikipedia_URL)` if Wikipedia exists
- Fallback: `(Name, email)` if no Wikipedia
- Case-insensitive matching
- Unicode normalization

### Unicode Cleaning
- Removes directional marks, embeddings, overrides
- Normalizes whitespace (non-breaking spaces)
- Prevents CSV corruption
- Ensures consistent matching

## 🔧 Configuration Highlights

**Required Environment Variables:**
- `GOOGLE_API_KEY`
- `GOOGLE_SCHOLAR_CSE_ID`
- `GOOGLE_GENERAL_CSE_ID`
- `OPENAI_API_KEY`

**Key Thresholds:**
- `MIN_CITATIONS_THRESHOLD=10000`
- `MIN_H_INDEX_THRESHOLD=40`
- `REQUIRE_H_INDEX=false` (optional)

**Pagination:**
- `CSE_NUM_PER_PAGE=10`
- `CSE_MAX_PAGES=3`

## 📈 Data Flow Summary

```
Query → Scholar Search → Extract Metrics → Filter → Enrich → Output
         (CSE)            (4 fallbacks)    (thresholds)  (homepage/wiki/email/summary)  (3 CSVs)
```

## 🚀 Key Strengths

1. **Robust**: Multiple fallbacks handle missing data
2. **Intelligent**: Advanced matching algorithms
3. **Efficient**: Caching and early deduplication
4. **Flexible**: Configurable thresholds and filters
5. **Production-ready**: Error handling, logging, validation

## ⚠️ Common Questions

**Q: How do you handle rate limiting?**
A: Track Google CSE calls globally, built-in Wikipedia delays, caching prevents duplicates, graceful fallbacks.

**Q: Why separate CSV files?**
A: Different use cases (outreach vs research), easier filtering, clear data quality indicators.

**Q: What if Wikipedia page not found?**
A: Try alternative searches with keywords, handle disambiguation, accept "N/A" if no match.

**Q: How accurate is email matching?**
A: Three methods (pattern, TF-IDF, similarity) combined, scores by name similarity, filters invalid formats.

**Q: Can this scale?**
A: Current limitations (CSE quotas, sequential), but can parallelize, use database backend, rotate API keys.



