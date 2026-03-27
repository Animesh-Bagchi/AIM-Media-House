"""
Agent 4 – Report Generator
Produces a 1000-word yearly summary for each year in the channel's history,
then renders a single HTML report (with optional PDF export).
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, BaseLoader

from agents.base_agent import BaseAgent
from database import manager as db
from config import REPORTS_DIR
from utils.helpers import truncate_to_words

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are an AI research analyst writing an annual review of the AIM Media House YouTube channel.

Year: {year}
Total videos published: {video_count}

Top entities mentioned this year:
{top_entities}

Top topics covered:
{topics}

Sentiment breakdown:
{sentiment}

Key video titles (sample):
{titles}

Combined transcript excerpts (representative sample):
{excerpts}

Write a comprehensive ~1000-word editorial summary of {year} for the AIM Media House channel.
Cover:
1. Major themes and narratives that dominated the year
2. Key people, companies, and technologies that were in the spotlight
3. How the AI/ML landscape evolved as seen through this channel
4. Standout discussions or debates
5. What this year meant for Indian and global AI ecosystem

Write in a professional, engaging journalistic tone. No bullet points — flowing paragraphs only.
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIM Media House – Annual Intelligence Report</title>
<style>
  :root {
    --primary: #6c3fc7;
    --accent: #e91e8c;
    --bg: #0f0f1a;
    --card: #1a1a2e;
    --text: #e0e0f0;
    --muted: #888;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }
  .hero {
    background: linear-gradient(135deg, #1a0533 0%, #0a1628 100%);
    padding: 60px 40px;
    text-align: center;
    border-bottom: 2px solid var(--primary);
  }
  .hero h1 { font-size: 2.8rem; font-weight: 800; color: #fff; }
  .hero h1 span { color: var(--accent); }
  .hero p { color: var(--muted); margin-top: 12px; font-size: 1.1rem; }
  .stats-bar {
    display: flex; justify-content: center; gap: 40px;
    padding: 30px 40px;
    background: var(--card);
    border-bottom: 1px solid #2a2a4a;
  }
  .stat { text-align: center; }
  .stat .num { font-size: 2rem; font-weight: 700; color: var(--primary); }
  .stat .label { font-size: 0.85rem; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
  .container { max-width: 900px; margin: 0 auto; padding: 40px 20px; }
  .year-section {
    background: var(--card);
    border-radius: 12px;
    padding: 36px;
    margin-bottom: 40px;
    border-left: 4px solid var(--primary);
    box-shadow: 0 4px 20px rgba(108,63,199,0.15);
  }
  .year-section h2 {
    font-size: 1.9rem; font-weight: 700;
    color: var(--primary);
    margin-bottom: 8px;
  }
  .year-meta {
    display: flex; gap: 20px; margin-bottom: 20px;
    font-size: 0.85rem; color: var(--muted);
  }
  .year-meta span { background: #16213e; padding: 4px 12px; border-radius: 20px; }
  .summary-text { font-size: 0.97rem; color: #ccc; }
  .summary-text p { margin-bottom: 14px; }
  .entities-row {
    display: flex; flex-wrap: wrap; gap: 8px; margin-top: 20px;
  }
  .tag {
    font-size: 0.78rem; padding: 4px 12px; border-radius: 20px;
    font-weight: 600;
  }
  .tag-person { background: rgba(108,63,199,0.2); color: #a78bfa; }
  .tag-company { background: rgba(233,30,140,0.15); color: #f472b6; }
  .tag-tool { background: rgba(14,165,233,0.15); color: #38bdf8; }
  .tag-technology { background: rgba(16,185,129,0.15); color: #34d399; }
  .toc { background: var(--card); border-radius: 12px; padding: 24px 32px; margin-bottom: 40px; }
  .toc h3 { color: var(--accent); margin-bottom: 14px; font-size: 1rem; text-transform: uppercase; letter-spacing: 1px; }
  .toc a { color: var(--text); text-decoration: none; display: block; padding: 6px 0;
            border-bottom: 1px solid #2a2a4a; font-size: 0.95rem; }
  .toc a:hover { color: var(--primary); }
  footer { text-align: center; padding: 40px; color: var(--muted); font-size: 0.85rem; border-top: 1px solid #2a2a4a; }
</style>
</head>
<body>
<div class="hero">
  <h1>AIM Media House<br><span>Annual Intelligence Report</span></h1>
  <p>AI & ML landscape through {{ stats.year_range[0] }}–{{ stats.year_range[1] }} &nbsp;·&nbsp; Automated multi-agent analysis</p>
</div>

<div class="stats-bar">
  <div class="stat"><div class="num">{{ stats.total }}</div><div class="label">Videos Analyzed</div></div>
  <div class="stat"><div class="num">{{ stats.analyzed }}</div><div class="label">Transcripts Processed</div></div>
  <div class="stat"><div class="num">{{ summaries|length }}</div><div class="label">Years Covered</div></div>
  <div class="stat"><div class="num">{{ generated_at }}</div><div class="label">Generated</div></div>
</div>

<div class="container">
  <div class="toc">
    <h3>Table of Contents</h3>
    {% for s in summaries %}
    <a href="#year-{{ s.year }}">{{ s.year }} &nbsp;–&nbsp; {{ s.video_count }} videos</a>
    {% endfor %}
  </div>

  {% for s in summaries %}
  <div class="year-section" id="year-{{ s.year }}">
    <h2>{{ s.year }}</h2>
    <div class="year-meta">
      <span>{{ s.video_count }} Videos</span>
      {% for theme in s.key_themes_parsed[:3] %}<span>{{ theme }}</span>{% endfor %}
    </div>
    <div class="summary-text">
      {% for para in s.summary.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}
    </div>
    {% if s.top_entities_parsed %}
    <div class="entities-row">
      {% for e in s.top_entities_parsed[:12] %}
      <span class="tag tag-{{ e.type }}">{{ e.name }}</span>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  {% endfor %}
</div>

<footer>
  AIM Media House Intelligence Report &nbsp;·&nbsp; Generated {{ generated_at }}
</footer>
</body>
</html>
"""


class ReportGeneratorAgent(BaseAgent):
    name = "ReportGenerator"

    def run(self):
        self.logger.info("[ReportGenerator] Generating yearly summaries")
        yearly_counts = db.get_yearly_video_counts()
        years = [row["year"] for row in yearly_counts if row["year"]]

        for year in years:
            self._generate_year_summary(year)

        self._render_html_report()
        self.logger.info(f"[ReportGenerator] Reports saved to {REPORTS_DIR}")

    def _generate_year_summary(self, year: int):
        from database.manager import get_conn
        with get_conn() as conn:
            videos = conn.execute("""
                SELECT title, view_count, transcript_clean
                FROM videos WHERE year=? AND has_transcript=1
                ORDER BY view_count DESC
            """, (year,)).fetchall()
            video_count = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE year=?", (year,)
            ).fetchone()[0]

        if not videos:
            self.logger.info(f"No transcripts for {year}, skipping")
            return

        top_entities = db.get_top_entities(year=year, limit=20)
        topics = db.get_topic_distribution(year=year)
        sentiments = db.get_sentiment_distribution(year=year)

        # build combined excerpt from top 10 most-viewed videos
        excerpts = []
        for v in list(videos)[:10]:
            if v["transcript_clean"]:
                chunk = truncate_to_words(v["transcript_clean"], 300)
                excerpts.append(f"[{v['title']}]\n{chunk}")
        excerpts_str = "\n\n".join(excerpts)

        titles_str = "\n".join(f"- {v['title']}" for v in list(videos)[:20])
        entities_str = "\n".join(f"- {e['name']} ({e['type']}, {e['count']} mentions)" for e in top_entities[:15])
        topics_str = "\n".join(f"- {t['category']}: {t['count']} videos" for t in topics[:10])
        sentiment_str = "\n".join(f"- {s['sentiment']}: {s['count']} videos" for s in sentiments)

        prompt = SUMMARY_PROMPT.format(
            year=year,
            video_count=video_count,
            top_entities=entities_str,
            topics=topics_str,
            sentiment=sentiment_str,
            titles=titles_str,
            excerpts=excerpts_str
        )

        summary_text = self.llm_call(prompt)
        if not summary_text:
            self.logger.warning(f"No summary generated for {year}")
            return

        key_themes = [t["category"] for t in topics[:5]]
        top_ents_data = [{"name": e["name"], "type": e["type"]} for e in top_entities[:10]]

        db.store_yearly_summary(year, summary_text, key_themes, top_ents_data, video_count)
        self.logger.info(f"  Saved summary for {year} ({len(summary_text.split())} words)")

    def _render_html_report(self):
        summaries = db.get_yearly_summaries()
        stats = db.get_stats()

        for s in summaries:
            try:
                s["key_themes_parsed"] = json.loads(s.get("key_themes") or "[]")
                s["top_entities_parsed"] = json.loads(s.get("top_entities") or "[]")
            except Exception:
                s["key_themes_parsed"] = []
                s["top_entities_parsed"] = []

        env = Environment(loader=BaseLoader())
        tmpl = env.from_string(HTML_TEMPLATE)
        html = tmpl.render(
            summaries=summaries,
            stats=stats,
            generated_at=datetime.now().strftime("%B %d, %Y")
        )

        out_path = Path(REPORTS_DIR) / "annual_report.html"
        out_path.write_text(html, encoding="utf-8")
        self.logger.info(f"HTML report written to {out_path}")

        # Optional PDF export via weasyprint (requires: brew install pango libffi)
        try:
            from weasyprint import HTML as WPHTML
            pdf_path = Path(REPORTS_DIR) / "annual_report.pdf"
            WPHTML(string=html, base_url=str(REPORTS_DIR)).write_pdf(str(pdf_path))
            self.logger.info(f"PDF report written to {pdf_path}")
        except (ImportError, OSError):
            self.logger.info("PDF export skipped (weasyprint system deps missing). HTML report is ready.")
        except Exception as e:
            self.logger.warning(f"PDF generation failed: {e}")
