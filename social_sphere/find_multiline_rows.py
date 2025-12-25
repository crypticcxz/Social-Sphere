#!/usr/bin/env python3
import csv

path = 'full_name_with_analysis.csv'

examples = []
with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
	reader = csv.reader(f)
	header = next(reader, None)
	for idx, row in enumerate(reader, start=2):
		newline_fields = [i for i, field in enumerate(row) if '\n' in (field or '')]
		if newline_fields:
			# capture up to first 3 examples
			examples.append((idx, newline_fields, row))
			if len(examples) >= 5:
				break

print(f'Found {len(examples)} example rows with embedded newlines:')
for line_num, cols, row in examples:
	print(f'Row {line_num} (data line; header is line 1) has newline(s) in column indexes: {cols}')
	# Show a compact preview with \n visible
	preview = []
	for i, field in enumerate(row):
		text = (field or '').replace('\n', '\\n')
		if len(text) > 140:
			text = text[:137] + '...'
		preview.append(text)
	print('  Preview of row fields:')
	for i, text in enumerate(preview):
		print(f'    [{i}] {text}')
	print()












