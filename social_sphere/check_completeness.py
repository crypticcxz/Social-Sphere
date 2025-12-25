#!/usr/bin/env python3
"""
Check if all unique entries from full_name.csv are in full_name_with_analysis.csv
"""

import csv
from collections import Counter

def check_completeness():
    # Read original CSV
    print("Reading full_name.csv...")
    with open('full_name.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        original_rows = list(reader)
    
    print(f"Original CSV has {len(original_rows)} entries")
    
    # Read analysis CSV
    print("Reading full_name_with_analysis.csv...")
    with open('full_name_with_analysis.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        analysis_rows = list(reader)
    
    print(f"Analysis CSV has {len(analysis_rows)} entries")
    
    # Create sets of unique name+email combinations
    original_combinations = set()
    analysis_combinations = set()
    
    for row in original_rows:
        name = row.get('Name', '').strip()
        email = row.get('email', '').strip()
        key = f'{name}|{email}'
        original_combinations.add(key)
    
    for row in analysis_rows:
        name = row.get('Name', '').strip()
        email = row.get('email', '').strip()
        key = f'{name}|{email}'
        analysis_combinations.add(key)
    
    print(f"\nUnique combinations in original: {len(original_combinations)}")
    print(f"Unique combinations in analysis: {len(analysis_combinations)}")
    
    # Find missing entries
    missing = original_combinations - analysis_combinations
    extra = analysis_combinations - original_combinations
    
    print(f"\nMissing from analysis: {len(missing)}")
    print(f"Extra in analysis: {len(extra)}")
    
    if missing:
        print("\nFirst 10 missing entries:")
        for i, combo in enumerate(list(missing)[:10]):
            name, email = combo.split('|', 1)
            print(f"{i+1}. {name} | {email}")
    
    if extra:
        print("\nFirst 10 extra entries in analysis:")
        for i, combo in enumerate(list(extra)[:10]):
            name, email = combo.split('|', 1)
            print(f"{i+1}. {name} | {email}")
    
    # Check completion percentage
    if len(original_combinations) > 0:
        completion_rate = (len(analysis_combinations) / len(original_combinations)) * 100
        print(f"\nCompletion rate: {completion_rate:.2f}%")
        
        if len(missing) == 0:
            print("✅ All unique entries have been processed!")
        else:
            print(f"❌ {len(missing)} unique entries are missing from analysis")
    
    return len(missing) == 0

if __name__ == "__main__":
    check_completeness()












