#!/usr/bin/env python3
import csv

path = 'full_name_with_analysis.csv'

# Count physical lines
with open(path, 'r', encoding='utf-8', errors='replace') as f:
	physical_lines = sum(1 for _ in f)

# Count logical rows and detect rows with embedded newlines
with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
	reader = csv.reader(f)
	header = next(reader, None)
	row_count = 0
	multiline_rows = 0
	for row in reader:
		row_count += 1
		if any('\n' in (field or '') for field in row):
			multiline_rows += 1

print(f'Physical line count: {physical_lines}')
print(f'Logical row count (including header): {row_count + (1 if header else 0)}')
print(f'Data rows (excluding header): {row_count}')
print(f'Rows containing embedded newlines: {multiline_rows}')












