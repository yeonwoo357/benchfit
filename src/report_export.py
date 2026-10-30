import csv
import io

from fpdf import FPDF

_UNICODE_REPLACEMENTS = {
    "—": "-",
    "–": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "→": "->",
    "↑": "^",
    "↓": "v",
    "·": "-",
}


def _safe(text):
    """fpdf2's core fonts only support latin-1 -- normalize the common unicode punctuation
    an LLM tends to produce (em dashes, smart quotes, arrows) before falling back to a
    lossy encode for anything else, so the PDF never crashes on generated text."""
    text = str(text)
    for src, dst in _UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def _trend_text(trend):
    if not trend:
        return ""
    sign = "+" if trend["pct_change"] >= 0 else ""
    return f"{sign}{trend['pct_change']:.1f}% vs last run ({trend['previous']})"


def build_pdf_report(inputs, quant_result, qual_result, trend_map, generated_at):
    """Renders the evaluation report as a clean, single-file PDF a marketer can hand to a
    stakeholder -- same content as the on-screen report, trend_map optional."""
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 10, "BENCH-FIT Evaluation Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 99)
    context_line = " | ".join(
        _safe(v)
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
    pdf.multi_cell(0, 5, context_line, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Generated {_safe(generated_at)}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_text_color(11, 11, 12)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, _safe(quant_result.get("overall_feedback", "")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Performance Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 9)
    col_widths = [38, 28, 38, 36, 34]
    headers = ["Metric", "Actual", "Benchmark", "Verdict", "vs. Last Run"]
    pdf.set_fill_color(240, 240, 242)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, _safe(h), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for r in quant_result["results"]:
        trend = trend_map.get(r["metric"].lower()) if trend_map else None
        row = [r["metric"], r["actual"], r["benchmark"], r["verdict"], _trend_text(trend) or "-"]
        for w, val in zip(col_widths, row):
            pdf.cell(w, 7, _safe(val)[:40], border=1)
        pdf.ln()
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Detailed Analysis", new_x="LMARGIN", new_y="NEXT")
    for r in quant_result["results"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, _safe(f"{r['metric']} -- {r['verdict']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(0, 5, _safe(r["feedback"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    recommendations = quant_result.get("recommendations", [])
    if recommendations:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, "Recommended Next Steps", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9.5)
        for rec in recommendations:
            pdf.multi_cell(0, 5.5, _safe(f"- {rec}"), new_x="LMARGIN", new_y="NEXT")

    if qual_result:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, "Qualitative Assessment", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(
            0,
            5.5,
            _safe(
                f"Tone fit: {qual_result['tone_fit_score']}/5 -- {qual_result['tone_fit_reason']}\n"
                f"Message clarity: {qual_result['clarity_score']}/5 -- {qual_result['clarity_reason']}\n"
                f"{qual_result['overall_feedback']}"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )

    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 128)
    pdf.multi_cell(
        0,
        4.5,
        "Every number above traces back to: the agent's research -> the benchmark reviewed "
        "and approved by the marketer -> this comparison. Portfolio project, not a production service.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    return bytes(pdf.output())


def build_csv_report(quant_result, trend_map):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Metric", "Actual", "Benchmark", "Verdict", "Previous Run", "% Change vs. Last Run", "Feedback"])
    for r in quant_result["results"]:
        trend = trend_map.get(r["metric"].lower()) if trend_map else None
        previous = trend["previous"] if trend else ""
        pct_change = f"{trend['pct_change']:.1f}%" if trend else ""
        writer.writerow([r["metric"], r["actual"], r["benchmark"], r["verdict"], previous, pct_change, r["feedback"]])
    return buf.getvalue()
