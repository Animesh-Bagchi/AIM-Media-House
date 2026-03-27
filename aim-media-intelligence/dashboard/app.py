"""
AIM Media House Intelligence Dashboard
Interactive Streamlit app for exploring channel analytics.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from database import manager as db

st.set_page_config(
    page_title="AIM Media Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styles ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #0f0f1e; }
  .main { background: #12121f; }
  .metric-card {
    background: #1a1a2e; border-radius: 10px; padding: 20px;
    border-left: 3px solid #6c3fc7; margin-bottom: 10px;
  }
  .metric-val { font-size: 2rem; font-weight: 800; color: #a78bfa; }
  .metric-lbl { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
  h1, h2, h3 { color: #e0e0f0 !important; }
  .stTabs [data-baseweb="tab"] { color: #888; }
  .stTabs [aria-selected="true"] { color: #a78bfa !important; }
</style>
""", unsafe_allow_html=True)


# ── Data loaders (cached) ──────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_stats():
    return db.get_stats()

@st.cache_data(ttl=300)
def load_entities(etype=None, year=None, limit=50):
    return db.get_top_entities(entity_type=etype, year=year, limit=limit)

@st.cache_data(ttl=300)
def load_topic_dist(year=None):
    return db.get_topic_distribution(year=year)

@st.cache_data(ttl=300)
def load_yearly_trends():
    return db.get_yearly_entity_trends()

@st.cache_data(ttl=300)
def load_sentiment(year=None):
    return db.get_sentiment_distribution(year=year)

@st.cache_data(ttl=300)
def load_yearly_counts():
    return db.get_yearly_video_counts()

@st.cache_data(ttl=300)
def load_summaries():
    return db.get_yearly_summaries()

@st.cache_data(ttl=300)
def load_relationships():
    return db.get_relationships(limit=300)


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 AIM Intelligence")
    st.markdown("*Analytics India Magazine*")
    st.divider()

    page = st.radio("Navigation", [
        "📊 Overview",
        "👤 Entities",
        "🗂 Topics",
        "📈 Trends",
        "💬 Sentiment",
        "🕸 Knowledge Graph",
        "💡 Deep Insights",
        "📄 Annual Reports",
        "🤖 Q&A Chat",
    ])

    st.divider()
    stats = load_stats()
    st.metric("Total Videos", stats["total"])
    st.metric("Transcripts", stats["with_transcript"])
    st.metric("Analyzed", stats["analyzed"])
    yr = stats["year_range"]
    if yr[0]:
        st.caption(f"Coverage: {yr[0]} – {yr[1]}")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 1 – OVERVIEW
# ══════════════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.title("AIM Media House – Channel Overview")

    c1, c2, c3, c4 = st.columns(4)
    for col, label, val in zip(
        [c1, c2, c3, c4],
        ["Total Videos", "Transcripts", "Analyzed", "Years Covered"],
        [stats["total"], stats["with_transcript"], stats["analyzed"],
         (stats["year_range"][1] - stats["year_range"][0] + 1) if stats["year_range"][0] else 0]
    ):
        with col:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-val">{val}</div>
                <div class="metric-lbl">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.divider()
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Videos Published Per Year")
        yearly = load_yearly_counts()
        if yearly:
            df = pd.DataFrame(yearly)
            fig = px.bar(df, x="year", y="count", color="count",
                         color_continuous_scale="Purples",
                         labels={"count": "Videos", "year": "Year"})
            fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                              font_color="#ccc", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Topic Distribution (All Time)")
        topics = load_topic_dist()
        if topics:
            df_t = pd.DataFrame(topics).head(12)
            fig = px.pie(df_t, names="category", values="count",
                         color_discrete_sequence=px.colors.sequential.Purples_r)
            fig.update_layout(paper_bgcolor="#12121f", font_color="#ccc")
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Cumulative Views Per Year")
    yearly = load_yearly_counts()
    if yearly:
        df = pd.DataFrame(yearly)
        if "total_views" in df.columns:
            fig = px.area(df, x="year", y="total_views",
                          color_discrete_sequence=["#6c3fc7"])
            fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                              font_color="#ccc")
            st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 2 – ENTITIES
# ══════════════════════════════════════════════════════════════════════════
elif page == "👤 Entities":
    st.title("Entity Analysis")
    st.caption("Most mentioned people, companies, and tools across all videos")

    yearly = load_yearly_counts()
    years = ["All"] + sorted([str(r["year"]) for r in yearly], reverse=True)
    year_filter = st.selectbox("Filter by year", years)
    year_val = None if year_filter == "All" else int(year_filter)

    tab_all, tab_person, tab_company, tab_tool = st.tabs(
        ["All Entities", "People", "Companies", "Tools & Technologies"]
    )

    def entity_bar(etype, tab, color):
        with tab:
            data = load_entities(etype=etype, year=year_val, limit=25)
            if data:
                df = pd.DataFrame(data)
                fig = px.bar(df, x="count", y="name", orientation="h",
                             color_discrete_sequence=[color],
                             labels={"count": "Mentions", "name": ""})
                fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                                  font_color="#ccc", height=600,
                                  yaxis=dict(autorange="reversed"))
                tab.plotly_chart(fig, use_container_width=True)
            else:
                tab.info("No data yet. Run the analysis pipeline first.")

    with tab_all:
        data = load_entities(year=year_val, limit=30)
        if data:
            df = pd.DataFrame(data)
            color_map = {"person": "#a78bfa", "company": "#f472b6",
                         "tool": "#38bdf8", "technology": "#34d399"}
            df["color"] = df["type"].map(color_map).fillna("#888")
            fig = px.treemap(df, path=["type", "name"], values="count",
                             color="type",
                             color_discrete_map=color_map)
            fig.update_layout(paper_bgcolor="#12121f", font_color="#ccc")
            st.plotly_chart(fig, use_container_width=True)

    entity_bar("person", tab_person, "#a78bfa")
    entity_bar("company", tab_company, "#f472b6")
    entity_bar(None, tab_tool, "#38bdf8")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 3 – TOPICS
# ══════════════════════════════════════════════════════════════════════════
elif page == "🗂 Topics":
    st.title("Topic Modeling")

    yearly = load_yearly_counts()
    years = ["All"] + sorted([str(r["year"]) for r in yearly], reverse=True)
    year_filter = st.selectbox("Year", years)
    year_val = None if year_filter == "All" else int(year_filter)

    topics = load_topic_dist(year=year_val)
    if topics:
        df = pd.DataFrame(topics)
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(df, x="count", y="category", orientation="h",
                         color="count", color_continuous_scale="Purples",
                         labels={"count": "Videos", "category": "Topic"})
            fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                              font_color="#ccc", height=500,
                              yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.pie(df, names="category", values="count",
                         color_discrete_sequence=px.colors.sequential.Purp_r)
            fig.update_layout(paper_bgcolor="#12121f", font_color="#ccc")
            st.plotly_chart(fig, use_container_width=True)

        # topic heatmap by year
        st.subheader("Topic Heatmap by Year")
        all_trends = load_yearly_trends()
        if all_trends:
            df_all = pd.DataFrame(all_trends)
            # aggregate by year + topic
            from database.manager import get_conn
            with get_conn() as conn:
                rows = conn.execute("""
                    SELECT year, category, COUNT(*) as count
                    FROM topics WHERE year IS NOT NULL
                    GROUP BY year, category
                """).fetchall()
            if rows:
                df_heat = pd.DataFrame([dict(r) for r in rows])
                pivot = df_heat.pivot(index="category", columns="year", values="count").fillna(0)
                fig = px.imshow(pivot, color_continuous_scale="Purples",
                                labels={"color": "Videos"})
                fig.update_layout(paper_bgcolor="#12121f", font_color="#ccc", height=500)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No topic data yet. Run: `python main.py --mode analyze`")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 4 – TRENDS
# ══════════════════════════════════════════════════════════════════════════
elif page == "📈 Trends":
    st.title("Trend Detection")
    st.caption("Track how topics, companies, and technologies have evolved over time")

    all_entities = load_entities(limit=100)
    if not all_entities:
        st.info("No trend data yet. Run the analysis pipeline first.")
    else:
        df_ent = pd.DataFrame(all_entities)
        entity_names = df_ent["name"].tolist()

        selected = st.multiselect(
            "Track entities over time",
            entity_names,
            default=entity_names[:5]
        )

        if selected:
            trend_data = []
            for name in selected:
                rows = db.get_entity_trends(name)
                for r in rows:
                    trend_data.append({"entity": name, "year": r["year"], "count": r["count"]})

            if trend_data:
                df_trend = pd.DataFrame(trend_data)
                fig = px.line(df_trend, x="year", y="count", color="entity",
                              markers=True, color_discrete_sequence=px.colors.qualitative.Vivid)
                fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                                  font_color="#ccc", height=450)
                st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("Rising Topics (Year-over-Year Growth)")
        all_trends = load_yearly_trends()
        if all_trends:
            df_t = pd.DataFrame(all_trends)
            # calculate YoY growth for entities with data in multiple years
            growth = []
            for name in df_t["name"].unique():
                sub = df_t[df_t["name"] == name].sort_values("year")
                if len(sub) >= 2:
                    latest = sub.iloc[-1]["count"]
                    prev = sub.iloc[-2]["count"]
                    if prev > 0:
                        growth.append({
                            "entity": name,
                            "type": sub.iloc[-1]["type"],
                            "latest_year": int(sub.iloc[-1]["year"]),
                            "growth_pct": round((latest - prev) / prev * 100, 1)
                        })
            if growth:
                df_growth = pd.DataFrame(growth).sort_values("growth_pct", ascending=False).head(20)
                color_map = {"person": "#a78bfa", "company": "#f472b6",
                             "tool": "#38bdf8", "technology": "#34d399"}
                df_growth["color"] = df_growth["type"].map(color_map).fillna("#888")
                fig = px.bar(df_growth, x="growth_pct", y="entity", orientation="h",
                             color="type", color_discrete_map=color_map,
                             labels={"growth_pct": "YoY Growth %", "entity": ""},
                             title="Fastest Growing Entities (Most Recent Year)")
                fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                                  font_color="#ccc", height=500,
                                  yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 5 – SENTIMENT
# ══════════════════════════════════════════════════════════════════════════
elif page == "💬 Sentiment":
    st.title("Sentiment Analysis")

    yearly = load_yearly_counts()
    years = ["All"] + sorted([str(r["year"]) for r in yearly], reverse=True)
    year_filter = st.selectbox("Year", years)
    year_val = None if year_filter == "All" else int(year_filter)

    sentiments = load_sentiment(year=year_val)
    if sentiments:
        df_s = pd.DataFrame(sentiments)
        c1, c2 = st.columns(2)
        with c1:
            color_map = {"positive": "#34d399", "neutral": "#94a3b8", "critical": "#f87171"}
            fig = px.pie(df_s, names="sentiment", values="count",
                         color="sentiment", color_discrete_map=color_map)
            fig.update_layout(paper_bgcolor="#12121f", font_color="#ccc",
                              title="Sentiment Breakdown")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.bar(df_s, x="sentiment", y="avg_score",
                         color="sentiment", color_discrete_map=color_map,
                         labels={"avg_score": "Average Score", "sentiment": ""},
                         title="Average Sentiment Score by Category")
            fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                              font_color="#ccc")
            st.plotly_chart(fig, use_container_width=True)

        # sentiment over years
        st.subheader("Sentiment Trend Over Time")
        from database.manager import get_conn
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT year, sentiment, COUNT(*) as count
                FROM sentiments WHERE year IS NOT NULL
                GROUP BY year, sentiment ORDER BY year
            """).fetchall()
        if rows:
            df_yearly_s = pd.DataFrame([dict(r) for r in rows])
            fig = px.bar(df_yearly_s, x="year", y="count", color="sentiment",
                         color_discrete_map=color_map, barmode="stack",
                         labels={"count": "Videos", "year": "Year"})
            fig.update_layout(paper_bgcolor="#12121f", plot_bgcolor="#1a1a2e",
                              font_color="#ccc")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No sentiment data yet. Run: `python main.py --mode analyze`")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 6 – KNOWLEDGE GRAPH
# ══════════════════════════════════════════════════════════════════════════
elif page == "🕸 Knowledge Graph":
    st.title("Knowledge Graph")
    st.caption("Relationships between people, companies, and technologies")

    rels = load_relationships()
    if not rels:
        st.info("No relationship data yet. Run: `python main.py --mode analyze`")
    else:
        min_weight = st.slider("Minimum co-occurrence weight", 1, 10, 2)
        rels_filtered = [r for r in rels if r["weight"] >= min_weight]

        if rels_filtered:
            G = nx.Graph()
            for r in rels_filtered:
                G.add_edge(r["entity1"], r["entity2"], weight=r["weight"])

            # node sizes by degree
            pos = nx.spring_layout(G, k=0.8, iterations=50, seed=42)
            degrees = dict(G.degree())

            edge_x, edge_y = [], []
            for e1, e2 in G.edges():
                x0, y0 = pos[e1]
                x1, y1 = pos[e2]
                edge_x += [x0, x1, None]
                edge_y += [y0, y1, None]

            node_x = [pos[n][0] for n in G.nodes()]
            node_y = [pos[n][1] for n in G.nodes()]
            node_text = list(G.nodes())
            node_size = [10 + degrees[n] * 3 for n in G.nodes()]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                                     line=dict(width=0.8, color="#444")))
            fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text",
                                     text=node_text, textposition="top center",
                                     marker=dict(size=node_size, color="#6c3fc7",
                                                 line=dict(width=1, color="#a78bfa")),
                                     hoverinfo="text"))
            fig.update_layout(
                showlegend=False, hovermode="closest",
                paper_bgcolor="#12121f", plot_bgcolor="#12121f",
                font_color="#ccc", height=600,
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Showing {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (min weight: {min_weight})")
        else:
            st.warning("No relationships meet the minimum weight threshold.")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 7 – DEEP INSIGHTS (new)
# ══════════════════════════════════════════════════════════════════════════
elif page == "💡 Deep Insights":
    st.title("Deep Insights")
    st.caption("Cross-video intelligence: viral patterns, content gaps, channel evolution")

    from config import REPORTS_DIR
    insights_path = Path(REPORTS_DIR) / "insights.json"

    if not insights_path.exists():
        st.info("No insights generated yet. Run: `python main.py --mode insights`")
    else:
        import json
        insights = json.loads(insights_path.read_text())

        tab_viral, tab_gaps, tab_evolution = st.tabs(
            ["🔥 Viral Content Patterns", "🕳 Content Gaps", "📡 Channel Evolution"]
        )

        with tab_viral:
            viral = insights.get("viral_patterns", {})
            if viral:
                for year, data in sorted(viral.items(), reverse=True):
                    with st.expander(f"**{year}** — Viral Formula", expanded=(year == max(viral.keys()))):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Winning Formula**\n\n{data.get('winning_formula', 'N/A')}")
                            st.markdown(f"**Best Tone**\n\n{data.get('best_sentiment_tone', 'N/A')}")
                        with c2:
                            st.markdown(f"**Top Topic+Entity Combo**\n\n{data.get('top_topic_entity_combo', 'N/A')}")
                            st.markdown(f"**Predicted Viral Topic**\n\n🎯 {data.get('predicted_viral_topic', 'N/A')}")
                        for i in data.get("insights", []):
                            st.markdown(f"• {i}")
            else:
                st.info("Run insights pipeline to generate viral pattern analysis.")

        with tab_gaps:
            gaps = insights.get("content_gaps", {})
            if gaps:
                st.subheader("Underrepresented Topics")
                for t in gaps.get("underrepresented_topics", []):
                    st.markdown(f"- 🟡 {t}")
                st.subheader("Missing Key Entities")
                for e in gaps.get("missing_key_entities", []):
                    st.markdown(f"- 👤 {e}")
                st.subheader("Emerging Opportunities")
                for o in gaps.get("emerging_opportunities", []):
                    st.markdown(f"- 🚀 {o}")
                st.success(f"**Top Recommendation:** {gaps.get('recommendation', 'N/A')}")
            else:
                st.info("Run insights pipeline to detect content gaps.")

        with tab_evolution:
            evo = insights.get("channel_evolution", {})
            if evo:
                st.markdown(f"### Channel Evolution Narrative\n\n{evo.get('evolution_narrative', '')}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Rising Entities**")
                    for e in evo.get("rising_entities", []):
                        st.markdown(f"↗ {e}")
                with c2:
                    st.markdown("**Declining Entities**")
                    for e in evo.get("declining_entities", []):
                        st.markdown(f"↘ {e}")
                st.markdown(f"**Current Trajectory:** {evo.get('current_trajectory', '')}")
                inflections = evo.get("inflection_years", [])
                if inflections:
                    st.subheader("Key Inflection Points")
                    for pt in inflections:
                        st.markdown(f"**{pt.get('year')}** — {pt.get('reason')}")
            else:
                st.info("Run insights pipeline to analyze channel evolution.")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 8 – ANNUAL REPORTS
# ══════════════════════════════════════════════════════════════════════════
elif page == "📄 Annual Reports":
    st.title("Annual Intelligence Reports")

    summaries = load_summaries()
    if not summaries:
        st.info("No reports generated yet. Run: `python main.py --mode report`")
    else:
        years = [str(s["year"]) for s in summaries]
        selected_year = st.selectbox("Select Year", sorted(years, reverse=True))

        summary = next((s for s in summaries if str(s["year"]) == selected_year), None)
        if summary:
            st.markdown(f"### {selected_year} — Annual Review")
            c1, c2 = st.columns([2, 1])
            with c1:
                try:
                    themes = json.loads(summary.get("key_themes") or "[]")
                    st.markdown("**Key Themes:** " + " · ".join(themes))
                except Exception:
                    pass
                st.divider()
                for para in (summary.get("summary") or "").split("\n\n"):
                    if para.strip():
                        st.markdown(para.strip())
            with c2:
                st.metric("Videos Published", summary.get("video_count", 0))
                try:
                    ents = json.loads(summary.get("top_entities") or "[]")
                    st.markdown("**Top Entities:**")
                    for e in ents[:8]:
                        badge_color = {"person": "🟣", "company": "🔴", "tool": "🔵", "technology": "🟢"}
                        icon = badge_color.get(e.get("type", ""), "⚪")
                        st.markdown(f"{icon} {e.get('name', '')}")
                except Exception:
                    pass

        # download HTML report
        from config import REPORTS_DIR
        from pathlib import Path
        html_file = Path(REPORTS_DIR) / "annual_report.html"
        if html_file.exists():
            st.divider()
            st.download_button(
                "⬇ Download Full HTML Report",
                data=html_file.read_bytes(),
                file_name="aim_annual_report.html",
                mime="text/html"
            )


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 8 – Q&A CHAT
# ══════════════════════════════════════════════════════════════════════════
elif page == "🤖 Q&A Chat":
    st.title("Ask Anything About AIM Media House")
    st.caption("Conversational Q&A powered by Gemini, grounded in channel data")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question about the channel..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Build context from DB
                    stats = load_stats()
                    top_people = load_entities("person", limit=10)
                    top_companies = load_entities("company", limit=10)
                    top_tools = load_entities("tool", limit=10)
                    topics = load_topic_dist()
                    summaries = load_summaries()

                    context = f"""Channel Statistics:
- Total videos: {stats['total']}
- Videos with transcripts: {stats['with_transcript']}
- Year range: {stats['year_range'][0]} – {stats['year_range'][1]}

Top People mentioned: {', '.join(e['name'] for e in top_people)}
Top Companies: {', '.join(e['name'] for e in top_companies)}
Top Tools/Technologies: {', '.join(e['name'] for e in top_tools)}
Top Topics: {', '.join(t['category'] for t in topics[:8])}

Annual Summaries available for years: {', '.join(str(s['year']) for s in summaries)}
"""

                    from config import GEMINI_API_KEY, LLM_MODEL
                    from google import genai as gai

                    full_prompt = f"""You are an analyst for AIM Media House (Analytics India Magazine) YouTube channel.
Answer questions based on the following channel data:

{context}

User question: {prompt}

Provide a concise, data-driven answer. If you don't have enough data, say so honestly."""

                    client = gai.Client(api_key=GEMINI_API_KEY)
                    response = client.models.generate_content(model=LLM_MODEL, contents=full_prompt)
                    answer = response.text
                    st.markdown(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                except Exception as e:
                    err = f"Error: {e}. Make sure GEMINI_API_KEY is set and the pipeline has been run."
                    st.error(err)
                    st.session_state.chat_history.append({"role": "assistant", "content": err})
