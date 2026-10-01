# System Architecture - Visual Flow Diagrams

## High-Level System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACADEMIC PROFILE SCRAPER                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: SEARCH & DISCOVERY                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ queries.txt → Google Scholar CSE → Pagination           │  │
│  │ Extract: titles, snippets, profile URLs                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: METRICS EXTRACTION (Multi-Source Fallback Chain)     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Extract from snippet (regex patterns)                 │  │
│  │    ↓ if missing                                          │  │
│  │ 2. Fetch full profile HTML (with jina.ai fallback)       │  │
│  │    ↓ if missing                                          │  │
│  │ 3. Targeted CSE refetch (by user ID)                     │  │
│  │    ↓ if missing                                          │  │
│  │ 4. OpenAlex API fallback (by name)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: QUALIFICATION FILTERING                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Citations >= 10,000?                                      │  │
│  │ h-index >= 40? (optional)                                 │  │
│  │ Affiliation match? (if configured)                        │  │
│  │                                                            │  │
│  │ ✅ QUALIFIED → Continue                                   │  │
│  │ ❌ REJECTED → Skip                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: DATA ENRICHMENT                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│  │ │  Homepage    │  │  Wikipedia   │  │    Email      │   │  │
│  │ │  Discovery   │  │  Finding     │  │  Extraction   │   │  │
│  │ └──────────────┘  └──────────────┘  └──────────────┘   │  │
│  │                                                             │  │
│  │ ┌──────────────────────────────────────────────────────┐  │  │
│  │ │         Summary Generation (Fallback Chain)          │  │  │
│  │ │  1. Wikipedia extract → GPT-4o-mini                  │  │  │
│  │ │  2. Homepage text → GPT-4o-mini                       │  │  │
│  │ │  3. Wikipedia extlinks → Homepage → GPT              │  │  │
│  │ │  4. Heuristic summary (rule-based)                    │  │  │
│  │ └──────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: OUTPUT ORGANIZATION                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Split by email/Wikipedia status:                        │  │
│  │                                                            │  │
│  │ ✅ Email + ✅ Wikipedia                                    │  │
│  │    → qualified_scholar_profiles_with_wikipedia.csv       │  │
│  │                                                            │  │
│  │ ✅ Email + ❌ Wikipedia                                    │  │
│  │    → qualified_scholar_profiles_without_wikipedia.csv    │  │
│  │                                                            │  │
│  │ ❌ Email (regardless of Wikipedia)                         │  │
│  │    → without_email.csv                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Homepage Discovery Flow

```
Profile URL
    │
    ▼
┌─────────────────────────────────────┐
│ Extract from Scholar Profile Page  │
│ (Parse HTML for "Homepage" link)   │
└─────────────────────────────────────┘
    │
    ├─ ✅ Found → Validate URL
    │              │
    │              ├─ ✅ Valid → Use it
    │              └─ ❌ Invalid → Continue
    │
    └─ ❌ Not Found
           │
           ▼
┌─────────────────────────────────────┐
│ Fetch from Wikipedia Wikidata      │
│ (P856 property: official website)   │
└─────────────────────────────────────┘
    │
    ├─ ✅ Found → Validate URL
    │              │
    │              ├─ ✅ Valid → Use it
    │              └─ ❌ Invalid → Continue
    │
    └─ ❌ Not Found
           │
           ▼
┌─────────────────────────────────────┐
│ Extract from Wikipedia External     │
│ Links (scored by .edu preference)  │
└─────────────────────────────────────┘
    │
    ├─ ✅ Found → Validate URL
    │              │
    │              ├─ ✅ Valid → Use it
    │              └─ ❌ Invalid → Continue
    │
    └─ ❌ Not Found
           │
           ▼
┌─────────────────────────────────────┐
│ Targeted CSE Search                │
│ Query: "name homepage site:edu"   │
└─────────────────────────────────────┘
    │
    ├─ ✅ Found → Validate URL
    │              │
    │              ├─ ✅ Valid → Use it
    │              └─ ❌ Invalid → "N/A"
    │
    └─ ❌ Not Found → "N/A"
```

## Wikipedia Page Finding Flow

```
Person Name
    │
    ▼
┌─────────────────────────────────────┐
│ Clean Name (remove titles, normalize)│
│ Extract: first + last name          │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Check Cache (key: first+last)      │
└─────────────────────────────────────┘
    │
    ├─ ✅ Cached → Return cached URL
    │
    └─ ❌ Not Cached
           │
           ▼
┌─────────────────────────────────────┐
│ MediaWiki API Search                │
│ Query: "first last" (unquoted)     │
└─────────────────────────────────────┘
    │
    ├─ ✅ Results Found
    │      │
    │      ▼
    │ ┌─────────────────────────────────┐
    │ │ Check for Disambiguation Pages │
    │ └─────────────────────────────────┘
    │      │
    │      ├─ ✅ Disambiguation Found
    │      │      │
    │      │      ▼
    │      │ ┌─────────────────────────────┐
    │      │ │ Alternative Searches        │
    │      │ │ - "name scientist"          │
    │      │ │ - "name professor"          │
    │      │ │ - "name Harvard"            │
    │      │ │ - Field-specific terms      │
    │      │ └─────────────────────────────┘
    │      │
    │      └─ ❌ No Disambiguation
    │             │
    │             ▼
    │ ┌─────────────────────────────────┐
    │ │ Score Results                   │
    │ │ - Parenthetical titles (+2)     │
    │ │ - Academic keywords (+1 each)  │
    │ │ - First+last match (+3)        │
    │ └─────────────────────────────────┘
    │             │
    │             ▼
    │ ┌─────────────────────────────────┐
    │ │ Match Using Intelligent        │
    │ │ Name Matching Algorithm        │
    │ └─────────────────────────────────┘
    │             │
    │             ├─ ✅ Match → Cache & Return
    │             └─ ❌ No Match → "N/A"
    │
    └─ ❌ No Results
           │
           ▼
┌─────────────────────────────────────┐
│ Retry with Quoted Search            │
│ Query: '"first last"'               │
└─────────────────────────────────────┘
    │
    └─ (Same process as above)
```

## Email Extraction Flow

```
Homepage URL
    │
    ▼
┌─────────────────────────────────────┐
│ Validate URL                        │
│ - Not PDF/document                 │
│ - Not news article                 │
│ - Looks like academic page         │
└─────────────────────────────────────┘
    │
    ├─ ❌ Invalid → "N/A"
    │
    └─ ✅ Valid
           │
           ▼
┌─────────────────────────────────────┐
│ EmailScraper.scrape_emails()       │
│ - Follow links (configurable depth)│
│ - Extract emails via:              │
│   • Regex patterns                 │
│   • HTML parsing                   │
│   • mailto links                   │
│   • Deobfuscation ("at", "dot")    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Filter Valid Emails                │
│ - Regex validation                 │
│ - Exclude file extensions          │
│ - Require alphabetic characters    │
└─────────────────────────────────────┘
    │
    ├─ ❌ No Valid Emails → "Not found"
    │
    └─ ✅ Valid Emails Found
           │
           ▼
┌─────────────────────────────────────┐
│ Analyze Emails for Person           │
│ ┌─────────────────────────────────┐ │
│ │ Method 1: Pattern Analysis      │ │
│ │ - Exact match: +10              │ │
│ │ - Partial match: +5             │ │
│ │ - Initial: +2                    │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ Method 2: TF-IDF Analysis       │ │
│ │ - Vectorize email & name        │ │
│ │ - Cosine similarity (0-100)     │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ Method 3: Similarity Analysis   │ │
│ │ - Name component matching       │ │
│ │ - Pattern scoring               │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Combine Scores                     │
│ Return highest-scoring email       │
└─────────────────────────────────────┘
```

## Summary Generation Flow

```
Profile Data
    │
    ▼
┌─────────────────────────────────────┐
│ Try Wikipedia Extract               │
│ - Fetch page content via API       │
│ - Extract plain text                │
└─────────────────────────────────────┘
    │
    ├─ ✅ Text Found
    │      │
    │      ▼
    │ ┌─────────────────────────────┐
    │ │ GPT-4o-mini Summary          │
    │ │ Mode: "wiki"                 │
    │ │ Output: 3-6 sentences       │
    │ └─────────────────────────────┘
    │      │
    │      └─ ✅ Success → Return Summary
    │
    └─ ❌ No Text or Failed
           │
           ▼
┌─────────────────────────────────────┐
│ Try Homepage Text                   │
│ - Fetch HTML                        │
│ - Extract text (BeautifulSoup)     │
│ - Limit to 5000 chars              │
└─────────────────────────────────────┘
    │
    ├─ ✅ Text Found
    │      │
    │      ▼
    │ ┌─────────────────────────────┐
    │ │ GPT-4o-mini Summary          │
    │ │ Mode: "home"                 │
    │ │ Output: 1-2 sentences       │
    │ └─────────────────────────────┘
    │      │
    │      └─ ✅ Success → Return Summary
    │
    └─ ❌ No Text or Failed
           │
           ▼
┌─────────────────────────────────────┐
│ Try Wikipedia External Links        │
│ - Get homepage from extlinks        │
│ - Fetch homepage text              │
└─────────────────────────────────────┘
    │
    ├─ ✅ Text Found
    │      │
    │      ▼
    │ ┌─────────────────────────────┐
    │ │ GPT-4o-mini Summary          │
    │ │ Mode: "home"                 │
    │ └─────────────────────────────┘
    │      │
    │      └─ ✅ Success → Return Summary
    │
    └─ ❌ No Text or Failed
           │
           ▼
┌─────────────────────────────────────┐
│ Heuristic Summary                   │
│ - Use affiliation text              │
│ - Extract field keywords            │
│ - Rule-based (1-2 sentences)        │
│ - No API calls                     │
└─────────────────────────────────────┘
    │
    └─ Return Summary
```

## Name Matching Algorithm Flow

```
Person Name + Wikipedia Title
    │
    ▼
┌─────────────────────────────────────┐
│ Clean Both Names                    │
│ - Remove titles (Prof., Dr., etc.) │
│ - Normalize whitespace             │
│ - Lowercase                         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Strategy 1: Exact Match            │
│ Compare cleaned names               │
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match
           │
           ▼
┌─────────────────────────────────────┐
│ Strategy 2: Contained Match        │
│ Check if name in title or vice versa│
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match
           │
           ▼
┌─────────────────────────────────────┐
│ Strategy 3: Parentheses Handling    │
│ Strip "(scientist)" from title      │
│ Retry exact/contained match         │
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match
           │
           ▼
┌─────────────────────────────────────┐
│ Strategy 4: Parts Match             │
│ Check if 2+ significant parts match  │
│ (ignore initials, short words)      │
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match
           │
           ▼
┌─────────────────────────────────────┐
│ Strategy 5: First/Last Match        │
│ Compare first and last names only   │
│ (ignore middle names/initials)      │
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match
           │
           ▼
┌─────────────────────────────────────┐
│ Strategy 6: Alias Support          │
│ Check predefined aliases            │
│ (e.g., Abraham = Avi)              │
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match
           │
           ▼
┌─────────────────────────────────────┐
│ Strategy 7: Academic Context        │
│ Check for academic keywords         │
│ Verify name parts in snippet        │
└─────────────────────────────────────┘
    │
    ├─ ✅ Match → Return True
    │
    └─ ❌ No Match → Return False
```

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        wiki.py                              │
│                  (Main Orchestrator)                        │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Google CSE  │ │ MediaWiki    │ │ OpenAI      │ │ Email       │
│ API         │ │ API          │ │ GPT-4o-mini │ │ Scraper     │
│             │ │              │ │             │ │             │
│ • Scholar   │ │ • Search     │ │ • Summaries │ │ • Scraping  │
│ • General   │ │ • Extracts   │ │ • Fallback  │ │ • Analysis │
│ • Pagination│ │ • Extlinks   │ │   to        │ │ • TF-IDF   │
│             │ │ • Wikidata   │ │   heuristic │ │             │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
         │              │              │              │
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  CSV Output     │
                    │  (3 files)      │
                    └─────────────────┘
```

## Data Flow Through Components

```
Input: queries.txt
    │
    ▼
┌─────────────────────────────────────┐
│ Google Scholar CSE                 │
│ • Search with pagination           │
│ • Extract snippets                 │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Metrics Extraction                  │
│ • Regex from snippet               │
│ • Full page fetch                  │
│ • OpenAlex fallback                │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Qualification Filter                │
│ • Check thresholds                  │
│ • Affiliation match                 │
└─────────────────────────────────────┘
    │
    ├─ ❌ Rejected → Skip
    │
    └─ ✅ Qualified
           │
           ├──────────────────┬──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Homepage │      │Wikipedia │      │  Email   │
    │ Discovery│      │  Finding │      │Extraction│
    └──────────┘      └──────────┘      └──────────┘
           │                  │                  │
           └──────────────────┴──────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Summary Gen     │
                    │ (GPT fallback)  │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ CSV Output      │
                    │ (3 files)       │
                    └─────────────────┘
```



