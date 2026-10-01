# Social Sphere — Academic Lead & Wikipedia Intelligence Platform

Social Sphere is a full-stack academic intelligence platform that discovers high-impact researchers, extracts verified contact emails, checks Wikipedia completeness, and automates cold-outreach pitches.

---

## 🚀 Live Demo & Key Capabilities

1. **Executive Scholar CRM**:
   - Pre-indexed database of **6,445+ top scholars** from MIT, Harvard, Stanford, Princeton, Yale, and more.
   - Filter by **Wikipedia Status** (*Missing Page / High Opportunity* vs. *Has Page*), **Email Availability**, and **Institution**.
   - Audit missing sections (*Awards & Honors*, *Selected Publications*, *Career*, *Infobox*).

2. **Live Background Scanner**:
   - Launch real-time scraping queries (e.g. *"Stanford Artificial Intelligence"*, *"Harvard Genetics"*).
   - Real-time terminal log viewer streaming results via Server-Sent Events (SSE).
   - Multi-source fallback (Google Scholar CSE $\rightarrow$ OpenAlex API $\rightarrow$ MediaWiki $\rightarrow$ Email Crawler).

3. **Wikipedia Completeness Auditor**:
   - Live MediaWiki API integration to audit any Wikipedia article in real time.
   - Generates completeness score (0-100), detects Wikipedia cleanup/warning tags, and flags missing sections.

4. **Outreach Pitch Generator**:
   - 1-click personalized email proposal generator for Wikipedia page creation or expansion.
   - Direct `mailto:` action and 1-click clipboard copy.

5. **Filtered Lead Export**:
   - Download filtered scholar leads directly as CSV for outreach campaigns.

---

## 💻 Running Locally

### 1. Requirements
- Python 3.9+

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Build & Index the Database (already pre-built)
```bash
python build_database.py
```

### 4. Start the Application
```bash
python server.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🌐 Deploy Live with $0 Cost (Render.com)

You can host this entire web app (FastAPI backend + frontend + background scanner) on **Render.com** with **$0 cost** and zero credit card required.

### 3-Step Free Deployment:
1. **Push your project to GitHub**:
   ```bash
   git add .
   git commit -m "Social Sphere full-stack app"
   git push origin main
   ```
2. **Go to [Render.com](https://render.com/)**:
   - Click **New +** $\rightarrow$ **Web Service**.
   - Select your GitHub repository.
   - Fill in:
     - **Name**: `social-sphere`
     - **Environment**: `Python 3`
     - **Build Command**: `pip install -r requirements.txt && python build_database.py`
     - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
     - **Instance Type**: Select **Free ($0/month)**.
3. **Add Environment Variables** (Optional):
   - Under **Environment Variables**, add:
     - `OPENAI_API_KEY`: Your OpenAI API key (for GPT-4o-mini custom pitch generation & AI summaries)
     - `GOOGLE_API_KEY`: Your Google API key (if using Google Scholar CSE)
     - `GOOGLE_SCHOLAR_CSE_ID`: Your Scholar CSE ID
     - `GOOGLE_GENERAL_CSE_ID`: Your General CSE ID
     - *(Note: The scanner and pitch generator include automatic fallbacks to OpenAlex + MediaWiki + structured templates, so the app still functions even if API keys are omitted!)*
4. Click **Deploy Web Service**!
   Your live application will be available at `https://social-sphere.onrender.com`.

---

## 📁 Project Architecture

```
Social Sphere/
├── server.py              # FastAPI server (search, background scans, pitch, export)
├── scanner_runner.py      # Background worker with OpenAlex & Google CSE fallbacks
├── pitch_generator.py     # Outreach email generator & live MediaWiki auditor
├── build_database.py      # Consolidates 7,000+ CSV records into SQLite
├── data/
│   ├── scholars.db        # High-performance SQLite database
│   └── stats.json         # Instant cached KPI metrics
├── public/
│   ├── index.html         # Responsive, glassmorphic UI
│   ├── style.css          # Modern dark-mode vanilla CSS design system
│   └── app.js             # Client state, table rendering, live SSE terminal
├── render.yaml            # 1-click Render blueprint
├── Procfile               # Cloud process command
└── requirements.txt       # Production dependencies
```
