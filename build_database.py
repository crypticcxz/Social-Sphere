import csv
import os
import re
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "scholars.db")

DOMAIN_TO_INSTITUTION = {
    "harvard.edu": "Harvard University",
    "mit.edu": "Massachusetts Institute of Technology",
    "stanford.edu": "Stanford University",
    "princeton.edu": "Princeton University",
    "yale.edu": "Yale University",
    "uchicago.edu": "University of Chicago",
    "northwestern.edu": "Northwestern University",
    "nyu.edu": "New York University",
    "ucdavis.edu": "UC Davis",
    "columbia.edu": "Columbia University",
    "manchester.ac.uk": "University of Manchester",
    "msu.edu": "Michigan State University",
    "berkeley.edu": "UC Berkeley",
    "ucla.edu": "UCLA",
    "wustl.edu": "Washington University in St. Louis",
    "cam.ac.uk": "University of Cambridge",
    "ox.ac.uk": "University of Oxford",
    "cornell.edu": "Cornell University",
    "cmu.edu": "Carnegie Mellon University",
    "upenn.edu": "University of Pennsylvania",
    "umich.edu": "University of Michigan",
    "caltech.edu": "California Institute of Technology",
    "uw.edu": "University of Washington",
    "illinois.edu": "University of Illinois",
    "jhu.edu": "Johns Hopkins University",
    "duke.edu": "Duke University",
}

def clean_text(s: str) -> str:
    if not s:
        return ""
    # Remove unicode formatting artifacts
    s = re.sub(r'[\u202a\u202c\u202b\u200e\u200f]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def extract_domain(email: str) -> str:
    if not email or "@" not in email or email.lower() == "not found":
        return ""
    parts = email.split("@")
    if len(parts) > 1:
        return parts[-1].lower().strip()
    return ""

def guess_institution(email: str, text: str = "") -> str:
    domain = extract_domain(email)
    for dom, inst in DOMAIN_TO_INSTITUTION.items():
        if domain == dom or domain.endswith("." + dom):
            return inst
    
    # Check domain format (e.g., xxx.edu -> capitalize name)
    if domain.endswith(".edu"):
        base = domain.replace(".edu", "").split(".")[-1]
        return base.upper() if len(base) <= 4 else base.capitalize() + " University"
    if domain.endswith(".ac.uk"):
        base = domain.replace(".ac.uk", "").split(".")[-1]
        return base.capitalize() + " University"
        
    # Text hints
    if text:
        text_lower = text.lower()
        for dom, inst in DOMAIN_TO_INSTITUTION.items():
            if inst.lower() in text_lower:
                return inst

    return "Other / Independent"

def parse_info_field(info: str):
    """
    Parses fields from info string like:
    SUMMARY: ... MISSING: ... WARNINGS: ... ASSESSMENT: ...
    """
    if not info:
        return {"summary": "", "missing": [], "warnings": "", "assessment": ""}
    
    summary = ""
    missing = []
    warnings = ""
    assessment = ""
    
    # Check if structured
    if "SUMMARY:" in info or "MISSING:" in info or "ASSESSMENT:" in info:
        m_sum = re.search(r'SUMMARY:\s*(.*?)(?=\s*MISSING:|\s*WARNINGS:|\s*ASSESSMENT:|$)', info, re.DOTALL)
        if m_sum:
            summary = clean_text(m_sum.group(1))
            
        m_miss = re.search(r'MISSING:\s*(.*?)(?=\s*WARNINGS:|\s*ASSESSMENT:|$)', info, re.DOTALL)
        if m_miss:
            miss_raw = clean_text(m_miss.group(1))
            # Known standard section names
            standard_sections = [
                "Introduction Paragraph",
                "Early Life & Education",
                "Early Life and Education",
                "Early Life & Education section",
                "Career Section",
                "Career",
                "Research Section",
                "Research",
                "Awards & Honors Section",
                "Awards & Honors",
                "Selected Publications section",
                "Selected Publications",
                "Publications",
                "Books (if available)",
                "Books",
                "References",
                "InfoBox",
                "Infobox with photo"
            ]
            for sec in standard_sections:
                if sec.lower() in miss_raw.lower():
                    # canonical name
                    canon = sec.replace(" section", "").replace(" (if available)", "")
                    if canon == "Early Life & Education": canon = "Early Life and Education"
                    if canon not in missing:
                        missing.append(canon)
            if not missing and miss_raw and miss_raw.lower() != "none":
                missing = [miss_raw]
                
        m_warn = re.search(r'WARNINGS:\s*(.*?)(?=\s*ASSESSMENT:|$)', info, re.DOTALL)
        if m_warn:
            warnings = clean_text(m_warn.group(1))
            
        m_assess = re.search(r'ASSESSMENT:\s*(.*?)$', info, re.DOTALL)
        if m_assess:
            assessment = clean_text(m_assess.group(1))
    else:
        summary = clean_text(info)
        
    return {
        "summary": summary,
        "missing": missing,
        "warnings": warnings,
        "assessment": assessment
    }

def build():
    print("Building consolidated scholars database...")
    profiles = {}

    # 1. Load citations / h_index from qualified_profiles.csv
    citations_map = {}
    qp_path = os.path.join(BASE_DIR, "qualified_profiles.csv")
    if os.path.exists(qp_path):
        with open(qp_path, "r", encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                nm = clean_text(row.get("name", "")).lower()
                if nm:
                    try:
                        c = int(row.get("citations", 0) or 0)
                        h = int(row.get("h_index", 0) or 0)
                        citations_map[nm] = {
                            "citations": c,
                            "h_index": h,
                            "profile_url": row.get("profile_url", "")
                        }
                    except ValueError:
                        pass

    # Files to process
    sources = [
        (os.path.join(BASE_DIR, "social_sphere", "full_name_with_analysis.csv"), "full_analysis"),
        (os.path.join(BASE_DIR, "wiki_check", "qualified_scholar_profiles_with_wikipedia.csv"), "wiki_verified"),
        (os.path.join(BASE_DIR, "wiki_check", "qualified_scholar_profiles_without_wikipedia.csv"), "no_wiki_verified"),
        (os.path.join(BASE_DIR, "wiki_check", "without_email.csv"), "no_email"),
    ]

    for fpath, tag in sources:
        if not os.path.exists(fpath):
            print(f"Skipping missing file: {fpath}")
            continue
        print(f"Ingesting: {fpath} ({tag})")
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = clean_text(row.get("Name") or row.get("name") or "")
                if not name or len(name) < 2:
                    continue
                
                key = name.lower()
                email = clean_text(row.get("email") or "")
                wiki_url = clean_text(row.get("wikipedia_url") or "")
                if wiki_url.lower() in ["n/a", "none", "not found"]:
                    wiki_url = ""
                
                is_wiki = row.get("is_wiki", "0") == "1" or bool(wiki_url.startswith("http"))
                info = row.get("info") or ""
                
                parsed_info = parse_info_field(info)
                
                # Check citations map
                metrics = citations_map.get(key, {})
                citations = metrics.get("citations", 0)
                h_index = metrics.get("h_index", 0)
                scholar_url = metrics.get("profile_url", "")

                if key not in profiles:
                    profiles[key] = {
                        "name": name,
                        "email": email if email.lower() != "not found" else "",
                        "wikipedia_url": wiki_url,
                        "is_wiki": 1 if is_wiki else 0,
                        "summary": parsed_info["summary"],
                        "missing_sections": parsed_info["missing"],
                        "warnings": parsed_info["warnings"],
                        "assessment": parsed_info["assessment"],
                        "citations": citations,
                        "h_index": h_index,
                        "scholar_url": scholar_url,
                        "tags": [tag]
                    }
                else:
                    # Update fields if new data is richer
                    existing = profiles[key]
                    if not existing["email"] and email and email.lower() != "not found":
                        existing["email"] = email
                    if not existing["wikipedia_url"] and wiki_url:
                        existing["wikipedia_url"] = wiki_url
                        existing["is_wiki"] = 1
                    if len(parsed_info["summary"]) > len(existing["summary"]):
                        existing["summary"] = parsed_info["summary"]
                    if parsed_info["missing"]:
                        for m in parsed_info["missing"]:
                            if m not in existing["missing_sections"]:
                                existing["missing_sections"].append(m)
                    if not existing["assessment"] and parsed_info["assessment"]:
                        existing["assessment"] = parsed_info["assessment"]
                    if not existing["warnings"] and parsed_info["warnings"]:
                        existing["warnings"] = parsed_info["warnings"]
                    if not existing["citations"] and citations:
                        existing["citations"] = citations
                        existing["h_index"] = h_index
                        existing["scholar_url"] = scholar_url
                    if tag not in existing["tags"]:
                        existing["tags"].append(tag)

    print(f"Total unique consolidated scholars: {len(profiles)}")

    # Add institution derived from email and summary
    scholars_list = []
    for idx, (k, p) in enumerate(profiles.items(), 1):
        inst = guess_institution(p["email"], p["summary"])
        scholars_list.append({
            "id": idx,
            "name": p["name"],
            "email": p["email"],
            "institution": inst,
            "wikipedia_url": p["wikipedia_url"],
            "is_wiki": p["is_wiki"],
            "summary": p["summary"],
            "missing_sections": p["missing_sections"],
            "warnings": p["warnings"],
            "assessment": p["assessment"],
            "citations": p["citations"],
            "h_index": p["h_index"],
            "scholar_url": p["scholar_url"],
            "tags": p["tags"]
        })

    # Save to SQLite for high performance and low memory
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE scholars (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        institution TEXT,
        wikipedia_url TEXT,
        is_wiki INTEGER,
        summary TEXT,
        missing_sections TEXT,
        warnings TEXT,
        assessment TEXT,
        citations INTEGER,
        h_index INTEGER,
        scholar_url TEXT,
        tags TEXT
    )
    """)

    cur.execute("CREATE INDEX idx_name ON scholars(name)")
    cur.execute("CREATE INDEX idx_institution ON scholars(institution)")
    cur.execute("CREATE INDEX idx_is_wiki ON scholars(is_wiki)")
    cur.execute("CREATE INDEX idx_email ON scholars(email)")
    cur.execute("CREATE INDEX idx_citations ON scholars(citations)")

    rows_to_insert = [
        (
            s["id"],
            s["name"],
            s["email"],
            s["institution"],
            s["wikipedia_url"],
            s["is_wiki"],
            s["summary"],
            json.dumps(s["missing_sections"]),
            s["warnings"],
            s["assessment"],
            s["citations"],
            s["h_index"],
            s["scholar_url"],
            json.dumps(s["tags"])
        )
        for s in scholars_list
    ]

    cur.executemany("""
    INSERT INTO scholars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows_to_insert)

    conn.commit()
    conn.close()

    # Also save a lightweight stats summary JSON for instant loads
    stats = {
        "total_scholars": len(scholars_list),
        "with_email": sum(1 for s in scholars_list if s["email"]),
        "with_wiki": sum(1 for s in scholars_list if s["is_wiki"]),
        "wiki_opportunities": sum(1 for s in scholars_list if not s["is_wiki"]),
        "with_missing_sections": sum(1 for s in scholars_list if s["missing_sections"]),
        "top_institutions": {}
    }

    inst_counter = {}
    for s in scholars_list:
        inst = s["institution"]
        inst_counter[inst] = inst_counter.get(inst, 0) + 1
    
    sorted_inst = sorted(inst_counter.items(), key=lambda x: x[1], reverse=True)[:10]
    stats["top_institutions"] = dict(sorted_inst)

    with open(os.path.join(DATA_DIR, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print(f"[OK] Successfully created SQLite database at {DB_PATH}")
    print(f"Stats: {stats}")

if __name__ == "__main__":
    build()
