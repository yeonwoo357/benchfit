# BenchFit

An AI agent that solves a specific pain point in campaign reporting: you have real
performance numbers, but no reasonable, context-specific standard to judge them against.
"Is 1.2% engagement good?" depends entirely on your industry, company stage, business
model, and channel — and that context is exactly what's hard to research every time.

I built this out of a real situation as a junior marketer: asked to turn around a
performance read-out with almost no notice, I had the numbers but no quick, defensible
way to say whether they were actually good — and not enough time to go research industry
benchmarks from scratch. BenchFit is the tool I wished existed in that moment.

Give it your campaign context (industry, company stage, B2C/B2B/D2C, channel, campaign
type, audience type, funnel stage) and your actual metrics. A **three-pass deep research
agent** (Gemini) researches live industry benchmark reports via Tavily -- specifically
targeting benchmark data for every metric you actually reported, not just generic channel
defaults -- critiques its own coverage, runs a targeted gap-fill pass, then a final
broadening pass that deliberately drops specificity for anything still thin so a niche
context degrades to a general estimate instead of dead-ending with "no data." It then
proposes a reasonable benchmark standard with a per-metric confidence rating
(High/Medium/Low), reasoning, and sources — and **stops and asks you to review and approve
it** before anything is scored. Only after you commit to the benchmark does it compare your
actual numbers against it and generate a report: an executive summary, a performance
snapshot, a metric breakdown table (with a trend column vs. your last run in the same
context), detailed per-metric analysis, and concrete recommendations — plus scores any
creative/customer-response text you paste in for tone fit and clarity (qualitative,
LLM-as-judge). An optional spend/volume field adds a statistical-significance caveat to
low-sample-size metrics, and the finished report exports as a one-click PDF or CSV.

## Why this isn't "just ask ChatGPT"
- **Grounded in live search**, not the model's training data — every benchmark metric
  cites a real, clickable source, not a possibly outdated or invented number.
- **A real tool-calling agent loop**: the model decides how many searches to run and what
  to search for, based on the specific campaign context, not a hardcoded query list.
- **Three-pass deep research, not a single search sweep, and it never just gives up**: the
  agent first guarantees a dedicated search for every metric you actually reported (not just
  metrics it guesses are standard for the channel), then reviews its own results like an
  analyst and runs a targeted gap-fill pass, then a final broadening pass that deliberately
  drops industry/stage specificity for anything still thin. Typical runs cross-reference
  40-50+ unique sources per report. When direct evidence genuinely isn't findable, the
  synthesis step falls back to a general-benchmark estimate with a stated confidence level
  (High/Medium/Low) instead of refusing with "no benchmark available."
- **Cross-source reconciliation**: when sources disagree on a number, the synthesis step
  is instructed to reconcile them into one range and say so, instead of picking one source
  silently.
- **An explicit commit gate, not a black box**: the agent's proposed benchmark is a draft.
  You can edit every range and every reasoning note before it's used to score anything.
  Nothing downstream happens without your sign-off.
- **Full transparency**: the final report always shows the benchmark, the reasoning behind
  it, and the sources — not just a pass/fail verdict.
- **LLM-as-judge reused deliberately**: the qualitative scoring step reuses the same
  structured-verdict evaluation pattern built and tested in `marketing-rag-qa/eval/`.
- **Tracks your own trend, not just an industry average**: every run is logged with its full
  metric values, and a later run in the same industry/channel/campaign-type context
  automatically shows percent-change vs. your last run — so the report answers "am I
  improving?" not just "am I average?"

## Pipeline
```
Input: industry · company stage · B2C/B2B/D2C · channel · campaign type · actual metrics
  -> Pass 1: Gemini decides benchmark-research queries via function calling, guaranteed to
     cover every metric the marketer actually reported first (src/agent.py)
  -> Tavily advanced-depth web search executes each query (src/search.py)
  -> Gap analysis: Gemini reviews its own results and flags thin/missing coverage
  -> Pass 2: targeted follow-up searches to fill exactly those gaps
  -> Pass 3: broadening search for any reported metric still thin after pass 2 -- drops
     industry/stage specificity so a niche context still gets a usable estimate
  -> Gemini synthesizes a benchmark standard: per-metric range + confidence (High/Med/Low)
     + reasoning + sources, reconciling disagreement between sources instead of picking one
     silently, and falling back to general-knowledge estimates rather than refusing
  -> COMMIT GATE: marketer reviews, edits, and approves the benchmark before anything is scored
  -> Quantitative evaluation: actual metrics vs. approved benchmark -> verdict + feedback per
     metric + an executive summary + concrete recommendations
  -> Qualitative evaluation: LLM-judge scores pasted creative/customer text on tone fit & clarity
  -> Trend: full metrics from this run are matched against the most recent prior run with the
     same industry/channel/campaign type, computing percent-change per metric (src/history.py)
  -> Report: executive summary + performance snapshot + metric table (with trend column) +
     detailed analysis + recommendations, fully traceable, exportable as PDF or CSV
     (src/report_export.py)
  -> Run logged to evaluation_log.json (src/history.py)
```

## Project structure
```
benchfit/
├── src/
│   ├── search.py       # Tavily web search (single query -> results)
│   ├── agent.py         # Research agent loop, benchmark synthesis, quant + qual evaluation
│   ├── history.py       # Local evaluation-run history log + trend computation
│   └── report_export.py # PDF / CSV export of the evaluation report
├── app/
│   └── app.py            # Streamlit UI (input -> commit gate -> report)
├── requirements.txt
└── .env                  # GEMINI_API_KEY, TAVILY_API_KEY (not committed)
```

## Running it
```bash
source .venv/bin/activate
streamlit run app/app.py --server.port 8504
```

## Status
- [x] Gemini function-calling agent loop researching benchmark reports (autonomous multi-step search)
- [x] Three-pass deep research: targeted coverage of the marketer's own metrics + self-critique
      gap-fill pass + a final broadening pass so thin coverage degrades to a general estimate
      instead of a dead end
- [x] Advanced-depth Tavily search for richer source content
- [x] Benchmark synthesis with per-metric confidence (High/Med/Low) + reasoning + sources,
      reconciling conflicting numbers and falling back to general knowledge rather than
      refusing (JSON schema output)
- [x] Human-in-the-loop commit gate: marketer reviews/edits the benchmark before it's used
- [x] Quantitative evaluation against the approved benchmark, with an executive summary and
      concrete recommendations
- [x] Qualitative LLM-judge evaluation of creative/customer-response text (tone fit, clarity)
- [x] Report-style output: executive summary, performance snapshot, metric table, detailed
      analysis, recommendations -- fully transparent and traceable
- [x] Local evaluation history log
- [x] Historical trend comparison: percent-change vs. your last run in the same
      industry/channel/campaign-type context, surfaced in the summary table and the
      executive summary
- [x] Audience type and funnel stage segmentation, threaded through research and evaluation
      for sharper, more specific benchmarks
- [x] Optional spend/volume input: adds an explicit statistical-significance caveat to
      metrics backed by a small sample
- [x] One-click PDF and CSV export of the finished evaluation report
- [x] Tested end-to-end in the browser
- [ ] RAG-based auto-eval + Q&A tab (stretch goal, not yet built)
- [ ] Public deployment (Streamlit Community Cloud)

## Known limitations
- Bound by Tavily's free tier (1,000 searches/month) — advanced-depth search and the
  three-pass gap-fill/broaden strategy use more credits per run (roughly 10-15 searches,
  ~2 credits each)
- Uses `gemini-3.5-flash-lite` rather than a heavier model, chosen for its much higher
  free-tier requests-per-minute quota given how many Gemini calls one research run now makes
- Benchmark quality depends on what's publicly indexed for a given industry/channel
  combination — niche or emerging categories fall back to a lower-confidence, more general
  estimate rather than failing outright, and this is always labeled plainly (confidence
  rating + reasoning) rather than papered over
- If deployed publicly, all visitors would share this project's free-tier API quota
