# BenchFit

An AI agent that solves a specific pain point in campaign reporting: you have real
performance numbers, but no reasonable, context-specific standard to judge them against.
"Is 1.2% engagement good?" depends entirely on your industry, company stage, business
model, and channel — and that context is exactly what's hard to research every time.

Give it your campaign context (industry, company stage, B2C/B2B/D2C, channel, campaign
type) and your actual metrics. A **two-pass deep research agent** (Gemini) researches live
industry benchmark reports via Tavily, critiques its own coverage, runs a second targeted
pass to fill whatever's thin, then proposes a reasonable benchmark standard with reasoning
and sources — and then **stops and asks you to review and approve it** before anything is
scored. Only after you commit to the benchmark does it compare your actual numbers against
it (quantitative) and score any creative/customer-response text you paste in for tone fit
and clarity (qualitative, LLM-as-judge).

## Why this isn't "just ask ChatGPT"
- **Grounded in live search**, not the model's training data — every benchmark metric
  cites a real, clickable source, not a possibly outdated or invented number.
- **A real tool-calling agent loop**: the model decides how many searches to run and what
  to search for, based on the specific campaign context, not a hardcoded query list.
- **Two-pass deep research, not a single search sweep**: after the initial pass, the agent
  reviews its own results like an analyst — flags which metrics are backed by only one weak
  source or don't match the context — and runs a second, targeted pass to plug exactly
  those gaps before synthesizing anything. Typical runs end up cross-referencing 20-30+
  unique sources per report.
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

## Pipeline
```
Input: industry · company stage · B2C/B2B/D2C · channel · campaign type · actual metrics
  -> Pass 1: Gemini decides benchmark-research queries via function calling (src/agent.py)
  -> Tavily advanced-depth web search executes each query (src/search.py)
  -> Gap analysis: Gemini reviews its own results and flags thin/missing coverage
  -> Pass 2: targeted follow-up searches to fill exactly those gaps
  -> Gemini synthesizes a benchmark standard (A): per-metric range + reasoning + sources,
     reconciling disagreement between sources instead of picking one silently
  -> COMMIT GATE: marketer reviews, edits, and approves (A) before anything is scored
  -> Quantitative evaluation: actual metrics vs. approved (A) -> verdict + feedback per metric
  -> Qualitative evaluation: LLM-judge scores pasted creative/customer text on tone fit & clarity
  -> Combined evaluation report: (A) + reasoning + results + feedback, fully traceable
  -> Run logged to evaluation_log.json (src/history.py)
```

## Project structure
```
benchfit/
├── src/
│   ├── search.py       # Tavily web search (single query -> results)
│   ├── agent.py         # Research agent loop, benchmark synthesis, quant + qual evaluation
│   └── history.py       # Local evaluation-run history log
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
- [x] Two-pass deep research: self-critique of coverage gaps + targeted follow-up pass
- [x] Advanced-depth Tavily search for richer source content
- [x] Benchmark synthesis with per-metric reasoning + sources, reconciling conflicting numbers (JSON schema output)
- [x] Human-in-the-loop commit gate: marketer reviews/edits the benchmark before it's used
- [x] Quantitative evaluation against the approved benchmark
- [x] Qualitative LLM-judge evaluation of creative/customer-response text (tone fit, clarity)
- [x] Combined, fully-transparent evaluation report
- [x] Local evaluation history log
- [x] Tested end-to-end in the browser
- [ ] RAG-based auto-eval + Q&A tab (stretch goal, not yet built)
- [ ] Public deployment (Streamlit Community Cloud)

## Known limitations
- Bound by Tavily's free tier (1,000 searches/month) — advanced-depth search and the
  two-pass gap-fill use more credits per run (roughly 6-9 searches, ~2 credits each)
- Benchmark quality depends on what's publicly indexed for a given industry/channel
  combination — niche or emerging categories will have thinner source coverage, which the
  agent flags in its context notes and gap analysis rather than papering over
- If deployed publicly, all visitors would share this project's free-tier API quota
