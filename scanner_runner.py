import os
import re
import sys
import time
import json
import sqlite3
import requests
from typing import Dict, List, Optional, Callable
from dotenv import load_dotenv

# Load env variables from root or wiki_check
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "wiki_check", ".env"))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = os.getenv("GOOGLE_API_KEY")
SCHOLAR_CSE_ID = os.getenv("GOOGLE_SCHOLAR_CSE_ID") or os.getenv("GOOGLE_CSE_ID")
GENERAL_CSE_ID = os.getenv("GOOGLE_GENERAL_CSE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

DB_PATH = os.path.join(BASE_DIR, "data", "scholars.db")

class ScanManager:
    def __init__(self):
        self.scans: Dict[str, dict] = {}

    def create_scan(self, scan_id: str, query: str, min_citations: int = 10000, min_h_index: int = 40):
        self.scans[scan_id] = {
            "id": scan_id,
            "query": query,
            "min_citations": min_citations,
            "min_h_index": min_h_index,
            "status": "starting", # starting, running, completed, error
            "progress": 0,
            "total_items": 0,
            "processed_items": 0,
            "found_scholars": [],
            "logs": [],
            "created_at": time.time()
        }

    def add_log(self, scan_id: str, message: str, level: str = "info"):
        if scan_id in self.scans:
            timestamp = time.strftime("%H:%M:%S")
            self.scans[scan_id]["logs"].append({
                "time": timestamp,
                "msg": message,
                "level": level
            })
            # Keep max 500 logs per scan
            if len(self.scans[scan_id]["logs"]) > 500:
                self.scans[scan_id]["logs"].pop(0)

    def update_progress(self, scan_id: str, progress: int, status: Optional[str] = None):
        if scan_id in self.scans:
            self.scans[scan_id]["progress"] = progress
            if status:
                self.scans[scan_id]["status"] = status

    def add_result(self, scan_id: str, scholar: dict):
        if scan_id in self.scans:
            self.scans[scan_id]["found_scholars"].append(scholar)

    def get_scan(self, scan_id: str) -> Optional[dict]:
        return self.scans.get(scan_id)

scan_manager = ScanManager()

def clean_name(title: str) -> str:
    name = re.sub(r'[\u202a\u202c\u202b\u200e\u200f‪‬]', '', title)
    name = re.sub(r'\s*-\s*Google Scholar.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Google Scholar.*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*-\s*$', '', name).strip()
    return name or "Unknown"

def extract_metrics(snippet: str) -> Dict[str, Optional[int]]:
    metrics = {"citations": None, "h_index": None}
    c_match = re.search(r"(?:Citations?|Cited by)\s*[,:]\s*([0-9][0-9,]*)", snippet, re.IGNORECASE)
    if c_match:
        try:
            metrics["citations"] = int(c_match.group(1).replace(",", ""))
        except ValueError:
            pass
    h_match = re.search(r"h-index\s*[,:]\s*([0-9]+)", snippet, re.IGNORECASE)
    if h_match:
        try:
            metrics["h_index"] = int(h_match.group(1))
        except ValueError:
            pass
    return metrics

def fetch_wikipedia_page(name: str) -> Dict[str, str]:
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": name,
        "utf8": 1,
        "srlimit": 1
    }
    headers = {"User-Agent": "SocialSphereAcademicScanner/1.0 (contact: info@socialsphere.app)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            search = data.get("query", {}).get("search", [])
            if search:
                title = search[0]["title"]
                # Basic check if title corresponds reasonably
                return {
                    "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                    "title": title
                }
    except Exception:
        pass
    return {"url": "", "title": ""}

def search_email_heuristic(name: str, api_key: str, cx_id: str, logger: Callable) -> str:
    if not api_key or not cx_id:
        return "Not found"
    url = "https://www.googleapis.com/customsearch/v1"
    query = f'"{name}" email'
    params = {"key": api_key, "cx": cx_id, "q": query, "num": 3}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            items = r.json().get("items", [])
            for it in items:
                text = (it.get("title", "") + " " + it.get("snippet", ""))
                match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', text)
                if match:
                    email = match.group(0)
                    if not any(email.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif"]):
                        return email
    except Exception as e:
        logger(f"Email search error: {e}", "warning")
    return "Not found"

def run_live_scan_task(scan_id: str, query: str, min_citations: int, min_h_index: int):
    """
    Background worker that runs the query search, extraction, qualification, and database insertion.
    """
    def log(msg: str, lvl: str = "info"):
        scan_manager.add_log(scan_id, msg, lvl)
        print(f"[{scan_id}] {msg}")

    log(f"Initiating scan for: '{query}' (Threshold: citations>={min_citations}, h-index>={min_h_index})")
    scan_manager.update_progress(scan_id, 10, "running")

    api_key = API_KEY or os.getenv("GOOGLE_API_KEY")
    scholar_cx = SCHOLAR_CSE_ID or os.getenv("GOOGLE_SCHOLAR_CSE_ID")
    general_cx = GENERAL_CSE_ID or os.getenv("GOOGLE_GENERAL_CSE_ID")

    items = []

    # Strategy 1: Google Custom Search API if configured
    if api_key and scholar_cx:
        log("Searching Google Scholar via Custom Search API...")
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": api_key,
                "cx": scholar_cx,
                "q": f'{query} "citations" "h-index"',
                "num": 10
            }
            r = requests.get(url, params=params, timeout=15)
            if r.status_code == 200:
                res = r.json()
                items = res.get("items", [])
                log(f"Retrieved {len(items)} profile candidates from Google Scholar CSE.")
            else:
                log(f"Google CSE returned status {r.status_code}: {r.text[:120]}", "warning")
        except Exception as e:
            log(f"Google CSE error: {e}", "warning")

    # Strategy 2: OpenAlex fallback if items are empty
    if not items:
        log("Querying OpenAlex Academic API fallback...")
        try:
            oa_url = "https://api.openalex.org/authors"
            params = {
                "search": query,
                "per-page": 10,
                "sort": "cited_by_count:desc"
            }
            r = requests.get(oa_url, params=params, timeout=12, headers={"User-Agent": "SocialSphere/1.0"})
            if r.status_code == 200:
                oa_data = r.json()
                oa_results = oa_data.get("results", [])
                log(f"Retrieved {len(oa_results)} authors from OpenAlex.")
                for auth in oa_results:
                    name = auth.get("display_name", "")
                    citations = auth.get("cited_by_count", 0)
                    h_index = auth.get("summary_stats", {}).get("h_index", 0)
                    insts = auth.get("affiliations", [])
                    inst_name = insts[0].get("institution", {}).get("display_name", "Academic Institution") if insts else "Academic Institution"
                    
                    items.append({
                        "title": f"{name} - {inst_name}",
                        "snippet": f"Citations: {citations}, h-index: {h_index}. Affiliation: {inst_name}",
                        "link": auth.get("id", ""),
                        "_oa_metrics": {"citations": citations, "h_index": h_index, "institution": inst_name}
                    })
        except Exception as e:
            log(f"OpenAlex fallback error: {e}", "error")

    total_candidates = len(items)
    scan_manager.scans[scan_id]["total_items"] = total_candidates
    scan_manager.update_progress(scan_id, 30)

    if total_candidates == 0:
        log("No candidate profiles returned from APIs. Please verify your API key or query.", "warning")
        scan_manager.update_progress(scan_id, 100, "completed")
        return

    qualifying_scholars = []

    for i, it in enumerate(items, 1):
        title = it.get("title", "")
        snippet = it.get("snippet", "")
        link = it.get("link", "")
        progress = int(30 + (i / total_candidates) * 60)
        scan_manager.update_progress(scan_id, progress)

        oa_metrics = it.get("_oa_metrics")
        if oa_metrics:
            citations = oa_metrics["citations"]
            h_index = oa_metrics["h_index"]
            institution = oa_metrics["institution"]
        else:
            extracted = extract_metrics(snippet)
            citations = extracted["citations"] or 0
            h_index = extracted["h_index"] or 0
            institution = "University Faculty"

        name = clean_name(title)
        log(f"[{i}/{total_candidates}] Analyzing {name}: {citations} citations, h-index {h_index}")

        # Check qualification
        if citations >= min_citations and (min_h_index == 0 or h_index >= min_h_index):
            log(f"-> QUALIFIED: {name} exceeds thresholds!", "success")
            
            # Wikipedia search
            wiki = fetch_wikipedia_page(name)
            wiki_url = wiki["url"]
            if wiki_url:
                log(f"   Wikipedia page found: {wiki_url}")
            else:
                log(f"   No Wikipedia page found (Opportunity!)")

            # Email search
            email = "Not found"
            if api_key and general_cx:
                email = search_email_heuristic(name, api_key, general_cx, log)
                if email and email != "Not found":
                    log(f"   Email discovered: {email}")

            scholar_entry = {
                "name": name,
                "citations": citations,
                "h_index": h_index,
                "email": email if email != "Not found" else "",
                "institution": institution,
                "wikipedia_url": wiki_url,
                "is_wiki": 1 if wiki_url else 0,
                "scholar_url": link,
                "summary": f"{name} is an academic researcher with {citations:,} citations and an h-index of {h_index}.",
                "missing_sections": [] if wiki_url else ["Complete Article Needed"],
                "warnings": "",
                "assessment": "High impact scholar."
            }

            qualifying_scholars.append(scholar_entry)
            scan_manager.add_result(scan_id, scholar_entry)
        else:
            log(f"-> Skipped {name} (citations={citations} < {min_citations})")

        time.sleep(0.3)

    # Save newly qualified scholars into database
    if qualifying_scholars:
        log(f"Saving {len(qualifying_scholars)} newly qualified scholars to database...")
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            for s in qualifying_scholars:
                # Check duplicate by name
                cur.execute("SELECT id FROM scholars WHERE LOWER(name) = LOWER(?)", (s["name"],))
                row = cur.fetchone()
                if not row:
                    cur.execute("""
                        INSERT INTO scholars (
                            name, email, institution, wikipedia_url, is_wiki,
                            summary, missing_sections, warnings, assessment,
                            citations, h_index, scholar_url, tags
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        s["name"], s["email"], s["institution"], s["wikipedia_url"], s["is_wiki"],
                        s["summary"], json.dumps(s["missing_sections"]), s["warnings"], s["assessment"],
                        s["citations"], s["h_index"], s["scholar_url"], json.dumps(["live_scan"])
                    ))
            conn.commit()
            conn.close()
            log("Database successfully updated with new profiles!", "success")
        except Exception as e:
            log(f"Database save error: {e}", "error")

    scan_manager.update_progress(scan_id, 100, "completed")
    log(f"Scan finished! Qualified {len(qualifying_scholars)} new scholar leads.")
