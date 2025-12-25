# Email Scraper and Analyzer

A streamlined Python tool that takes a URL, scrapes emails, saves to CSV, then performs TF-IDF analysis to find the email that matches closest to a given name.

**Primary Workflow:**
1. **Input URL** → Scrape emails → Save to CSV
2. **Input person name** → TF-IDF analysis → Find best match

## 🚀 Features

- **Web Scraping**: Automatically scrapes emails from websites with configurable depth
- **Advanced Analysis**: Uses multiple algorithms (Pattern matching, TF-IDF, Similarity scoring)
- **Smart Filtering**: Filters out spam emails, hashes, and invalid patterns
- **CSV Export**: Saves results with timestamps for easy tracking
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Command Line Interface**: Easy-to-use CLI with multiple operation modes
- **Configurable**: Customizable parameters for different use cases

## 📋 Requirements

- Python 3.7+
- Internet connection for web scraping
- Required packages (see requirements.txt)

## 🛠️ Installation

1. **Clone or download the project files**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 📖 Usage

### Command Line Interface

#### Primary Mode (URL → Scrape → Analyze)
```bash
# Interactive mode - will prompt for person name after scraping
python email_scraper_final.py --url https://example.com

# Scrape and immediately analyze for a specific person
python email_scraper_final.py --url https://example.com --person "John Doe"

# Scrape only (skip analysis)
python email_scraper_final.py --url https://example.com --no-analysis

# Scrape with custom max URLs
python email_scraper_final.py --url https://example.com --max-urls 50
```

#### Interactive Mode (No arguments)
```bash
python email_scraper_final.py
```

#### Analysis Mode
```bash
# Analyze existing CSV file for a specific person
python email_scraper_final.py --csv emails_example.com_20240101_120000.csv --person "John Doe"
```

#### Advanced Options
```bash
# Verbose output
python email_scraper_final.py --url https://example.com --verbose

# Custom configuration file
python email_scraper_final.py --url https://example.com --config config.json
```

### Configuration File

Create a `config.json` file to customize behavior:

```json
{
    "max_urls": 30,
    "timeout": 15,
    "user_agent": "Custom User Agent",
    "follow_external_links": false,
    "save_results": true,
    "analysis_methods": ["pattern", "tfidf", "similarity"]
}
```

## 🔍 How It Works

### 1. Email Scraping
- Starts from a target URL
- Follows links within the same domain (configurable)
- Extracts emails using regex patterns
- Limits scraping depth to prevent infinite loops
- Saves results to timestamped CSV files

### 2. Email Analysis
The tool uses three analysis methods:

#### Pattern-Based Analysis
- Checks for exact name matches in email local parts
- Identifies partial matches and initials
- Scores based on name component presence
- Handles common email patterns (dots, underscores, hyphens)

#### TF-IDF Analysis
- Uses scikit-learn's TF-IDF vectorizer
- Compares email local parts with target name
- Calculates cosine similarity scores
- Considers n-grams for better matching

#### Similarity Analysis
- Advanced pattern matching
- Checks for name components and initials
- Provides detailed scoring breakdown
- Handles various email naming conventions

### 3. Result Combination
- Combines scores from all three methods
- Provides comprehensive analysis report
- Shows top candidates with detailed reasoning
- Gives final recommendation with confidence score

## 📊 Output Examples

### Scraping Results
```
[+] Scraping completed!
[+] URLs processed: 15
[+] Emails found: 23
[+] Emails saved to: emails_example.com_20240101_120000.csv

[+] Found emails:
 1. contact@example.com
 2. info@example.com
 3. john.doe@example.com
 4. jane.smith@example.com
 ...
```

### Analysis Results
```
🔍 COMPREHENSIVE EMAIL ANALYSIS FOR JOHN DOE
================================================================================

[+] PATTERN-BASED ANALYSIS (Top 5):
------------------------------------------------------------
1. john.doe@example.com                    | Score: 25
   Details: {'exact_first_name': True, 'exact_last_name': True, ...}

[+] TF-IDF ANALYSIS (Top 5):
------------------------------------------------------------
1. john.doe@example.com                    | Score: 95.2

[+] SIMILARITY ANALYSIS (Top 5):
------------------------------------------------------------
1. john.doe@example.com                    | Score: 20

================================================================================
🎯 FINAL RECOMMENDATION
================================================================================
📧 MOST LIKELY EMAIL: john.doe@example.com
📊 Combined Score: 140.2
✅ CONCLUSION: This is most likely John Doe's email address.
```

## 📁 File Structure

```
email-scraper/
├── email_scraper_final.py    # Main script
├── requirements.txt          # Dependencies
├── README.md                # This file
├── config.json              # Configuration (optional)
├── email_scraper.log        # Log file (generated)
└── emails_*.csv             # Output files (generated)
```

## ⚙️ Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `max_urls` | Maximum URLs to scrape | 20 |
| `timeout` | Request timeout in seconds | 10 |
| `user_agent` | HTTP User-Agent string | Mozilla/5.0... |
| `follow_external_links` | Follow links to other domains | false |
| `save_results` | Save results to CSV | true |
| `analysis_methods` | Analysis methods to use | ["pattern", "tfidf", "similarity"] |

## 🚨 Important Notes

### Legal and Ethical Considerations
- **Respect robots.txt**: Check website's robots.txt before scraping
- **Rate limiting**: The tool includes delays to be respectful
- **Terms of service**: Ensure compliance with website terms
- **Privacy**: Only use for legitimate purposes
- **GDPR/Privacy laws**: Be aware of applicable privacy regulations

### Technical Limitations
- Some websites may block automated requests
- JavaScript-rendered content is not supported
- Email addresses in images cannot be extracted
- Rate limiting may be necessary for large sites

## 🐛 Troubleshooting

### Common Issues

1. **No emails found**
   - Check if the website has emails in HTML source
   - Verify the URL is accessible
   - Try increasing `max_urls` limit

2. **Connection errors**
   - Check internet connection
   - Verify URL is correct
   - Try increasing timeout value

3. **Analysis not working**
   - Ensure CSV file exists and is readable
   - Check person name format (e.g., "John Doe")
   - Verify pandas and scikit-learn are installed

4. **Permission errors**
   - Ensure write permissions in current directory
   - Check if antivirus is blocking file creation

### Debug Mode
Use `--verbose` flag for detailed logging:
```bash
python email_scraper_final.py --url https://example.com --verbose
```

## 📈 Performance Tips

1. **Optimize scraping depth**: Use appropriate `max_urls` for your needs
2. **Filter domains**: Use `follow_external_links: false` for faster scraping
3. **Batch processing**: Process multiple sites separately
4. **Monitor logs**: Check `email_scraper.log` for issues

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is for educational and research purposes. Please ensure compliance with applicable laws and website terms of service.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the log files
3. Ensure all dependencies are installed
4. Verify your configuration

## 🔄 Version History

- **v1.0.0**: Initial release with comprehensive scraping and analysis features
- Multiple analysis algorithms
- Command-line interface
- Configuration support
- Comprehensive logging

---

**Disclaimer**: This tool is for educational and legitimate research purposes only. Users are responsible for ensuring compliance with applicable laws, website terms of service, and privacy regulations.
