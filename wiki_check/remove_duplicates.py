#!/usr/bin/env python3
"""
Script to remove duplicates from existing CSV files.
Prioritizes Wikipedia URL for deduplication, then falls back to email.
"""

import csv
import os
from typing import Dict, List, Set, Tuple

def remove_duplicates_from_csv(file_path: str) -> int:
    """Remove duplicates from a CSV file, prioritizing Wikipedia URL for uniqueness."""
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist, skipping...")
        return 0
    
    # Read all rows
    rows = []
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0
    
    if not rows:
        print(f"No data in {file_path}")
        return 0
    
    # Deduplicate using (Name, Wikipedia URL) as primary key
    seen_keys: Set[Tuple[str, str]] = set()
    unique_rows = []
    duplicates_removed = 0
    
    for row in rows:
        name = (row.get("Name") or "").lower().strip()
        wurl = (row.get("wikipedia_url") or "").strip().lower()
        email = (row.get("email") or "").strip().lower()
        
        # Use Wikipedia URL if available, otherwise fall back to email
        unique_id = wurl if wurl and wurl != "n/a" else email
        key = (name, unique_id)
        
        if key not in seen_keys:
            seen_keys.add(key)
            unique_rows.append(row)
        else:
            duplicates_removed += 1
            print(f"  Removing duplicate: {row.get('Name')} (key: {key})")
    
    # Write back unique rows
    if duplicates_removed > 0:
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(unique_rows)
            print(f"✅ Removed {duplicates_removed} duplicates from {file_path}")
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return 0
    
    return duplicates_removed

def main():
    """Remove duplicates from all CSV files."""
    csv_files = [
        "qualified_scholar_profiles_with_wikipedia.csv",
        "qualified_scholar_profiles_without_wikipedia.csv", 
        "without_email.csv"
    ]
    
    total_removed = 0
    for file_path in csv_files:
        print(f"\nProcessing {file_path}...")
        removed = remove_duplicates_from_csv(file_path)
        total_removed += removed
    
    print(f"\n📊 Summary: Removed {total_removed} total duplicates across all files")

if __name__ == "__main__":
    main()
