import os
import csv
import re
import time
import argparse
from typing import Dict, Optional
from dotenv import load_dotenv

# Reuse the analyzer from wiki_analyzer
from wiki_analyzer import WikipediaAnalyzer, OPENAI_API_KEY

# Load environment variables
load_dotenv()

OUTPUT_CSV = "full_name_with_analysis.csv"
INPUT_CSV = "first_name.csv"


def clean_for_csv(text: str) -> str:
	if not text:
		return ""
	text = str(text)
	# Remove Wikipedia markup
	text = re.sub(r'\[\[([^|\]]+)(\|[^\]]+)?\]\]', r'\1', text)
	text = re.sub(r'\{\{[^}]*\}\}', '', text)
	text = re.sub(r'<[^>]+>', '', text)
	text = re.sub(r'==+[^=]+==+', '', text)
	text = re.sub(r'\*+', '', text)
	text = re.sub(r'#+', '', text)
	text = re.sub(r'\|+', ' ', text)
	text = re.sub(r'^[\s\-\*#\|]+', '', text, flags=re.MULTILINE)
	# Clean up citation markers words
	text = re.sub(r'(?i)cite journal|cite book|cite web', '', text)
	# Replace commas and semicolons
	text = text.replace(",", " and")
	text = text.replace(";", " and")
	# Normalize whitespace
	text = re.sub(r'\s+', ' ', text).strip()
	return text


def load_existing_keys(output_csv: str) -> set:
	existing = set()
	if os.path.exists(output_csv):
		try:
			with open(output_csv, 'r', encoding='utf-8', newline='') as f:
				reader = csv.DictReader(f)
				for row in reader:
					key = f"{row.get('Name', '')}|{row.get('email', '')}"
					existing.add(key)
		except Exception:
			pass
	return existing


def process_first_name_csv(input_csv: str, output_csv: str, max_entries: Optional[int] = None, force: bool = False):
	if not OPENAI_API_KEY:
		raise ValueError("OPENAI_API_KEY not found in environment variables")

	analyzer = WikipediaAnalyzer()

	# Read input rows
	with open(input_csv, 'r', encoding='utf-8', newline='') as f:
		reader = csv.DictReader(f)
		rows = list(reader)

	existing = set()
	if not force:
		existing = load_existing_keys(output_csv)

	# Filter to unprocessed
	rows_to_process = []
	skipped = 0
	for r in rows:
		key = f"{r.get('Name', '')}|{r.get('email', '')}"
		if not force and key in existing:
			skipped += 1
			continue
		rows_to_process.append(r)

	if max_entries is not None and max_entries < len(rows_to_process):
		rows_to_process = rows_to_process[:max_entries]

	print(f"Processing {len(rows_to_process)} entries from {input_csv}...")
	if skipped:
		print(f"⏭️ Skipping {skipped} already processed entries")

	processed = 0
	for i, row in enumerate(rows_to_process, 1):
		name = row.get('Name', '')
		wiki_field = row.get('wikipedia_url', '') or ''

		print(f"{i}/{len(rows_to_process)}: {name}")

		if not wiki_field or wiki_field.strip().upper() == 'N/A':
			# No usable Wikipedia reference
			row['info'] = "No Wikipedia page available"
			row['is_wiki'] = '0'
		else:
			print(f"  Fetching: {wiki_field}")
			content = analyzer.fetch_wikipedia_content(wiki_field)
			if not content:
				print("  ❌ Could not fetch content")
				row['info'] = "Could not fetch Wikipedia content"
				row['is_wiki'] = '0'
			else:
				print("  ✅ Analyzing with OpenAI...")
				analysis = analyzer.analyze_with_openai(name, content)
				analysis_text = (
					f"SUMMARY: {clean_for_csv(analysis.get('summary',''))} | "
					f"MISSING: {clean_for_csv(analysis.get('missing_sections',''))} | "
					f"WARNINGS: {clean_for_csv(analysis.get('warnings',''))} | "
					f"ASSESSMENT: {clean_for_csv(analysis.get('overall_assessment',''))}"
				)
				row['info'] = analysis_text
				row['is_wiki'] = '1'

		# Append immediately
		try:
			file_exists = os.path.exists(output_csv)
			with open(output_csv, 'a', encoding='utf-8', newline='') as f:
				fieldnames = ['Name', 'email', 'wikipedia_url', 'info', 'is_wiki']
				writer = csv.DictWriter(f, fieldnames=fieldnames)
				if not file_exists:
					writer.writeheader()
				writer.writerow({
					'Name': row.get('Name',''),
					'email': row.get('email',''),
					'wikipedia_url': row.get('wikipedia_url',''),
					'info': row.get('info',''),
					'is_wiki': row.get('is_wiki','0'),
				})
			processed += 1
			print(f"  ✅ Saved (total {processed})")
		except Exception as e:
			print(f"  ❌ Error writing row: {e}")

		# polite delay
		time.sleep(1)

	print(f"\nDone. Processed {processed} rows from {input_csv} → {output_csv}")


def main():
	parser = argparse.ArgumentParser(description="Analyze first_name.csv and append to full_name_with_analysis.csv")
	parser.add_argument('--input', default=INPUT_CSV, help='Input CSV path (default first_name.csv)')
	parser.add_argument('--output', default=OUTPUT_CSV, help='Output CSV path (default full_name_with_analysis.csv)')
	parser.add_argument('--limit', type=int, help='Limit number of entries to process')
	parser.add_argument('--force', action='store_true', help='Force reprocessing even if Name|email exists')
	args = parser.parse_args()

	if not os.path.exists(args.input):
		print(f"Error: {args.input} not found")
		return

	process_first_name_csv(args.input, args.output, args.limit, args.force)


if __name__ == '__main__':
	main()









