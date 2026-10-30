import html
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
from agent import (
    deep_research_benchmarks,
    evaluate_qualitative,
    evaluate_quantitative,
    synthesize_benchmark,
)
from history import compute_trend, find_previous_run, load_history, log_run
from report_export import build_csv_report, build_pdf_report
from style import confidence_badge, inject_base_css, render_hero, verdict_badge


def esc(text):
    """Escape $ so Streamlit's markdown renderer doesn't treat dollar amounts as LaTeX math."""
    return str(text).replace("$", "\\$")


def html_esc(text):
    """Escape text for embedding inside a raw HTML string (unsafe_allow_html=True).
    No markdown $ escaping needed here -- plain HTML text isn't LaTeX-parsed."""
    return html.escape(str(text))


st.set_page_config(page_title="BENCH-FIT", page_icon="📏", layout="centered")
inject_base_css()
render_hero()

for key in [
    "search_results",
    "trace",
    "gaps",
    "benchmark",
    "benchmark_confirmed",
    "quant_result",
    "qual_result",
    "inputs",
    "previous_run",
]:
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.benchmark_confirmed is None:
    st.session_state.benchmark_confirmed = False
if "active_step" not in st.session_state:
    st.session_state.active_step = 0

with st.sidebar:
    st.markdown("### Evaluation history")
    history = load_history()
    if not history:
        st.caption("No evaluations yet.")
    else:
        for entry in reversed(history[-10:]):
            st.markdown(
                f"**{esc(entry['industry'])}** ({esc(entry['channel'])})  \n"
                f"{esc(entry['stage'])} · {esc(entry['business_model'])} · {esc(entry['campaign_type'])}  \n"
                f"{entry['metric_count']} metrics · {entry['timestamp'][:16].replace('T', ' ')}"
            )
            st.divider()

# ---- Step navigation (card stepper) ----
step_names = ["Context", "Benchmark", "Report"]
unlocked = [True, bool(st.session_state.benchmark), bool(st.session_state.quant_result)]
st.session_state.active_step = min(st.session_state.active_step, max(i for i, u in enumerate(unlocked) if u))

nav_cols = st.columns(3)
for i, (col, name) in enumerate(zip(nav_cols, step_names)):
    with col:
        is_active = st.session_state.active_step == i
        if st.button(
            f"0{i + 1} · {name}",
            key=f"nav_{i}",
            type="primary" if is_active else "secondary",
            disabled=not unlocked[i],
            use_container_width=True,
        ):
            st.session_state.active_step = i
            st.rerun()

st.markdown('<div class="bf-hr"></div>', unsafe_allow_html=True)

active_step = st.session_state.active_step

# ---- Step 1: Campaign context ----
if active_step == 0:
    st.markdown("### Campaign context")
    with st.container(border=True):
        with st.form("context_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                industry = st.text_input("Industry / sector", placeholder="e.g. vegan skincare, B2B SaaS")
                channel = st.selectbox(
                    "Channel", ["Instagram", "Google Ads", "Facebook", "TikTok", "YouTube", "Email", "Other"]
                )
            with col2:
                stage = st.selectbox("Company stage", ["Startup", "SMB", "Mid-size", "Enterprise"])
                campaign_type = st.text_input("Campaign type", placeholder="e.g. brand awareness, conversion")
            with col3:
                business_model = st.selectbox("Business model", ["B2C", "B2B", "D2C"])

            col4, col5 = st.columns(2)
            with col4:
                audience_type = st.selectbox(
                    "Audience type", ["Prospecting / Cold", "Retargeting / Warm", "Mixed / Full-funnel"]
                )
            with col5:
                funnel_stage = st.selectbox("Funnel stage", ["Awareness", "Consideration", "Conversion", "Retention"])

            actual_metrics = st.text_area(
                "Actual performance metrics",
                placeholder="e.g.\nCTR: 2.3%\nConversion rate: 1.1%\nCPA: $14\nROAS: 3.2x",
                height=100,
            )
            volume_context = st.text_input(
                "Spend & volume (optional — improves the confidence read)",
                placeholder="e.g. $2,400 spend, 85K impressions, 1,200 clicks",
            )
            creative_text = st.text_area(
                "Creative / customer-response text (optional, for qualitative scoring)",
                placeholder="Paste ad copy, captions, or customer comments here",
                height=100,
            )
            submitted = st.form_submit_button("Deep-research industry benchmarks →", type="primary")

    if submitted:
        if not (industry and campaign_type and actual_metrics):
            st.warning("Please fill in industry, campaign type, and actual metrics.")
        else:
            status = st.empty()
            with st.spinner("Agent is researching, then reviewing its own coverage for gaps..."):
                results, trace, gaps = deep_research_benchmarks(
                    industry,
                    stage,
                    business_model,
                    channel,
                    campaign_type,
                    audience_type,
                    funnel_stage,
                    actual_metrics,
                    on_step=lambda s: status.write(f"🔎 {s}"),
                )
                benchmark = synthesize_benchmark(
                    industry,
                    stage,
                    business_model,
                    channel,
                    campaign_type,
                    audience_type,
                    funnel_stage,
                    actual_metrics,
                    results,
                )
            status.empty()
            st.session_state.search_results = results
            st.session_state.trace = trace
            st.session_state.gaps = gaps
            st.session_state.benchmark = benchmark
            st.session_state.benchmark_confirmed = False
            st.session_state.quant_result = None
            st.session_state.qual_result = None
            st.session_state.inputs = {
                "industry": industry,
                "stage": stage,
                "business_model": business_model,
                "channel": channel,
                "campaign_type": campaign_type,
                "audience_type": audience_type,
                "funnel_stage": funnel_stage,
                "actual_metrics": actual_metrics,
                "volume_context": volume_context,
                "creative_text": creative_text,
            }
            st.session_state.active_step = 1
            st.rerun()

# ---- Step 2: Benchmark review / confirmed ----
if active_step == 1:
    benchmark = st.session_state.benchmark
    if benchmark and not st.session_state.benchmark_confirmed:
        st.markdown("### Review the proposed benchmark")
        st.markdown(
            '<div class="bf-gate"><b>This is a draft, not a verdict.</b> Adjust any range or '
            "reasoning before committing to it — you know your context better than the agent does. "
            "Nothing is scored until you confirm.</div>",
            unsafe_allow_html=True,
        )

        with st.expander(
            f"🤖 Agent trace — {len(st.session_state.trace)} searches across 2 research passes "
            f"({len(st.session_state.search_results)} unique sources)"
        ):
            phase_tags = {"gap-fill": " 🔍 *(gap-fill pass)*", "broaden": " 🌐 *(broadened pass)*"}
            for step in st.session_state.trace:
                tag = phase_tags.get(step.get("phase"), "")
                st.write(f"- Searched \"{esc(step['query'])}\" → {step['result_count']} results{tag}")
            if st.session_state.gaps:
                st.caption(f"Self-identified gaps before the second pass: {esc(st.session_state.gaps)}")

        if benchmark.get("context_notes"):
            st.info(esc(benchmark["context_notes"]))

        for i, m in enumerate(benchmark["metrics"]):
            with st.container(border=True):
                st.markdown(
                    f'<div class="bf-metric-name">{html_esc(m["name"])} {confidence_badge(m.get("confidence"))}</div>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.text_input("Reasonable range", value=m["reasonable_range"], key=f"range_{i}")
                with c2:
                    st.text_area("Reasoning", value=m["reasoning"], key=f"reasoning_{i}", height=70)
                sources = m.get("sources")
                if sources:
                    domain_count = len(
                        {urlparse(s["url"]).netloc for s in sources if isinstance(s, dict) and s.get("url")}
                    )
                    agreement_note = (
                        f" ({domain_count} independent sources)" if domain_count >= 2 else ""
                    )
                    labels = [
                        (f'{s.get("title", s.get("url", ""))} {s["url"]}' if isinstance(s, dict) else str(s))
                        for s in sources
                    ]
                    st.caption("Sources" + agreement_note + ": " + esc(" · ".join(labels)))

        if st.button("✅ Confirm this benchmark & continue", type="primary"):
            confirmed_metrics = []
            for i, m in enumerate(benchmark["metrics"]):
                confirmed_metrics.append(
                    {
                        "name": m["name"],
                        "reasonable_range": st.session_state[f"range_{i}"],
                        "reasoning": st.session_state[f"reasoning_{i}"],
                        "confidence": m.get("confidence", ""),
                    }
                )
            st.session_state.benchmark = {
                "metrics": confirmed_metrics,
                "context_notes": benchmark.get("context_notes", ""),
            }
            st.session_state.benchmark_confirmed = True
            st.rerun()

    if st.session_state.benchmark_confirmed:
        st.markdown("### Confirmed benchmark")
        confirmed = st.session_state.benchmark
        with st.container(border=True):
            for m in confirmed["metrics"]:
                st.markdown(
                    f'<div class="bf-metric-name">{html_esc(m["name"])}: {html_esc(m["reasonable_range"])} '
                    f'{confidence_badge(m.get("confidence"))}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(esc(m["reasoning"]))

        if st.session_state.quant_result is None:
            if st.button("📊 Run evaluation against this benchmark", type="primary"):
                inputs = st.session_state.inputs
                previous_run = find_previous_run(history, inputs["industry"], inputs["channel"], inputs["campaign_type"])
                with st.spinner("Scoring actual results against the confirmed benchmark..."):
                    quant = evaluate_quantitative(
                        confirmed, inputs["actual_metrics"], inputs.get("volume_context"), previous_run
                    )
                    qual = None
                    if inputs["creative_text"].strip():
                        qual = evaluate_qualitative(
                            inputs["creative_text"], inputs["industry"], inputs["business_model"], inputs["channel"]
                        )
                st.session_state.quant_result = quant
                st.session_state.qual_result = qual
                st.session_state.previous_run = previous_run
                log_run(
                    inputs["industry"],
                    inputs["stage"],
                    inputs["business_model"],
                    inputs["channel"],
                    inputs["campaign_type"],
                    inputs["audience_type"],
                    inputs["funnel_stage"],
                    [{"metric": r["metric"], "actual": r["actual"]} for r in quant["results"]],
                )
                st.session_state.active_step = 2
                st.rerun()

# ---- Step 3: Evaluation report ----
if active_step == 2:
    quant_result = st.session_state.quant_result
    if quant_result:
        inputs = st.session_state.inputs
        qual_result = st.session_state.qual_result
        previous_run = st.session_state.previous_run

        trend_map = {}
        if previous_run:
            prev_by_metric = {m["metric"].lower(): m["actual"] for m in previous_run["metrics"]}
            for r in quant_result["results"]:
                prev_actual = prev_by_metric.get(r["metric"].lower())
                if prev_actual is not None:
                    trend = compute_trend(r["actual"], prev_actual)
                    if trend:
                        trend_map[r["metric"].lower()] = trend

        st.markdown("### Evaluation report")

        chips = "".join(
            f'<span class="bf-chip">{html_esc(v)}</span>'
            for v in [
                inputs["industry"],
                inputs["stage"],
                inputs["business_model"],
                inputs["channel"],
                inputs["campaign_type"],
                inputs.get("audience_type", ""),
                inputs.get("funnel_stage", ""),
            ]
            if v
        )
        st.markdown(f'<div class="bf-context-chips">{chips}</div>', unsafe_allow_html=True)

        if previous_run:
            st.caption(
                f"📈 Compared against your previous run for this context "
                f"({previous_run['timestamp'][:10]})."
            )

        st.markdown(
            f'<div class="bf-exec-summary"><b>Executive summary.</b> {html_esc(quant_result["overall_feedback"])}</div>',
            unsafe_allow_html=True,
        )

        verdict_counts = {}
        for r in quant_result["results"]:
            verdict_counts[r["verdict"]] = verdict_counts.get(r["verdict"], 0) + 1
        tile_order = ["Above benchmark", "Within benchmark", "Below benchmark", "Estimated (general benchmark)"]
        tiles_html = "".join(
            f'<div class="bf-stat-tile"><div class="bf-stat-number">{verdict_counts.get(v, 0)}</div>'
            f'<div class="bf-stat-label">{html_esc(v)}</div></div>'
            for v in tile_order
            if verdict_counts.get(v, 0) > 0
        )
        if tiles_html:
            st.markdown(f'<div class="bf-stat-row">{tiles_html}</div>', unsafe_allow_html=True)

        def trend_cell(metric_name):
            trend = trend_map.get(metric_name.lower())
            if not trend:
                return "—"
            arrow = "▲" if trend["pct_change"] > 0 else "▼" if trend["pct_change"] < 0 else "–"
            return f'{arrow} {abs(trend["pct_change"]):.1f}% <span style="color:#5B5B63;">(was {html_esc(trend["previous"])})</span>'

        has_trend = bool(trend_map)
        trend_header = "<th>vs. Last Run</th>" if has_trend else ""
        rows_html = "".join(
            f'<tr><td><b>{html_esc(r["metric"])}</b></td><td>{html_esc(r["actual"])}</td>'
            f'<td>{html_esc(r["benchmark"])}</td><td>{verdict_badge(r["verdict"])}</td>'
            + (f"<td>{trend_cell(r['metric'])}</td>" if has_trend else "")
            + "</tr>"
            for r in quant_result["results"]
        )
        st.markdown(
            f'<table class="bf-report-table"><thead><tr><th>Metric</th><th>Actual</th>'
            f"<th>Benchmark</th><th>Verdict</th>{trend_header}</tr></thead><tbody>{rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

        st.markdown("#### Detailed analysis")
        for r in quant_result["results"]:
            with st.container(border=True):
                st.markdown(
                    f'<div class="bf-metric-name">{html_esc(r["metric"])} {verdict_badge(r["verdict"])}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(esc(r["feedback"]))

        recommendations = quant_result.get("recommendations", [])
        if recommendations:
            st.markdown("#### Recommended next steps")
            items = "".join(f"<li>{html_esc(rec)}</li>" for rec in recommendations)
            st.markdown(f'<ul class="bf-rec-list">{items}</ul>', unsafe_allow_html=True)

        if qual_result:
            st.markdown("#### Qualitative — LLM-judge on creative / customer-response text")
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Tone fit", f"{qual_result['tone_fit_score']}/5")
                st.caption(esc(qual_result["tone_fit_reason"]))
            with c2:
                st.metric("Message clarity", f"{qual_result['clarity_score']}/5")
                st.caption(esc(qual_result["clarity_reason"]))
            st.info(esc(qual_result["overall_feedback"]))

        st.caption(
            "Every number above traces back to: the agent's research → the benchmark you reviewed "
            "and approved → this comparison. Nothing here was decided without your sign-off."
        )

        st.markdown("#### Export")
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "⬇ Download PDF report",
                data=build_pdf_report(inputs, quant_result, qual_result, trend_map, generated_at),
                file_name=f"benchfit-report-{inputs['industry'].replace(' ', '-').lower()}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "⬇ Download CSV (metrics)",
                data=build_csv_report(quant_result, trend_map),
                file_name=f"benchfit-metrics-{inputs['industry'].replace(' ', '-').lower()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
