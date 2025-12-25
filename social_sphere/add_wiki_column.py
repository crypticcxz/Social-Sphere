#!/usr/bin/env python3
"""
Script to add 'is_wiki' column to existing full_name_with_analysis.csv file.
This script adds a new column with value "1" for all entries since all leads have Wikipedia pages.
"""

import csv
import os
import argparse

def add_is_wiki_column(input_csv: str, output_csv: str = None):
    """
    Add 'is_wiki' column to existing CSV file.
    
    Args:
        input_csv: Path to input CSV file
        output_csv: Path to output CSV file (if None, overwrites input file)
    """
    
    if not os.path.exists(input_csv):
        print(f"❌ Error: {input_csv} not found")
        return False
    
    # If no output file specified, overwrite the input file
    if output_csv is None:
        output_csv = input_csv
        print(f"📝 Will update {input_csv} in place")
    else:
        print(f"📝 Will create new file: {output_csv}")
    
    # Read the existing CSV
    rows = []
    try:
        with open(input_csv, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        print(f"✅ Read {len(rows)} entries from {input_csv}")
        
        # Check if 'is_wiki' column already exists
        if 'is_wiki' in fieldnames:
            print("⚠️ 'is_wiki' column already exists. Skipping.")
            return True
        
        # Add 'is_wiki' column to each row
        for row in rows:
            row['is_wiki'] = '1'  # All entries have Wikipedia pages
        
        # Add 'is_wiki' to fieldnames
        fieldnames.append('is_wiki')
        
        # Write the updated CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"✅ Successfully added 'is_wiki' column to {output_csv}")
        print(f"📊 Total entries updated: {len(rows)}")
        return True
        
    except Exception as e:
        print(f"❌ Error processing file: {e}")
        return False

def main():
    """Main function to add is_wiki column."""
    parser = argparse.ArgumentParser(description="Add 'is_wiki' column to existing CSV file")
    parser.add_argument(
        "--input", 
        default="full_name_with_analysis.csv", 
        help="Input CSV file path (default: full_name_with_analysis.csv)"
    )
    parser.add_argument(
        "--output", 
        help="Output CSV file path (if not specified, updates input file in place)"
    )
    
    args = parser.parse_args()
    
    print("🔧 Adding 'is_wiki' column to existing CSV file")
    print("=" * 60)
    
    success = add_is_wiki_column(args.input, args.output)
    
    if success:
        print("\n✅ Column addition completed successfully!")
        print("💡 The 'is_wiki' column has been added with value '1' for all entries")
    else:
        print("\n❌ Column addition failed!")
        print("💡 Please check the file path and try again")

if __name__ == "__main__":
    main()

















