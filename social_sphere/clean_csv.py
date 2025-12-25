#!/usr/bin/env python3
"""
Clean up the existing CSV file by removing Wikipedia markup and formatting issues.
"""

import csv
import re

def clean_text(text):
    """Clean text to remove Wikipedia markup and formatting issues."""
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

def clean_csv(input_file, output_file):
    """Clean the CSV file by removing Wikipedia markup from all text fields."""
    print(f"Cleaning {input_file} -> {output_file}")
    
    # Read the input CSV
    rows = []
    with open(input_file, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Clean each row
    cleaned_rows = []
    for row in rows:
        cleaned_row = {}
        for key, value in row.items():
            if key == 'info':  # This is the field with the Wikipedia analysis
                cleaned_row[key] = clean_text(value)
            else:
                cleaned_row[key] = value
        cleaned_rows.append(cleaned_row)
    
    # Write the cleaned CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)
    
    print(f"✅ Cleaned {len(cleaned_rows)} rows")
    print(f"📁 Output saved to: {output_file}")

if __name__ == "__main__":
    # Clean the original file in place
    clean_csv("full_name_with_analysis.csv", "full_name_with_analysis_temp.csv")
    
    # Replace original with cleaned version
    import shutil
    shutil.move("full_name_with_analysis_temp.csv", "full_name_with_analysis.csv")
    print("✅ Original file has been cleaned and updated")
