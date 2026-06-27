"""Streamlit MVP dashboard for the KSA RE Investment Agent.

Communicates with FastAPI backend via HTTP only. Never imports src
modules directly — this dashboard runs as a separate process.
"""

import httpx
import streamlit as st

API_BASE_URL = "http://localhost:8000"

DISTRICTS = [
    "Olaya",
    "Al_Malqa",
    "Al_Nakheel",
    "Al_Rawdah",
    "KAFD",
    "Al_Naseem",
    "Al_Shifa",
    "Al_Wurud",
]

st.set_page_config(
    page_title="KSA RE Investment Agent",
    page_icon="🏙️",
    layout="wide",
)

st.title("🏙️ Riyadh Real Estate Investment Intelligence")
st.caption("Multi-agent AI pipeline — Powered by LangGraph + LiteLLM")

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🚀 Run Analysis",
        "📊 Live Status",
        "📋 Investment Report",
        "🗺️ Market Overview",
    ]
)

# ── Tab 1: Run Analysis ─────────────────────────────────────────
with tab1:
    st.subheader("Configure Analysis Pipeline")

    selected_districts = st.multiselect(
        "Select Riyadh Districts",
        options=DISTRICTS,
        default=["Olaya", "Al_Malqa", "KAFD"],
    )

    max_listings = st.slider(
        "Max Listings per District",
        min_value=5,
        max_value=50,
        value=10,
        step=5,
    )

    use_mock = st.checkbox(
        "Use Mock Data (development mode)",
        value=True,
        help="Uncheck to use live Brave Search API",
    )

    if st.button("🚀 Run Analysis", type="primary"):
        if not selected_districts:
            st.error("Please select at least one district")
        else:
            with st.spinner("Queuing analysis pipeline..."):
                try:
                    response = httpx.post(
                        f"{API_BASE_URL}/analyze",
                        json={
                            "districts": selected_districts,
                            "max_listings_per_district": max_listings,
                            "use_mock_data": use_mock,
                        },
                        timeout=10.0,
                    )
                    if response.status_code == 202:
                        data = response.json()
                        st.session_state["run_id"] = data["run_id"]
                        st.success(f"✅ Pipeline queued! Run ID: `{data['run_id']}`")
                        st.info(
                            "Switch to **Live Status** tab to monitor progress"
                        )
                    else:
                        st.error(f"Failed: {response.status_code} — {response.text}")
                except httpx.ConnectError:
                    st.error(
                        "Cannot connect to API. Is the FastAPI server running? "
                        "Run: `uvicorn src.api.main:app --reload`"
                    )

# ── Tab 2: Live Status ──────────────────────────────────────────
with tab2:
    st.subheader("Pipeline Execution Status")

    run_id_input = st.text_input(
        "Run ID",
        value=st.session_state.get("run_id", ""),
        placeholder="Paste run_id from Run Analysis tab",
    )

    PHASE_ORDER = [
        "initialized",
        "sourcing_complete",
        "cleaning_complete",
        "analysis_complete",
        "risk_complete",
        "complete",
    ]

    PHASE_LABELS = {
        "initialized": "🔄 Initialized",
        "sourcing_complete": "🔍 Sourcing Complete",
        "cleaning_complete": "🧹 Cleaning Complete",
        "analysis_complete": "📊 Analysis Complete",
        "risk_complete": "⚖️ Risk Assessment Complete",
        "complete": "✅ Pipeline Complete",
        "failed": "❌ Failed",
    }

    if run_id_input:
        if st.button("🔄 Refresh Status"):
            try:
                resp = httpx.get(
                    f"{API_BASE_URL}/analyze/{run_id_input}",
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    phase = data.get("current_phase", "unknown")
                    status_val = data.get("status", "unknown")

                    st.metric("Status", status_val.upper())
                    st.metric("Current Phase", PHASE_LABELS.get(phase, phase))

                    if phase in PHASE_ORDER:
                        progress = (PHASE_ORDER.index(phase) + 1) / len(PHASE_ORDER)
                        st.progress(progress)

                    if status_val == "complete":
                        st.success(
                            "Pipeline complete! Check the **Investment Report** tab."
                        )
                        st.session_state["report_run_id"] = run_id_input
                    elif status_val == "failed":
                        st.error(f"Error: {data.get('error')}")

            except httpx.ConnectError:
                st.error("Cannot connect to API server")

# ── Tab 3: Investment Report ────────────────────────────────────
with tab3:
    st.subheader("Investment Intelligence Report")

    report_run_id = st.text_input(
        "Run ID for Report",
        value=st.session_state.get("report_run_id", ""),
    )

    if report_run_id and st.button("📋 Load Report"):
        try:
            resp = httpx.get(
                f"{API_BASE_URL}/analyze/{report_run_id}",
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                report = data.get("investment_report")
                if report:
                    st.text_area(
                        "Investment Report",
                        value=report,
                        height=500,
                    )
                    st.download_button(
                        "⬇️ Download Report",
                        data=report,
                        file_name=f"re_report_{report_run_id}.txt",
                        mime="text/plain",
                    )
                else:
                    st.warning(
                        "Report not ready yet. Status: "
                        + data.get("status", "unknown")
                    )
        except httpx.ConnectError:
            st.error("Cannot connect to API server")

# ── Tab 4: Market Overview ──────────────────────────────────────
with tab4:
    st.subheader("Riyadh District Market Overview")

    selected_district = st.selectbox("Select District", options=DISTRICTS)

    if st.button("🔍 Load Listings"):
        try:
            resp = httpx.get(
                f"{API_BASE_URL}/listings/{selected_district}",
                params={"limit": 50},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                listings = data.get("listings", [])

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Listings", data["total"])
                col2.metric(
                    "Avg Price/m²", f"SAR {data.get('avg_price_per_sqm', 0):,.0f}"
                )
                col3.metric("District", selected_district)

                if listings:
                    import pandas as pd

                    df = pd.DataFrame(listings)
                    st.dataframe(
                        df[
                            [
                                "listing_id",
                                "title_en",
                                "price_sar",
                                "area_sqm",
                                "price_per_sqm",
                                "property_type",
                                "rera_number",
                            ]
                        ],
                        use_container_width=True,
                    )
                    st.bar_chart(df.set_index("listing_id")["price_per_sqm"])
            elif resp.status_code == 404:
                st.warning(
                    f"No listings found for {selected_district}. "
                    "Run an analysis first."
                )
            else:
                st.error(f"API error: {resp.status_code}")
        except httpx.ConnectError:
            st.error("Cannot connect to API server")
