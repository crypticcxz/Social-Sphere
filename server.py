import os
import io
import csv
import json
import time
import sqlite3
import asyncio
from typing import Optional, List
from fastapi import FastAPI, Query, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from scanner_runner import scan_manager, run_live_scan_task
from pitch_generator import generate_outreach_pitch, audit_wikipedia_page_live

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "scholars.db")
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
os.makedirs(PUBLIC_DIR, exist_ok=True)

# Ensure DB exists
if not os.path.exists(DB_PATH):
    import build_database
    build_database.build()

app = FastAPI(
    title="Social Sphere — Academic Intelligence & Wikipedia Opportunity Engine",
    description="High-impact researcher lead generation, contact discovery, and Wikipedia completeness auditing.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ----------------- Models -----------------
class ScanRequest(BaseModel):
    query: str
    min_citations: int = 10000
    min_h_index: int = 40

class PitchRequest(BaseModel):
    scholar_id: Optional[int] = None
    name: Optional[str] = None
    institution: Optional[str] = None
    citations: Optional[int] = 0
    h_index: Optional[int] = 0
    wikipedia_url: Optional[str] = ""
    is_wiki: Optional[int] = 0
    email: Optional[str] = ""
    missing_sections: Optional[List[str]] = []

class LiveAuditRequest(BaseModel):
    query: str

# ----------------- Endpoints -----------------

@app.get("/api/stats")
def get_stats():
    """Returns high-level KPI metrics and institution distributions."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM scholars")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scholars WHERE email IS NOT NULL AND email != '' AND email != 'Not found'")
    with_email = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scholars WHERE is_wiki = 1")
    with_wiki = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scholars WHERE is_wiki = 0")
    wiki_opps = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scholars WHERE missing_sections != '[]' AND missing_sections IS NOT NULL")
    missing_sections_count = cur.fetchone()[0]

    cur.execute("SELECT AVG(citations) FROM scholars WHERE citations > 0")
    avg_citations = int(cur.fetchone()[0] or 0)

    cur.execute("""
        SELECT institution, COUNT(*) as cnt 
        FROM scholars 
        GROUP BY institution 
        ORDER BY cnt DESC 
        LIMIT 10
    """)
    top_institutions = {row["institution"]: row["cnt"] for row in cur.fetchall()}

    conn.close()

    return {
        "total_scholars": total,
        "with_email": with_email,
        "with_wiki": with_wiki,
        "wiki_opportunities": wiki_opps,
        "with_missing_sections": missing_sections_count,
        "avg_citations": avg_citations,
        "top_institutions": top_institutions
    }

@app.get("/api/institutions")
def get_institutions():
    """Returns list of distinct universities / institutions for filter dropdown."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT institution, COUNT(*) as cnt 
        FROM scholars 
        GROUP BY institution 
        HAVING cnt >= 5 
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"name": r["institution"], "count": r["cnt"]} for r in rows]

@app.get("/api/scholars")
def get_scholars(
    q: Optional[str] = None,
    institution: Optional[str] = None,
    wiki_status: str = "all", # all, has_wiki, missing_wiki
    email_status: str = "all", # all, has_email, missing_email
    missing_section: Optional[str] = None,
    min_citations: int = 0,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    sort_by: str = "citations", # citations, name, institution
    sort_dir: str = "desc" # asc, desc
):
    """Filter, search, and paginate academic scholar profiles."""
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []

    if q:
        q_term = f"%{q.strip()}%"
        conditions.append("(name LIKE ? OR email LIKE ? OR institution LIKE ? OR summary LIKE ?)")
        params.extend([q_term, q_term, q_term, q_term])

    if institution and institution != "all":
        conditions.append("institution = ?")
        params.append(institution)

    if wiki_status == "has_wiki":
        conditions.append("is_wiki = 1")
    elif wiki_status == "missing_wiki":
        conditions.append("is_wiki = 0")

    if email_status == "has_email":
        conditions.append("email IS NOT NULL AND email != '' AND email != 'Not found'")
    elif email_status == "missing_email":
        conditions.append("(email IS NULL OR email = '' OR email = 'Not found')")

    if missing_section and missing_section != "all":
        conditions.append("missing_sections LIKE ?")
        params.append(f"%{missing_section}%")

    if min_citations > 0:
        conditions.append("citations >= ?")
        params.append(min_citations)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Count total
    cur.execute(f"SELECT COUNT(*) FROM scholars {where_clause}", params)
    total_matching = cur.fetchone()[0]

    # Validate sort
    allowed_sorts = {
        "citations": "citations",
        "name": "name",
        "institution": "institution",
        "h_index": "h_index"
    }
    col_sort = allowed_sorts.get(sort_by, "citations")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    offset = (page - 1) * limit
    query_sql = f"""
        SELECT id, name, email, institution, wikipedia_url, is_wiki, summary, 
               missing_sections, warnings, assessment, citations, h_index, scholar_url 
        FROM scholars 
        {where_clause} 
        ORDER BY {col_sort} {direction} 
        LIMIT ? OFFSET ?
    """
    cur.execute(query_sql, params + [limit, offset])
    rows = cur.fetchall()

    scholars = []
    for r in rows:
        missing = []
        try:
            missing = json.loads(r["missing_sections"]) if r["missing_sections"] else []
        except Exception:
            missing = [r["missing_sections"]]

        scholars.append({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"] or "",
            "institution": r["institution"] or "Independent",
            "wikipedia_url": r["wikipedia_url"] or "",
            "is_wiki": bool(r["is_wiki"]),
            "summary": r["summary"] or "",
            "missing_sections": missing,
            "warnings": r["warnings"] or "",
            "assessment": r["assessment"] or "",
            "citations": r["citations"] or 0,
            "h_index": r["h_index"] or 0,
            "scholar_url": r["scholar_url"] or ""
        })

    conn.close()

    total_pages = (total_matching + limit - 1) // limit

    return {
        "page": page,
        "limit": limit,
        "total": total_matching,
        "total_pages": total_pages,
        "scholars": scholars
    }

@app.get("/api/scholars/{scholar_id}")
def get_scholar_detail(scholar_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scholars WHERE id = ?", (scholar_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Scholar not found")

    missing = []
    try:
        missing = json.loads(row["missing_sections"]) if row["missing_sections"] else []
    except Exception:
        missing = [row["missing_sections"]]

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"] or "",
        "institution": row["institution"],
        "wikipedia_url": row["wikipedia_url"] or "",
        "is_wiki": bool(row["is_wiki"]),
        "summary": row["summary"] or "",
        "missing_sections": missing,
        "warnings": row["warnings"] or "",
        "assessment": row["assessment"] or "",
        "citations": row["citations"] or 0,
        "h_index": row["h_index"] or 0,
        "scholar_url": row["scholar_url"] or ""
    }

@app.post("/api/scan/start")
def start_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    """Starts a live academic scraping & enrichment task asynchronously in the background."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    scan_id = f"scan_{int(time.time())}"
    scan_manager.create_scan(scan_id, query, req.min_citations, req.min_h_index)

    # Dispatch to background task runner (will not timeout or block API!)
    background_tasks.add_task(
        run_live_scan_task,
        scan_id,
        query,
        req.min_citations,
        req.min_h_index
    )

    return {
        "status": "started",
        "scan_id": scan_id,
        "message": f"Scan initiated for '{query}'. Monitor live logs at /api/scan/status/{scan_id}"
    }

@app.get("/api/scan/status/{scan_id}")
def get_scan_status(scan_id: str):
    """Poll the status, progress, logs, and found leads of a running scan."""
    scan = scan_manager.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan

@app.get("/api/scan/logs/{scan_id}")
async def stream_scan_logs(scan_id: str):
    """Server-Sent Events (SSE) endpoint to stream live logs to the browser terminal."""
    scan = scan_manager.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    async def event_generator():
        last_index = 0
        while True:
            current_scan = scan_manager.get_scan(scan_id)
            if not current_scan:
                break
            logs = current_scan.get("logs", [])
            if last_index < len(logs):
                for log_item in logs[last_index:]:
                    yield f"data: {json.dumps(log_item)}\n\n"
                last_index = len(logs)

            if current_scan["status"] in ["completed", "error"]:
                yield f"data: {json.dumps({'time': time.strftime('%H:%M:%S'), 'msg': 'END_OF_STREAM', 'level': 'info', 'status': current_scan['status']})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/pitch/generate")
def generate_pitch(req: PitchRequest):
    """Generates personalized Wikipedia outreach pitch (Creation or Expansion)."""
    scholar_dict = {}
    if req.scholar_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM scholars WHERE id = ?", (req.scholar_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            missing = []
            try:
                missing = json.loads(row["missing_sections"])
            except Exception:
                missing = []
            scholar_dict = {
                "name": row["name"],
                "institution": row["institution"],
                "citations": row["citations"],
                "h_index": row["h_index"],
                "wikipedia_url": row["wikipedia_url"],
                "is_wiki": row["is_wiki"],
                "email": row["email"],
                "missing_sections": missing
            }

    if not scholar_dict:
        scholar_dict = req.model_dump()

    pitch = generate_outreach_pitch(scholar_dict)
    return pitch

@app.post("/api/wiki/audit-live")
def live_wiki_audit(req: LiveAuditRequest):
    """Audits any researcher's live Wikipedia page structure via MediaWiki."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    result = audit_wikipedia_page_live(query)
    return result

@app.get("/api/export")
def export_scholars_csv(
    q: Optional[str] = None,
    institution: Optional[str] = None,
    wiki_status: str = "all",
    email_status: str = "all",
    missing_section: Optional[str] = None,
    min_citations: int = 0
):
    """Exports filtered scholars into a clean, downloadable CSV file."""
    conn = get_db()
    cur = conn.cursor()

    conditions = []
    params = []

    if q:
        q_term = f"%{q.strip()}%"
        conditions.append("(name LIKE ? OR email LIKE ? OR institution LIKE ? OR summary LIKE ?)")
        params.extend([q_term, q_term, q_term, q_term])

    if institution and institution != "all":
        conditions.append("institution = ?")
        params.append(institution)

    if wiki_status == "has_wiki":
        conditions.append("is_wiki = 1")
    elif wiki_status == "missing_wiki":
        conditions.append("is_wiki = 0")

    if email_status == "has_email":
        conditions.append("email IS NOT NULL AND email != '' AND email != 'Not found'")
    elif email_status == "missing_email":
        conditions.append("(email IS NULL OR email = '' OR email = 'Not found')")

    if missing_section and missing_section != "all":
        conditions.append("missing_sections LIKE ?")
        params.append(f"%{missing_section}%")

    if min_citations > 0:
        conditions.append("citations >= ?")
        params.append(min_citations)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cur.execute(f"""
        SELECT name, email, institution, citations, h_index, wikipedia_url, is_wiki, missing_sections, summary 
        FROM scholars 
        {where_clause} 
        ORDER BY citations DESC 
        LIMIT 5000
    """, params)
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Institution", "Citations", "h_index", "Wikipedia_URL", "Has_Wikipedia", "Missing_Sections", "Summary"])

    for r in rows:
        missing_str = ""
        try:
            m_list = json.loads(r["missing_sections"])
            missing_str = "; ".join(m_list)
        except Exception:
            missing_str = r["missing_sections"] or ""

        writer.writerow([
            r["name"],
            r["email"] or "Not found",
            r["institution"],
            r["citations"],
            r["h_index"],
            r["wikipedia_url"] or "N/A",
            "Yes" if r["is_wiki"] else "No",
            missing_str,
            r["summary"]
        ])

    output.seek(0)
    filename = f"social_sphere_scholars_{int(time.time())}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Mount public directory for frontend
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Social Sphere server on http://localhost:{port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
