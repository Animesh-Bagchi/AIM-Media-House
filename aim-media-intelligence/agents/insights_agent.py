"""
Insights Agent — cross-video intelligence.

Runs AFTER the analysis agent to produce higher-order insights:
- Viral content patterns (what makes high-view videos)
- Content gap detection (underserved topics)
- Channel evolution narrative
- Influencer network (who appears together most)
- Token-efficient: works entirely from pre-aggregated DB data, no transcript re-reads.
"""
import json
import logging
from database import manager as db
from agents.base_agent import BaseAgent
from config import REPORTS_DIR
from pathlib import Path

logger = logging.getLogger(__name__)

VIRAL_PROMPT = """You are analyzing what makes YouTube videos from AIM Media House go viral.

Top 20 most-viewed videos this year ({year}):
{top_videos}

Most-mentioned entities in high-view videos:
{top_entities}

Top topics in high-view videos:
{top_topics}

Sentiment of high-view videos:
{sentiment}

Based on this data, identify:
1. What topic/entity combinations reliably drive high views?
2. What sentiment tone performs best?
3. What is the "winning formula" for this channel in {year}?
4. Predict: what video would likely get the most views if published tomorrow?

Respond with JSON:
{{
  "winning_formula": "...",
  "top_topic_entity_combo": "...",
  "best_sentiment_tone": "...",
  "predicted_viral_topic": "...",
  "insights": ["insight1", "insight2", "insight3"]
}}
"""

GAP_PROMPT = """You are analyzing content gaps for AIM Media House YouTube channel.

Topics covered (with video counts):
{covered_topics}

Top entities mentioned (showing what's popular):
{top_entities}

Given this is an AI/ML media channel covering the Indian tech ecosystem, identify:
1. Topics that are clearly underrepresented relative to their importance in 2024 AI landscape
2. Notable people/companies that should be covered more
3. Emerging topics not yet covered

Respond with JSON:
{{
  "underrepresented_topics": ["topic1", "topic2", "topic3"],
  "missing_key_entities": ["entity1", "entity2"],
  "emerging_opportunities": ["opportunity1", "opportunity2"],
  "recommendation": "single most impactful content gap to fill"
}}
"""

EVOLUTION_PROMPT = """You are writing a channel evolution analysis for AIM Media House.

Year-by-year topic distribution:
{yearly_topics}

Year-by-year top entities:
{yearly_entities}

Year-by-year sentiment:
{yearly_sentiment}

Video count per year:
{yearly_counts}

Analyze how this channel has evolved over time:
1. How has the focus shifted (e.g., from traditional ML to GenAI)?
2. Which entities have risen/fallen in prominence?
3. What does the sentiment trend tell us about the industry mood?
4. Identify key "inflection points" — years where the channel's direction clearly shifted.

Respond with JSON:
{{
  "evolution_narrative": "2-3 sentence summary",
  "inflection_years": [{{"year": ..., "reason": "..."}}],
  "rising_entities": ["entity1", "entity2"],
  "declining_entities": ["entity1", "entity2"],
  "current_trajectory": "..."
}}
"""


class InsightsAgent(BaseAgent):
    name = "InsightsAgent"

    def run(self):
        self.logger.info("[InsightsAgent] Generating cross-video insights")
        results = {}

        results["viral_patterns"] = self._analyze_viral_patterns()
        results["content_gaps"] = self._analyze_content_gaps()
        results["channel_evolution"] = self._analyze_channel_evolution()

        # save to file
        out_path = Path(REPORTS_DIR) / "insights.json"
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        self.logger.info(f"[InsightsAgent] Insights saved to {out_path}")
        return results

    def _analyze_viral_patterns(self) -> dict:
        from database.manager import get_conn
        results = {}
        yearly_counts = db.get_yearly_video_counts()
        years = [r["year"] for r in yearly_counts if r["year"]]

        for year in years[-3:]:  # last 3 years to save tokens
            with get_conn() as conn:
                top_videos = conn.execute("""
                    SELECT title, view_count, like_count
                    FROM videos WHERE year=? AND has_transcript=1
                    ORDER BY view_count DESC LIMIT 20
                """, (year,)).fetchall()

            if not top_videos:
                continue

            top_ids_query = f"SELECT video_id FROM videos WHERE year={year} ORDER BY view_count DESC LIMIT 20"
            with get_conn() as conn:
                top_ids = [r[0] for r in conn.execute(top_ids_query).fetchall()]

            top_entities_str = ""
            top_topics_str = ""
            sentiment_str = ""

            if top_ids:
                placeholders = ",".join("?" * len(top_ids))
                with get_conn() as conn:
                    ents = conn.execute(f"""
                        SELECT name, type, COUNT(*) as cnt FROM entities
                        WHERE video_id IN ({placeholders}) GROUP BY name, type
                        ORDER BY cnt DESC LIMIT 10
                    """, top_ids).fetchall()
                    tops = conn.execute(f"""
                        SELECT category, COUNT(*) as cnt FROM topics
                        WHERE video_id IN ({placeholders}) AND is_primary=1
                        GROUP BY category ORDER BY cnt DESC LIMIT 5
                    """, top_ids).fetchall()
                    sents = conn.execute(f"""
                        SELECT sentiment, COUNT(*) as cnt FROM sentiments
                        WHERE video_id IN ({placeholders})
                        GROUP BY sentiment
                    """, top_ids).fetchall()
                top_entities_str = "\n".join(f"{r[0]} ({r[1]}): {r[2]} times" for r in ents)
                top_topics_str = "\n".join(f"{r[0]}: {r[1]} videos" for r in tops)
                sentiment_str = "\n".join(f"{r[0]}: {r[1]} videos" for r in sents)

            videos_str = "\n".join(
                f"- {v['title']} ({v['view_count']:,} views)" for v in top_videos[:10]
            )

            prompt = VIRAL_PROMPT.format(
                year=year,
                top_videos=videos_str,
                top_entities=top_entities_str,
                top_topics=top_topics_str,
                sentiment=sentiment_str,
            )
            result = self.llm_json(prompt)
            if result:
                results[str(year)] = result
                self.logger.info(f"  Viral analysis for {year}: {result.get('winning_formula', '')[:80]}")

        return results

    def _analyze_content_gaps(self) -> dict:
        topics = db.get_topic_distribution()
        entities = db.get_top_entities(limit=30)

        topics_str = "\n".join(f"{t['category']}: {t['count']} videos" for t in topics)
        entities_str = "\n".join(f"{e['name']} ({e['type']}): {e['count']} mentions" for e in entities[:20])

        result = self.llm_json(GAP_PROMPT.format(
            covered_topics=topics_str,
            top_entities=entities_str
        ))
        if result:
            self.logger.info(f"  Content gap identified: {result.get('recommendation', '')[:80]}")
        return result or {}

    def _analyze_channel_evolution(self) -> dict:
        yearly_counts = db.get_yearly_video_counts()

        yearly_topics = {}
        yearly_entities = {}
        yearly_sentiment_data = {}

        for row in yearly_counts:
            year = row["year"]
            if not year:
                continue
            topics = db.get_topic_distribution(year=year)
            entities = db.get_top_entities(year=year, limit=5)
            sentiment = db.get_sentiment_distribution(year=year)
            yearly_topics[str(year)] = [t["category"] for t in topics[:5]]
            yearly_entities[str(year)] = [e["name"] for e in entities]
            yearly_sentiment_data[str(year)] = {s["sentiment"]: s["count"] for s in sentiment}

        counts_str = "\n".join(f"{r['year']}: {r['count']} videos" for r in yearly_counts if r["year"])

        result = self.llm_json(EVOLUTION_PROMPT.format(
            yearly_topics=json.dumps(yearly_topics, indent=2),
            yearly_entities=json.dumps(yearly_entities, indent=2),
            yearly_sentiment=json.dumps(yearly_sentiment_data, indent=2),
            yearly_counts=counts_str,
        ))
        if result:
            self.logger.info(f"  Evolution: {result.get('evolution_narrative', '')[:100]}")
        return result or {}
