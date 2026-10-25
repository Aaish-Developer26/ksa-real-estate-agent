"""Script to generate professional, publication-quality architecture diagrams for the Project Proposal."""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Styling Palette
NAVY = "#0F2537"
STEEL_BLUE = "#1B6B93"
CYAN = "#0284C7"
AMBER = "#D97706"
EMERALD = "#059669"
CRIMSON = "#DC2626"
SLATE = "#475569"
LIGHT_BG = "#F8FAFC"
WHITE = "#FFFFFF"
BORDER_GRAY = "#CBD5E1"


def create_figure_1():
    """Figure 1: High-Level End-to-End System Architecture Flowchart."""
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
    ax.set_facecolor(LIGHT_BG)
    fig.patch.set_facecolor(LIGHT_BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.5)
    ax.axis("off")

    # Title
    ax.text(6, 6.1, "Riyadh Real Estate Investment Multi-Agent System Flow", 
            ha="center", va="center", fontsize=15, fontweight="bold", color=NAVY)
    ax.text(6, 5.75, "From Multilingual Portals to Structured, Risk-Audited Investment Due Diligence", 
            ha="center", va="center", fontsize=10, color=SLATE)

    # Box Helper
    def draw_box(x, y, w, h, title, subtitle, bg_color, border_color, title_color=WHITE, sub_color="#E2E8F0"):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.15",
                                      linewidth=1.5, edgecolor=border_color, facecolor=bg_color)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.62, title, ha="center", va="center", fontsize=9.5, fontweight="bold", color=title_color)
        ax.text(x + w/2, y + h*0.32, subtitle, ha="center", va="center", fontsize=7.5, color=sub_color, multialignment="center")

    def draw_arrow(x1, y1, x2, y2, color=SLATE, style="->"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle=style, color=color, lw=1.6, mutation_scale=12, shrinkA=3, shrinkB=3))

    # Top Row: Ingestion & Normalization
    draw_box(0.5, 4.2, 2.0, 1.1, "Listing Portals", "Arabic & English\nAqar, Bayut, Private", WHITE, BORDER_GRAY, NAVY, SLATE)
    draw_box(3.0, 4.2, 2.2, 1.1, "1. Sourcing Agent", "Brave Search MCP\nSynthetic Mock Datasets", STEEL_BLUE, NAVY)
    draw_box(5.7, 4.2, 2.4, 1.1, "2. Cleaning Agent", "Two-Pass Hybrid Engine\nDeterministic + Semantic", STEEL_BLUE, NAVY)
    draw_box(8.6, 4.2, 2.9, 1.1, "Normalized Property Store", "PostgreSQL 16 + TimescaleDB\nHypertables & Audit Logs", NAVY, CYAN)

    draw_arrow(2.5, 4.75, 3.0, 4.75)
    draw_arrow(5.2, 4.75, 5.7, 4.75)
    draw_arrow(8.1, 4.75, 8.6, 4.75)

    # Downward flow to Analysis
    draw_arrow(10.05, 4.2, 10.05, 3.4)

    # Middle Row: Analytical & Regulatory Intelligence
    draw_box(1.5, 2.3, 2.8, 1.1, "3. Analyst Agent", "Quant Tools (Z-score, IQR)\nUndervaluation Discount %", AMBER, NAVY)
    draw_box(4.8, 2.3, 2.8, 1.1, "4. Risk Agent", "Saudi Compliance Engine\nRERA, Waqf, Foreign Limits", EMERALD, NAVY)
    draw_box(8.1, 2.3, 2.8, 1.1, "Report Composer", "Synthesis & Rationale\nExecutive Due Diligence", STEEL_BLUE, NAVY)

    draw_arrow(8.6, 2.85, 7.6, 2.85, style="<-")
    draw_arrow(4.8, 2.85, 4.3, 2.85, style="<-")
    # Feed from DB to Analyst
    ax.annotate("", xy=(2.9, 3.4), xytext=(9.0, 4.2),
                arrowprops=dict(arrowstyle="->", color=CYAN, lw=1.5, ls="--", mutation_scale=10))
    ax.text(5.5, 3.75, "Empirical Benchmark SQL Queries", ha="center", va="center", fontsize=7.5, color=CYAN, fontweight="bold")

    # Bottom Row: Delivery & Human Governance
    draw_arrow(2.9, 2.3, 2.9, 1.5)
    draw_arrow(6.2, 2.3, 6.2, 1.5)
    draw_arrow(9.5, 2.3, 9.5, 1.5)

    draw_box(1.2, 0.4, 9.6, 1.0, "FastAPI Service (Async REST)  →  Live Streamlit / Next.js Dashboard",
             "Ranked Investment Pipeline  •  Human-in-the-Loop Due Diligence Review Before Capital Allocation",
             NAVY, CYAN, WHITE, "#94A3B8")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig1_system_architecture.png")
    plt.savefig(path, dpi=300, facecolor=LIGHT_BG, bbox_inches="tight")
    plt.close()
    print(f"Generated {path}")


def create_figure_2():
    """Figure 2: LangGraph State Machine & Runtime Harness DAG."""
    fig, ax = plt.subplots(figsize=(12, 6.0), dpi=300)
    ax.set_facecolor(LIGHT_BG)
    fig.patch.set_facecolor(LIGHT_BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.0)
    ax.axis("off")

    # Title
    ax.text(6, 5.65, "LangGraph State Machine Topology & Runtime Harness", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=NAVY)
    ax.text(6, 5.3, "Stateful DAG Execution with Pure Deterministic Edge Routing & Dead-Letter Error Sink", 
            ha="center", va="center", fontsize=9.5, color=SLATE)

    def draw_node(x, y, w, h, title, sub, bg, border):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                                      linewidth=1.4, edgecolor=border, facecolor=bg)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.62, title, ha="center", va="center", fontsize=9, fontweight="bold", color=WHITE)
        ax.text(x + w/2, y + h*0.32, sub, ha="center", va="center", fontsize=7.2, color="#E2E8F0", multialignment="center")

    def draw_arrow(x1, y1, x2, y2, color=SLATE, label=None, label_pos=0.5):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.5, mutation_scale=10))
        if label:
            lx = x1 + (x2 - x1) * label_pos
            ly = y1 + (y2 - y1) * label_pos + 0.16
            ax.text(lx, ly, label, ha="center", va="center", fontsize=7, color=color, fontweight="bold")

    # Master State Bus across top
    bus_rect = patches.FancyBboxPatch((0.5, 4.4), 11.0, 0.6, boxstyle="round,pad=0.05,rounding_size=0.08",
                                      linewidth=1.2, edgecolor=CYAN, facecolor="#E0F2FE", linestyle="--")
    ax.add_patch(bus_rect)
    ax.text(6.0, 4.7, "Central LangGraph AgentState Bus (Pydantic v2 Contract • operator.add Reducers • Checkpointer)",
            ha="center", va="center", fontsize=8.5, fontweight="bold", color=NAVY)

    # Main DAG Nodes
    draw_node(0.5, 2.7, 1.8, 1.1, "Sourcing Agent", "MCP Web Search\nMock Ingestion", STEEL_BLUE, NAVY)
    draw_node(2.8, 2.7, 1.9, 1.1, "Cleaning Agent", "Normalizer (regex)\nLiteLLM Enrichment", STEEL_BLUE, NAVY)
    draw_node(5.2, 2.7, 1.9, 1.1, "Analyst Agent", "Quant Tools\nBenchmarking", AMBER, NAVY)
    draw_node(7.6, 2.7, 1.9, 1.1, "Risk Agent", "RERA / Waqf Rules\nCompliance Synth", EMERALD, NAVY)
    draw_node(10.0, 2.7, 1.6, 1.1, "Report Node", "Final Markdown\nAssembly", NAVY, CYAN)

    # Success Edges
    draw_arrow(2.3, 3.25, 2.8, 3.25, CYAN, "raw_listings > 0")
    draw_arrow(4.7, 3.25, 5.2, 3.25, CYAN, "cleaned_valid")
    draw_arrow(7.1, 3.25, 7.6, 3.25, CYAN, "analysis_ok")
    draw_arrow(9.5, 3.25, 10.0, 3.25, CYAN, "risk_ok")

    # Error Sink Node
    error_node_rect = patches.FancyBboxPatch((3.5, 0.8), 5.0, 1.0, boxstyle="round,pad=0.08,rounding_size=0.12",
                                             linewidth=1.5, edgecolor=CRIMSON, facecolor="#FEE2E2")
    ax.add_patch(error_node_rect)
    ax.text(6.0, 1.45, "Error Node (Dead-Letter Sink)", ha="center", va="center", fontsize=9.5, fontweight="bold", color=CRIMSON)
    ax.text(6.0, 1.1, "Graceful Degradation  •  Auditable Failure Record  •  Zero Unbounded Token Depletion",
            ha="center", va="center", fontsize=7.5, color=NAVY)

    # Conditional Failure Edges to Error Node
    for x_source in [1.4, 3.75, 6.15, 8.55]:
        ax.annotate("", xy=(6.0 if x_source > 5.0 else 5.2, 1.8), xytext=(x_source, 2.7),
                    arrowprops=dict(arrowstyle="->", color=CRIMSON, lw=1.2, ls=":", mutation_scale=8))

    ax.text(2.2, 2.0, "route_after_sourcing (failure)", fontsize=6.5, color=CRIMSON, rotation=-25)
    ax.text(8.8, 2.0, "route_after_risk (failure)", fontsize=6.5, color=CRIMSON, rotation=25)

    # Exit Edges
    draw_arrow(10.8, 2.7, 10.8, 1.8, NAVY, "END")
    draw_arrow(6.0, 0.8, 6.0, 0.2, CRIMSON, "END (Audited Failure)")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig2_langgraph_runtime_harness.png")
    plt.savefig(path, dpi=300, facecolor=LIGHT_BG, bbox_inches="tight")
    plt.close()
    print(f"Generated {path}")


def create_figure_3():
    """Figure 3: Neuro-Symbolic Division of Labor & Multi-Tier Fallback Hierarchy."""
    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
    ax.set_facecolor(LIGHT_BG)
    fig.patch.set_facecolor(LIGHT_BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.5)
    ax.axis("off")

    # Title
    ax.text(6, 6.15, "Neuro-Symbolic Division of Labor & Multi-Tier Fallback Hierarchy", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=NAVY)
    ax.text(6, 5.8, "Rigid Boundaries Between Probabilistic Semantic Inference and Deterministic Algorithmic Tooling", 
            ha="center", va="center", fontsize=9.5, color=SLATE)

    # Left Column: Probabilistic LLM Layer
    rect_llm = patches.FancyBboxPatch((0.5, 0.8), 5.2, 4.7, boxstyle="round,pad=0.1,rounding_size=0.15",
                                      linewidth=1.5, edgecolor=STEEL_BLUE, facecolor="#F0F9FF")
    ax.add_patch(rect_llm)
    ax.text(3.1, 5.2, "Cognitive & Semantic Layer (LLM via LiteLLM)", ha="center", va="center",
            fontsize=11, fontweight="bold", color=STEEL_BLUE)

    llm_items = [
        ("Arabic → English Translation", "Bilingual property title and landmark localization"),
        ("Contextual Type Inference", "Deduce villa/apartment from unstructured narrative"),
        ("Macro Market Narrative", "Contextualize district dynamics and regional drivers"),
        ("Executive Due Diligence Summary", "Synthesize compliance flags into PROCEED / CAUTION"),
        ("Strict Temperature Guardrail", "T=0.0 for extraction, T=0.2 for narrative synthesis")
    ]
    y_pos = 4.6
    for title, desc in llm_items:
        r = patches.FancyBboxPatch((0.8, y_pos - 0.55), 4.6, 0.65, boxstyle="round,pad=0.05,rounding_size=0.08",
                                   facecolor=WHITE, edgecolor="#BAE6FD", lw=1.0)
        ax.add_patch(r)
        ax.text(1.0, y_pos - 0.2, f"• {title}", fontsize=8.5, fontweight="bold", color=NAVY)
        ax.text(1.0, y_pos - 0.42, f"  {desc}", fontsize=7.2, color=SLATE)
        y_pos -= 0.8

    # Right Column: Deterministic Scientific & Regulatory Layer
    rect_det = patches.FancyBboxPatch((6.3, 0.8), 5.2, 4.7, boxstyle="round,pad=0.1,rounding_size=0.15",
                                      linewidth=1.5, edgecolor=EMERALD, facecolor="#ECFDF5")
    ax.add_patch(rect_det)
    ax.text(8.9, 5.2, "Deterministic Algorithmic Layer (Pure Python / SciPy)", ha="center", va="center",
            fontsize=11, fontweight="bold", color=EMERALD)

    det_items = [
        ("Numeral & Currency Sanitization", "Eastern Arabic numerals (٠-٩) and SAR/sqm conversions"),
        ("Z-Score Price Outlier Detection", "Scipy 3σ statistical anomaly and fraud detection"),
        ("Logarithmic Opportunity Ranking", "Formula: Discount % × ln(Area + 1) deterministic scoring"),
        ("Saudi Legal & Regulatory Engine", "10-digit RERA regex, Waqf inalienability, Foreign Zone lookup"),
        ("Post-Generation ID Intersection", "_validate_listing_ids strips hallucinated candidate IDs")
    ]
    y_pos = 4.6
    for title, desc in det_items:
        r = patches.FancyBboxPatch((6.6, y_pos - 0.55), 4.6, 0.65, boxstyle="round,pad=0.05,rounding_size=0.08",
                                   facecolor=WHITE, edgecolor="#A7F3D0", lw=1.0)
        ax.add_patch(r)
        ax.text(6.8, y_pos - 0.2, f"✓ {title}", fontsize=8.5, fontweight="bold", color=NAVY)
        ax.text(6.8, y_pos - 0.42, f"  {desc}", fontsize=7.2, color=SLATE)
        y_pos -= 0.8

    # Central Bi-Directional Guardrail Arrow
    ax.annotate("", xy=(6.2, 3.15), xytext=(5.8, 3.15),
                arrowprops=dict(arrowstyle="<->", color=NAVY, lw=2.0, mutation_scale=12))
    ax.text(6.0, 3.5, "Strict Contract\nBarrier", ha="center", va="center", fontsize=7.5, fontweight="bold", color=NAVY)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig3_neuro_symbolic_harness.png")
    plt.savefig(path, dpi=300, facecolor=LIGHT_BG, bbox_inches="tight")
    plt.close()
    print(f"Generated {path}")


def create_figure_4():
    """Figure 4: Dual-Track Optimization Framework: Harnessing vs Fine-Tuning."""
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=300)
    ax.set_facecolor(LIGHT_BG)
    fig.patch.set_facecolor(LIGHT_BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    # Title
    ax.text(6, 5.8, "Dual-Track Optimization: Architectural Harnessing vs. Model Fine-Tuning", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=NAVY)
    ax.text(6, 5.45, "Complementary Strategies for Enterprise Reliability, Domain Accuracy, and Data Sovereignty", 
            ha="center", va="center", fontsize=9.5, color=SLATE)

    # Track 1 Box: Harnessing
    r1 = patches.FancyBboxPatch((0.5, 0.6), 5.2, 4.5, boxstyle="round,pad=0.1,rounding_size=0.15",
                                linewidth=1.5, edgecolor=CYAN, facecolor=WHITE)
    ax.add_patch(r1)
    ax.text(3.1, 4.8, "Track 1: Agentic Harnessing (Runtime Control)", ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=NAVY)

    track1_points = [
        ("Finite-State Machine Topologies", "Constrains reasoning steps into a deterministic DAG"),
        ("Multi-Tier Fallback Engines", "In-memory math fallback when LLM fails or times out"),
        ("Post-Validation Filters", "Intersects LLM IDs with ground truth to eliminate hallucinations"),
        ("Token & Rate-Limit Management", "Batching with asyncio pauses, 15-45s exponential backoff"),
        ("Pydantic Contract Invariants", "Rejects malformed listings at the schema boundary")
    ]
    y = 4.2
    for t, d in track1_points:
        ax.text(0.8, y, f"▸ {t}:", fontsize=8.2, fontweight="bold", color=CYAN)
        ax.text(0.8, y - 0.22, f"   {d}", fontsize=7.2, color=SLATE)
        y -= 0.72

    # Track 2 Box: Fine-Tuning
    r2 = patches.FancyBboxPatch((6.3, 0.6), 5.2, 4.5, boxstyle="round,pad=0.1,rounding_size=0.15",
                                linewidth=1.5, edgecolor=AMBER, facecolor=WHITE)
    ax.add_patch(r2)
    ax.text(8.9, 4.8, "Track 2: Targeted Model Fine-Tuning (Model Level)", ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=NAVY)

    track2_points = [
        ("Saudi Dialect & Real Estate NER", "Adapts base models to local terminology (صك, سوم, دبلكس)"),
        ("PEFT / LoRA Parameter Efficiency", "Trains rank adapters with <16GB VRAM on bilingual pairs"),
        ("Structured Extraction Instruction Tuning", "Direct listing-to-Pydantic JSON with 0% schema errors"),
        ("DPO Alignment for Due Diligence", "Penalizes speculative claims; reinforces conservative risk tone"),
        ("Distillation for Saudi Sovereignty", "Distills 70B teacher to 8B student for local on-prem hosting")
    ]
    y = 4.2
    for t, d in track2_points:
        ax.text(6.6, y, f"▸ {t}:", fontsize=8.2, fontweight="bold", color=AMBER)
        ax.text(6.6, y - 0.22, f"   {d}", fontsize=7.2, color=SLATE)
        y -= 0.72

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig4_harnessing_vs_finetuning.png")
    plt.savefig(path, dpi=300, facecolor=LIGHT_BG, bbox_inches="tight")
    plt.close()
    print(f"Generated {path}")


def create_figure_5():
    """Figure 5: Automated Evaluation Harness (Ragas & CI/CD Quality Gating)."""
    fig, ax = plt.subplots(figsize=(12, 5.8), dpi=300)
    ax.set_facecolor(LIGHT_BG)
    fig.patch.set_facecolor(LIGHT_BG)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.8)
    ax.axis("off")

    # Title
    ax.text(6, 5.4, "Automated Continuous Evaluation Harness (Ragas CI/CD Suite)", 
            ha="center", va="center", fontsize=14, fontweight="bold", color=NAVY)
    ax.text(6, 5.05, "Quantitative Benchmarking Across Golden Datasets with Automated CI Regression Gates", 
            ha="center", va="center", fontsize=9.5, color=SLATE)

    def draw_box(x, y, w, h, title, subtitle, bg, border, tc=NAVY, sc=SLATE):
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                                      linewidth=1.3, edgecolor=border, facecolor=bg)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h*0.62, title, ha="center", va="center", fontsize=9, fontweight="bold", color=tc)
        ax.text(x + w/2, y + h*0.32, subtitle, ha="center", va="center", fontsize=7.2, color=sc, multialignment="center")

    def draw_arrow(x1, y1, x2, y2, color=SLATE, label=None):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.5, mutation_scale=10))
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, label, ha="center", va="center", fontsize=7, color=color, fontweight="bold")

    # Flow Left to Right
    draw_box(0.5, 2.3, 2.3, 1.4, "Golden Datasets", "evals/datasets/*.json\n15 Cleaning Records\n10 Analyst Records\n10 Risk Records", WHITE, BORDER_GRAY)
    draw_box(3.4, 2.3, 2.4, 1.4, "Evaluation Runner", "evals/runner.py\nSequential Plan Exec\nScore Aggregation", STEEL_BLUE, NAVY, WHITE, "#E2E8F0")

    draw_arrow(2.8, 3.0, 3.4, 3.0)

    # Judges Top & Bottom
    draw_box(6.4, 3.3, 2.8, 1.3, "Faithfulness Judge", "ChatLiteLLM + LangChain\nClaim-to-Context Grounding\nThreshold: ≥ 0.75", EMERALD, NAVY, WHITE, "#E2E8F0")
    draw_box(6.4, 1.4, 2.8, 1.3, "Answer Relevance Judge", "FastEmbed ONNX Embeddings\n(BAAI/bge-small-en-v1.5)\nThreshold: ≥ 0.75", AMBER, NAVY, WHITE, "#E2E8F0")

    draw_arrow(5.8, 3.3, 6.4, 3.8, CYAN)
    draw_arrow(5.8, 2.7, 6.4, 2.1, CYAN)

    # Synthesis & Gate
    draw_box(9.8, 2.3, 1.8, 1.4, "CI/CD Gate", "Overall: PASS / FAIL\nExit 0 on Success\nExit 1 on Regression", NAVY, CYAN, WHITE, "#94A3B8")

    draw_arrow(9.2, 3.8, 9.8, 3.3, EMERALD, "cleaning, analyst, risk")
    draw_arrow(9.2, 2.1, 9.8, 2.7, AMBER, "analyst relevance")

    # Bottom Callout
    callout = patches.FancyBboxPatch((1.5, 0.3), 9.0, 0.7, boxstyle="round,pad=0.05,rounding_size=0.08",
                                     facecolor="#F1F5F9", edgecolor=BORDER_GRAY, lw=1.0)
    ax.add_patch(callout)
    ax.text(6.0, 0.65, "Output Artifact: evals/reports/eval_report_TIMESTAMP.json with full record-level telemetry",
            ha="center", va="center", fontsize=8, color=NAVY, fontweight="bold")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig5_evaluation_harness.png")
    plt.savefig(path, dpi=300, facecolor=LIGHT_BG, bbox_inches="tight")
    plt.close()
    print(f"Generated {path}")


if __name__ == "__main__":
    create_figure_1()
    create_figure_2()
    create_figure_3()
    create_figure_4()
    create_figure_5()
    print("All 5 publication-quality diagrams generated successfully.")
