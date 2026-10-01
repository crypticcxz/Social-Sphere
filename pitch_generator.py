import os
import re
import json
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def generate_outreach_pitch_with_openai(scholar: dict) -> Optional[dict]:
    """Uses OpenAI GPT-4o-mini to draft an ultra-personalized, compelling cold outreach email."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        name = scholar.get("name", "Professor")
        institution = scholar.get("institution", "Academic Institution")
        citations = scholar.get("citations", 0)
        h_index = scholar.get("h_index", 0)
        wikipedia_url = scholar.get("wikipedia_url", "")
        has_wiki = bool(scholar.get("is_wiki") and wikipedia_url and wikipedia_url != "N/A")
        missing = scholar.get("missing_sections", [])
        if isinstance(missing, str):
            try: missing = json.loads(missing)
            except Exception: missing = [missing]
        summary = scholar.get("summary", "")

        prompt = f"""You are an elite academic communications and digital presence consultant. Write a professional, concise, respectful outreach email to Professor {name} (or their department chair/PR office) at {institution}.

Scholar Details:
- Name: {name}
- Institution: {institution}
- Citations: {citations:,}
- h-index: {h_index}
- Summary: {summary}
- Has Wikipedia Page: {'Yes' if has_wiki else 'No'}
- Wikipedia URL: {wikipedia_url if has_wiki else 'None'}
- Missing or Incomplete Sections: {', '.join(missing) if missing else 'None'}

Goal:
{'Propose creating a verified, notable Wikipedia biographical entry under WP:NPROF since their high citation count clearly meets academic notability standards.' if not has_wiki else 'Propose enhancing their existing Wikipedia article by adding missing critical sections (such as awards, research impact, and publications) so journalists and grant committees see an accurate record.'}

Format requirement:
Output JSON with exactly two fields:
{{
  "subject": "Compelling, professional subject line",
  "body": "The email body text including salutation and sign-off (Social Sphere Academic Relations Team)"
}}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You write elegant, high-converting academic outreach communications. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=600
        )

        content = response.choices[0].message.content
        res_json = json.loads(content)
        if "subject" in res_json and "body" in res_json:
            return {
                "subject": res_json["subject"],
                "recipient": scholar.get("email") or f"contact for {name}",
                "body": res_json["body"],
                "type": "ai_generated"
            }
    except Exception as e:
        print(f"OpenAI pitch generation fallback triggered: {e}")
        return None

def generate_outreach_pitch(scholar: dict, client_type: str = "creator") -> dict:
    # 1. Try OpenAI if configured
    ai_pitch = generate_outreach_pitch_with_openai(scholar)
    if ai_pitch:
        return ai_pitch

    # 2. High-quality rule-based fallback
    name = scholar.get("name", "Professor")
    institution = scholar.get("institution", "your institution")
    citations = scholar.get("citations", 0)
    h_index = scholar.get("h_index", 0)
    wikipedia_url = scholar.get("wikipedia_url", "")
    has_wiki = bool(scholar.get("is_wiki") and wikipedia_url and wikipedia_url != "N/A")
    email = scholar.get("email", "")
    missing_sections = scholar.get("missing_sections", [])
    if isinstance(missing_sections, str):
        try:
            missing_sections = json.loads(missing_sections)
        except Exception:
            missing_sections = [missing_sections]

    citations_str = f"{citations:,}" if citations else "thousands of"
    h_index_str = str(h_index) if h_index else "significant"

    if not has_wiki:
        subject = f"Wikipedia Profile Creation for Professor {name} — {institution}"
        body = f"""Dear Professor {name},

I hope this email finds you well.

I have been following your impactful research at {institution}. With {citations_str} scholarly citations and an h-index of {h_index_str}, your academic contributions unmistakably fulfill Wikipedia's Notability Guidelines for Academics (WP:NPROF).

However, while reviewing online academic directories, we noticed that you currently do not have a dedicated Wikipedia biography. A well-sourced Wikipedia article serves as a central knowledge reference for journalists, conference organizers, grant committees, and prospective graduate students looking up your laboratory and key discoveries.

Our academic communications team specializes in compiling peer-reviewed citations, academic appointments, and media mentions to build fully compliant, neutral Wikipedia biographies that adhere strictly to Wikipedia’s Conflict of Interest and Notability policies.

Would you or your communications department be open to a brief 10-minute introductory conversation this week to discuss creating an accurate, verified biography?

Sincerely,

Academic Relations & Digital Presence Team
Social Sphere Communications
"""
    else:
        missing_bullets = "\n".join([f"  • {sec}" for sec in missing_sections]) if missing_sections else "  • Recent Awards and Selected Publications\n  • Comprehensive Infobox and Early Career"
        subject = f"Enhancing the Wikipedia Biography for Professor {name} — Profile Audit"
        body = f"""Dear Professor {name},

I hope this note finds you well.

While reviewing top faculty profiles from {institution}, our research team performed a structural completeness audit of your Wikipedia page ({wikipedia_url}).

While it is great to see your presence on Wikipedia, our automated audit identified several notable omissions compared to standard biographies of leading researchers:

Missing or Incomplete Sections:
{missing_bullets}

Without these updated sections, key breakthroughs, lifetime awards, and recent major publications are overlooked by journalists, grant committees, and prospective collaborators who consult Wikipedia first.

We assist distinguished academics and university departments in updating and expanding existing Wikipedia pages in strict accordance with Wikipedia's neutral point of view (NPOV) and independent sourcing standards.

Would you be open to a quick 10-minute chat this week to review the audit and discuss bringing your page up to the highest biographical standard?

Best regards,

Academic Relations & Digital Presence Team
Social Sphere Communications
"""

    return {
        "subject": subject,
        "recipient": email or f"contact for {name}",
        "body": body,
        "type": "creation" if not has_wiki else "expansion"
    }

def audit_wikipedia_page_live(page_title_or_url: str) -> dict:
    """
    Queries MediaWiki API live to audit sections, warnings, and text.
    """
    title = page_title_or_url
    if "wikipedia.org/wiki/" in page_title_or_url:
        title = page_title_or_url.split("wikipedia.org/wiki/")[-1].replace("_", " ")

    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "format": "json",
        "page": title,
        "prop": "sections|templates",
        "redirects": 1
    }
    headers = {"User-Agent": "SocialSphereAcademicAuditor/1.0 (info@socialsphere.app)"}

    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if "error" in data:
            return {
                "success": False,
                "error": data["error"].get("info", "Page not found on Wikipedia")
            }

        parse = data.get("parse", {})
        actual_title = parse.get("title", title)
        sections = [s.get("line", "") for s in parse.get("sections", [])]
        templates = [t.get("*", "") for t in parse.get("templates", [])]

        standard_sections = {
            "Early Life & Education": ["early life", "education", "background", "childhood"],
            "Career & Academic Positions": ["career", "academic career", "appointments", "positions"],
            "Research & Discoveries": ["research", "work", "contributions", "scientific work"],
            "Awards & Honors": ["awards", "honors", "prizes", "fellowships", "recognition"],
            "Selected Publications": ["publications", "selected publications", "books", "bibliography", "papers"],
            "References & Citations": ["references", "sources", "notes"]
        }

        found_sections = []
        missing_sections = []

        all_sec_lower = " ".join([s.lower() for s in sections])

        for category, keywords in standard_sections.items():
            matched = any(k in all_sec_lower for k in keywords)
            if matched:
                found_sections.append(category)
            else:
                missing_sections.append(category)

        # Detect warnings
        warning_keywords = ["orphan", "unreferenced", "notability", "citation needed", "advert", "coi", "cleanup"]
        detected_warnings = []
        for t in templates:
            t_lower = t.lower()
            for w in warning_keywords:
                if w in t_lower and t not in detected_warnings:
                    detected_warnings.append(t)

        has_infobox = any("infobox" in t.lower() for t in templates)

        score = int((len(found_sections) / len(standard_sections)) * 70 + (20 if has_infobox else 0) + (10 if not detected_warnings else 0))

        return {
            "success": True,
            "title": actual_title,
            "wikipedia_url": f"https://en.wikipedia.org/wiki/{actual_title.replace(' ', '_')}",
            "sections": sections,
            "found_sections": found_sections,
            "missing_sections": missing_sections,
            "has_infobox": has_infobox,
            "warnings": detected_warnings[:5],
            "completeness_score": score,
            "recommendation": "Great profile, add missing sections" if score > 70 else "Needs significant expansion to meet academic guidelines."
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
