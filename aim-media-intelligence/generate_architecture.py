"""
Generates the multi-agent architecture diagram as a PNG.
Run: python generate_architecture.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT_PATH = Path("data/outputs/architecture_diagram.png")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

BG = "#0f0f1a"
CARD = "#1a1a2e"
PURPLE = "#6c3fc7"
PINK = "#e91e8c"
BLUE = "#0ea5e9"
GREEN = "#10b981"
YELLOW = "#f59e0b"
TEXT = "#e0e0f0"
MUTED = "#888888"

fig, ax = plt.subplots(figsize=(18, 11))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 18)
ax.set_ylim(0, 11)
ax.axis("off")


def box(x, y, w, h, color, label, sublabel="", icon=""):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                           linewidth=2, edgecolor=color, facecolor=CARD)
    ax.add_patch(rect)
    full_label = f"{icon}  {label}" if icon else label
    ax.text(x + w / 2, y + h / 2 + (0.15 if sublabel else 0),
            full_label, ha="center", va="center",
            fontsize=9.5, fontweight="bold", color=TEXT)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.25, sublabel,
                ha="center", va="center", fontsize=7.5, color=MUTED)


def arrow(x1, y1, x2, y2, color=PURPLE):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.8))


def label(x, y, txt, color=MUTED, size=7.5):
    ax.text(x, y, txt, ha="center", va="center", fontsize=size, color=color)


# ── Title ──────────────────────────────────────────────────────────────────
ax.text(9, 10.5, "AIM Media House — Multi-Agent Intelligence Pipeline",
        ha="center", va="center", fontsize=14, fontweight="bold", color=TEXT)
ax.text(9, 10.15, "End-to-end automated workflow: YouTube → Transcripts → Analysis → Dashboard",
        ha="center", va="center", fontsize=9, color=MUTED)

# ── Data Sources ───────────────────────────────────────────────────────────
box(0.3, 8.0, 2.4, 1.0, BLUE, "YouTube Channel", "AIM Media House", "[YT]")
box(0.3, 6.7, 2.4, 0.9, BLUE, "YouTube Data API", "Video metadata", "[API]")
box(0.3, 5.6, 2.4, 0.9, BLUE, "Transcript API", "Captions / ASR", "[TXT]")

ax.text(1.5, 9.25, "DATA SOURCES", ha="center", fontsize=7, color=BLUE, fontweight="bold")

# ── Agent 1 ────────────────────────────────────────────────────────────────
box(3.5, 6.9, 2.8, 1.6, PURPLE, "Agent 1", "Data Collector", "[COL]")
label(4.9, 6.6, "• Fetches video list\n• Pulls transcripts\n• Stores to SQLite", MUTED, 7)

arrow(2.7, 8.5, 3.5, 8.0)
arrow(2.7, 7.15, 3.5, 7.6)
arrow(2.7, 6.05, 3.5, 7.3)

# ── SQLite DB ──────────────────────────────────────────────────────────────
box(7.0, 7.3, 2.2, 1.2, YELLOW, "SQLite DB", "Persistent store", "[DB]")
arrow(6.3, 7.7, 7.0, 7.8)

# ── Agent 2 ────────────────────────────────────────────────────────────────
box(3.5, 4.8, 2.8, 1.6, GREEN, "Agent 2", "Transcript Processor", "[CLN]")
label(4.9, 4.5, "• Remove timestamps\n• Strip filler words\n• Normalize text", MUTED, 7)

arrow(4.9, 6.9, 4.9, 6.4)
arrow(4.9, 4.8, 7.0, 7.4)  # writes to DB

# ── Agent 3 ────────────────────────────────────────────────────────────────
box(7.0, 4.2, 3.2, 2.8, PINK, "Agent 3", "Analysis Agent", "[LLM]")
# sub-boxes inside
for i, (sub, clr) in enumerate([
    ("Entity Extraction", "#a78bfa"),
    ("Topic Modeling", "#38bdf8"),
    ("Sentiment Analysis", "#34d399"),
    ("Trend Detection", "#fbbf24"),
]):
    sy = 4.35 + i * 0.58
    ax.add_patch(FancyBboxPatch((7.15, sy), 2.9, 0.45,
                                boxstyle="round,pad=0.05",
                                linewidth=1, edgecolor=clr, facecolor="#12121f"))
    ax.text(8.6, sy + 0.22, sub, ha="center", va="center", fontsize=7.5, color=clr)

arrow(7.0, 7.3, 8.6, 7.0)   # DB → Agent 3
arrow(8.6, 4.2, 8.6, 3.5)   # Agent 3 → DB write

# ── Gemini LLM ────────────────────────────────────────────────────────────
box(11.0, 5.2, 2.4, 1.2, YELLOW, "Gemini 1.5 Flash", "LLM (free tier)", "[GEM]")
arrow(10.2, 5.5, 11.0, 5.7)
arrow(11.0, 5.6, 10.2, 4.9)
label(10.6, 5.15, "prompt/response", MUTED, 6.5)

# ── Agent 4 ────────────────────────────────────────────────────────────────
box(3.5, 2.6, 2.8, 1.6, YELLOW, "Agent 4", "Report Generator", "[RPT]")
label(4.9, 2.3, "• Yearly 1000-word summaries\n• HTML/PDF report\n• Jinja2 templating", MUTED, 7)

arrow(8.6, 4.2, 4.9, 4.2)
arrow(4.9, 2.6, 4.9, 2.2)

# ── Outputs ───────────────────────────────────────────────────────────────
box(0.3, 0.6, 2.4, 1.2, GREEN, "HTML/PDF Report", "Annual summaries", "[HTM]")
box(3.2, 0.6, 2.4, 1.2, PURPLE, "Streamlit Dashboard", "Interactive UI", "[DSH]")
box(6.1, 0.6, 2.4, 1.2, PINK, "Knowledge Graph", "Entity network", "[KG]")
box(9.0, 0.6, 2.4, 1.2, BLUE, "Q&A Chat", "Gemini-powered", "[QA]")

arrow(4.9, 2.6, 1.5, 1.8)
arrow(4.9, 2.6, 4.4, 1.8)
arrow(8.6, 3.5, 7.3, 1.8)
arrow(11.0, 5.2, 10.2, 1.8)

ax.text(9, 0.25, "OUTPUTS", ha="center", fontsize=8, color=GREEN, fontweight="bold")
ax.text(9, 0.05, "Pipeline is fully automated — run python main.py for end-to-end execution",
        ha="center", fontsize=7.5, color=MUTED)

# ── Legend ─────────────────────────────────────────────────────────────────
legend_items = [
    mpatches.Patch(color=PURPLE, label="Agents"),
    mpatches.Patch(color=BLUE, label="Data Sources"),
    mpatches.Patch(color=YELLOW, label="LLM / Storage"),
    mpatches.Patch(color=GREEN, label="Processing / Output"),
    mpatches.Patch(color=PINK, label="Analysis"),
]
ax.legend(handles=legend_items, loc="lower right", facecolor=CARD,
          edgecolor=PURPLE, labelcolor=TEXT, fontsize=8)

plt.tight_layout()
plt.savefig(str(OUT_PATH), dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"Architecture diagram saved to: {OUT_PATH}")
