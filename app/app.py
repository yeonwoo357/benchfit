import html
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit as st
from agent import (
    deep_research_benchmarks,
    evaluate_qualitative,
    evaluate_quantitative,
    synthesize_benchmark,
)
from history import load_history, log_run
from style import inject_base_css, render_hero, verdict_badge


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

for key in ["search_results", "trace", "gaps", "benchmark", "benchmark_confirmed", "quant_result", "qual_result", "inputs"]:
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

            actual_metrics = st.text_area(
                "Actual performance metrics",
                placeholder="e.g.\nCTR: 2.3%\nConversion rate: 1.1%\nCPA: $14\nROAS: 3.2x",
                height=100,
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
                    industry, stage, business_model, channel, campaign_type, on_step=lambda s: status.write(f"🔎 {s}")
                )
                benchmark = synthesize_benchmark(industry, stage, business_model, channel, campaign_type, results)
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
                "actual_metrics": actual_metrics,
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
            for step in st.session_state.trace:
                tag = " 🔍 *(gap-fill pass)*" if step.get("phase") == "gap-fill" else ""
                st.write(f"- Searched \"{esc(step['query'])}\" → {step['result_count']} results{tag}")
            if st.session_state.gaps:
                st.caption(f"Self-identified gaps before the second pass: {esc(st.session_state.gaps)}")

        if benchmark.get("context_notes"):
            st.info(esc(benchmark["context_notes"]))

        for i, m in enumerate(benchmark["metrics"]):
            with st.container(border=True):
                st.markdown(f'<div class="bf-metric-name">{html_esc(m["name"])}</div>', unsafe_allow_html=True)
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.text_input("Reasonable range", value=m["reasonable_range"], key=f"range_{i}")
                with c2:
                    st.text_area("Reasoning", value=m["reasoning"], key=f"reasoning_{i}", height=70)
                if m.get("sources"):
                    st.caption("Sources: " + esc(" · ".join(m["sources"])))

        if st.button("✅ Confirm this benchmark & continue", type="primary"):
            confirmed_metrics = []
            for i, m in enumerate(benchmark["metrics"]):
                confirmed_metrics.append(
                    {
                        "name": m["name"],
                        "reasonable_range": st.session_state[f"range_{i}"],
                        "reasoning": st.session_state[f"reasoning_{i}"],
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
                    f'<div class="bf-metric-name">{html_esc(m["name"])}: {html_esc(m["reasonable_range"])}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(esc(m["reasoning"]))

        if st.session_state.quant_result is None:
            if st.button("📊 Run evaluation against this benchmark", type="primary"):
                inputs = st.session_state.inputs
                with st.spinner("Scoring actual results against the confirmed benchmark..."):
                    quant = evaluate_quantitative(confirmed, inputs["actual_metrics"])
                    qual = None
                    if inputs["creative_text"].strip():
                        qual = evaluate_qualitative(
                            inputs["creative_text"], inputs["industry"], inputs["business_model"], inputs["channel"]
                        )
                st.session_state.quant_result = quant
                st.session_state.qual_result = qual
                log_run(
                    inputs["industry"],
                    inputs["stage"],
                    inputs["business_model"],
                    inputs["channel"],
                    inputs["campaign_type"],
                    len(confirmed["metrics"]),
                )
                st.session_state.active_step = 2
                st.rerun()

# ---- Step 3: Evaluation report ----
if active_step == 2:
    quant_result = st.session_state.quant_result
    if quant_result:
        st.markdown("### Evaluation report")

        st.markdown("#### Quantitative — actual vs. confirmed benchmark")
        for r in quant_result["results"]:
            with st.container(border=True):
                st.markdown(
                    f'<div class="bf-metric-name">{html_esc(r["metric"])} {verdict_badge(r["verdict"])}</div>'
                    f'<div style="color:#5B5B63;font-size:0.92rem;margin-top:0.3rem;">'
                    f'actual: <b>{html_esc(r["actual"])}</b> · benchmark: {html_esc(r["benchmark"])}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(esc(r["feedback"]))
        st.success(esc(quant_result["overall_feedback"]))

        qual_result = st.session_state.qual_result
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
