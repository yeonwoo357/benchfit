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


def esc(text):
    """Escape $ so Streamlit's markdown renderer doesn't treat dollar amounts as LaTeX math."""
    return str(text).replace("$", "\\$")


st.set_page_config(page_title="BenchFit", page_icon="📏", layout="wide")
st.title("📏 BenchFit — Marketing Results Measurement Agent")
st.caption(
    "The hard part of judging campaign results isn't the math — it's knowing what a "
    "reasonable benchmark even IS for your industry, company stage, and channel. This "
    "agent researches that benchmark, lets you review and adjust it, and only then scores "
    "your actual results against it. AI proposes the standard; you approve it. "
    "(Portfolio project — not a production service)"
)

for key in ["search_results", "trace", "gaps", "benchmark", "benchmark_confirmed", "quant_result", "qual_result", "inputs"]:
    if key not in st.session_state:
        st.session_state[key] = None
if st.session_state.benchmark_confirmed is None:
    st.session_state.benchmark_confirmed = False

with st.sidebar:
    st.subheader("Evaluation History")
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

st.subheader("1. Campaign context")
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
    submitted = st.form_submit_button("🔎 Deep-research industry benchmarks")

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

benchmark = st.session_state.benchmark
if benchmark and not st.session_state.benchmark_confirmed:
    st.divider()
    st.subheader("2. Review the proposed benchmark — this is a draft, not a verdict")
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

    st.caption("Adjust any range or reasoning before committing to it — you know your context better than the agent does.")
    for i, m in enumerate(benchmark["metrics"]):
        st.markdown(f"**{esc(m['name'])}**")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.text_input("Reasonable range", value=m["reasonable_range"], key=f"range_{i}")
        with c2:
            st.text_area("Reasoning", value=m["reasoning"], key=f"reasoning_{i}", height=70)
        if m.get("sources"):
            st.caption("Sources: " + esc(" · ".join(m["sources"])))
        st.divider()

    if st.button("✅ Confirm this benchmark & continue"):
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
    st.divider()
    st.subheader("2. Confirmed benchmark (A)")
    confirmed = st.session_state.benchmark
    for m in confirmed["metrics"]:
        st.markdown(f"**{esc(m['name'])}**: {esc(m['reasonable_range'])}")
        st.caption(esc(m["reasoning"]))

    if st.session_state.quant_result is None:
        if st.button("📊 Run evaluation against this benchmark"):
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
            st.rerun()

quant_result = st.session_state.quant_result
if quant_result:
    st.divider()
    st.subheader("3. Evaluation report")

    st.markdown("#### Quantitative — actual vs. confirmed benchmark")
    for r in quant_result["results"]:
        verdict_icon = {
            "Below benchmark": "🔴",
            "Within benchmark": "🟡",
            "Above benchmark": "🟢",
            "No benchmark available": "⚪",
        }.get(r["verdict"], "⚪")
        st.markdown(
            f"{verdict_icon} **{esc(r['metric'])}** — actual: {esc(r['actual'])} · "
            f"benchmark: {esc(r['benchmark'])} · {r['verdict']}"
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
        "and approved → this comparison. Nothing here was decided without your sign-off on (A)."
    )
