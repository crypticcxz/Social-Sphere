# Wikipedia Analyzer

This script analyzes Wikipedia pages for scholars and researchers, providing structured feedback on content completeness and quality.

## Quick Start

```bash
# Test with 5 entries first
python wiki_analyzer.py --limit 5

# Process all entries
python wiki_analyzer.py
```

## Updating Existing Files

If you have an existing `full_name_with_analysis.csv` file without the `is_wiki` column:

```bash
# Add the is_wiki column to existing file
python add_wiki_column.py

# Or specify custom files
python add_wiki_column.py --input my_file.csv --output my_updated_file.csv
```

## Features

- Fetches full Wikipedia page content using MediaWiki API
- **Smart URL/Title handling**: Works with both Wikipedia URLs and page titles
- **Automatic search**: If you have page titles instead of URLs, it will search MediaWiki to find the correct page
- Analyzes pages for required sections:
  - Introduction Paragraph
  - Early Life & Education section
  - Career Section
  - Research Section
  - Awards & Honors Section
  - Selected Publications section
  - Books (if available)
  - References
  - InfoBox with photo & basic info
- Detects Wikipedia warning templates and tags
- Uses OpenAI GPT-4 for intelligent analysis
- Adds analysis results to your CSV file

## Setup

1. **Install required packages:**
   ```bash
   pip install openai requests python-dotenv
   ```

2. **Create environment file:**
   - Copy `env_template.txt` to `.env`
   - Fill in your actual values:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     WIKI_MAILTO=your-email@example.com
     WIKI_DELAY_MS=200
     REQUEST_TIMEOUT=30
     ```

3. **Get OpenAI API Key:**
   - Visit https://platform.openai.com/api-keys
   - Create a new API key
   - Add it to your `.env` file

## Usage

### Test the Analyzer
First, test with a single Wikipedia page:
```bash
python test_analyzer.py
```

### Analyze Full Dataset
Process your `full_name.csv` file:
```bash
python wiki_analyzer.py
```

This will create a new file `full_name_with_analysis.csv` with the analysis results.

### Test with Limited Entries
For testing purposes, you can limit the number of entries processed:
```bash
# Process only first 5 entries
python wiki_analyzer.py --limit 5

# Process only first 50 entries
python wiki_analyzer.py --limit 50

# Custom input/output files with limit
python wiki_analyzer.py --input my_data.csv --output my_results.csv --limit 10
```

### Smart Processing (Resume Capability)
The script automatically detects already processed entries and skips them:
```bash
# First run - processes all entries
python wiki_analyzer.py --limit 10

# Second run - only processes remaining unprocessed entries
python wiki_analyzer.py --limit 10

# Force reprocessing of all entries (ignore existing results)
python wiki_analyzer.py --force
```

### Command Line Options
- `--input`: Input CSV file path (default: full_name.csv)
- `--output`: Output CSV file path (default: full_name_with_analysis.csv)
- `--limit`: Limit number of entries to process (useful for testing)
- `--force`: Force reprocessing of all entries (ignore existing results)

## Output Format

The script adds two new columns to your CSV:

1. **`info`** - Detailed analysis with the following format:
```
SUMMARY: [Brief summary of the person] | MISSING: [Missing sections] | WARNINGS: [Wikipedia warnings] | ASSESSMENT: [Overall assessment]
```

2. **`is_wiki`** - Boolean flag indicating Wikipedia analysis status:
- `1` - Wikipedia page successfully analyzed
- `0` - No Wikipedia page or failed to fetch

### Assessment Types:
- **"Perfect profile - no improvements possible"**: All required sections present, no warnings
- **Specific recommendations**: Lists what needs improvement

### Warning Detection:
The script detects common Wikipedia warning templates like:
- Notability issues
- Citation needed
- Cleanup required
- Unreferenced content
- Biased content
- And many more...

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | Required |
| `WIKI_MAILTO` | Your email for Wikipedia API requests | Required |
| `WIKI_DELAY_MS` | Delay between requests (milliseconds) | 200 |
| `REQUEST_TIMEOUT` | HTTP request timeout (seconds) | 30 |

## Rate Limiting

The script includes built-in rate limiting to be respectful to Wikipedia's servers:
- 200ms delay between requests (configurable)
- Proper User-Agent headers
- Email identification for Wikipedia API

## Error Handling

- Gracefully handles missing Wikipedia URLs
- Continues processing even if individual pages fail
- Provides detailed error messages
- Saves progress even if interrupted

## Files Created

- `full_name_with_analysis.csv`: Your original data with analysis results
- `test_analyzer.py`: Test script for verification
- `README_wiki_analyzer.md`: This documentation

## Troubleshooting

1. **"OPENAI_API_KEY not found"**: Make sure your `.env` file exists and contains the API key
2. **"Could not fetch Wikipedia content"**: 
   - Check your internet connection
   - The script now handles both URLs and page titles automatically
   - If you have entries like "Joshua Sanes - Wikipedia", it will search for the actual page
3. **Rate limiting errors**: Increase `WIKI_DELAY_MS` in your `.env` file
4. **OpenAI API errors**: Check your API key and account credits
5. **Mixed URL/Title format**: The script automatically detects and handles both formats:
   - `https://en.wikipedia.org/wiki/Person_Name` (full URL)
   - `Person Name - Wikipedia` (title format)
   - `Person Name` (just the name)

## Cost Estimation

- OpenAI GPT-4 costs approximately $0.03 per 1K tokens
- Each Wikipedia page analysis uses roughly 500-1000 tokens
- For 1000 pages: approximately $15-30 in OpenAI costs
- Wikipedia API is free with proper rate limiting
