import csv
import os

def separate_names(input_csv_path):
    """
    Separates CSV data into two files based on whether the Name field contains
    only a first name or a full name (multiple words).
    
    Args:
        input_csv_path (str): Path to the input CSV file
    """
    
    # Define output file paths
    first_name_csv = "first_name.csv"
    full_name_csv = "full_name.csv"
    
    # Lists to store the separated data
    first_name_data = []
    full_name_data = []
    
    # Read the input CSV and separate the data
    with open(input_csv_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        
        for row in csv_reader:
            name = row['Name'].strip()
            
            # Check if the name contains only one word (first name only)
            if len(name.split()) == 1:
                first_name_data.append(row)
            else:
                # Multiple words means it's a full name
                full_name_data.append(row)
    
    # Write first name data to CSV
    if first_name_data:
        with open(first_name_csv, 'w', newline='', encoding='utf-8') as file:
            fieldnames = ['Name', 'email', 'wikipedia_url']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(first_name_data)
        print(f"Created {first_name_csv} with {len(first_name_data)} entries (first names only)")
    else:
        print("No first name entries found")
    
    # Write full name data to CSV
    if full_name_data:
        with open(full_name_csv, 'w', newline='', encoding='utf-8') as file:
            fieldnames = ['Name', 'email', 'wikipedia_url']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(full_name_data)
        print(f"Created {full_name_csv} with {len(full_name_data)} entries (full names)")
    else:
        print("No full name entries found")
    
    # Print summary statistics
    total_entries = len(first_name_data) + len(full_name_data)
    print(f"\nSummary:")
    print(f"Total entries processed: {total_entries}")
    print(f"First name entries: {len(first_name_data)}")
    print(f"Full name entries: {len(full_name_data)}")

def main():
    """
    Main function to run the name separation script
    """
    input_file = "wikipedia.csv"
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found in current directory")
        return
    
    print(f"Processing {input_file}...")
    separate_names(input_file)
    print("Name separation completed successfully!")

if __name__ == "__main__":
    main()
