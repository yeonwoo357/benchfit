# BenchFit — Lovable build prompt

Paste everything below (from "Build a web app called BenchFit" to the end) into Lovable as
your first prompt. It describes the full product, user flow, and the exact backend logic
(prompts + JSON schemas) so the generated app matches the working Python/Streamlit
prototype this was built from.

---

Build a web app called **BenchFit — Marketing Results Measurement Agent**.

## The problem it solves
Marketers have real campaign performance numbers but no reasonable, context-specific
standard to judge them against. "Is 1.2% engagement good?" depends entirely on industry,
company stage, business model, and channel — and researching that context every time is
the actual bottleneck. BenchFit automates the research, but always asks the marketer to
review and approve the benchmark before anything gets scored against it.

## Tech requirements
- Frontend: React + Tailwind, clean data-dashboard aesthetic (not playful/consumer —
  this is a B2B tool for marketers). Light mode, generous whitespace, card-based layout.
- Backend: use **Supabase Edge Functions** for every call to Gemini and Tavily — never
  call these APIs directly from the client, since that would expose the API keys. Store
  `GEMINI_API_KEY` and `TAVILY_API_KEY` as Supabase secrets.
- Use the `gemini-2.5-flash` model (or latest available stable Gemini flash model) via the
  Gemini API for all LLM calls below. Use `response_mime_type: "application/json"` for any
  call that must return structured JSON.
- Use the Tavily Search API (`https://api.tavily.com/search`) with `search_depth: "advanced"`
  for all web searches.
- Persist each completed evaluation run to a Supabase table (`evaluation_runs`): industry,
  stage, business_model, channel, campaign_type, metric_count, created_at. Show the last 10
  runs in a sidebar/history panel.

## User flow (4 screens/states on one page, revealed progressively)

### 1. Campaign context form
Fields:
- Industry / sector (free text, e.g. "vegan skincare", "B2B SaaS")
- Company stage (select: Startup / SMB / Mid-size / Enterprise)
- Business model (select: B2C / B2B / D2C)
- Channel (select: Instagram / Google Ads / Facebook / TikTok / YouTube / Email / Other)
- Campaign type (free text, e.g. "brand awareness", "lead generation")
- Actual performance metrics (textarea, free text like "CTR: 2.3%\nCPA: $14\nROAS: 3.2x")
- Creative / customer-response text (textarea, optional — ad copy or customer comments for
  qualitative scoring)

Submit button: "Deep-research industry benchmarks". While running, show live status text
for each search query the agent is executing (see backend logic below) — this is important,
don't just show a generic spinner.

### 2. Benchmark review — the commit gate (critical UX requirement)
Show the agent's research trace in a collapsible panel (every search query it ran, tagged
by phase: initial pass vs. gap-fill pass, plus a one-line note on self-identified gaps).

For each proposed benchmark metric, render an **editable** card:
- Metric name (read-only)
- Reasonable range (editable text input, pre-filled with the agent's proposal)
- Reasoning (editable textarea, pre-filled with the agent's reasoning, which should
  reference specific sources and reconcile any disagreement between them)
- Sources (list of title + clickable URL, read-only)

This screen must NOT auto-advance. The marketer can edit any field. Only a button labeled
"✅ Confirm this benchmark & continue" moves to the next screen, and it must use whatever
values are currently in the editable fields (including unedited defaults) — never the
model's original raw output if the user changed something. Make this gate visually obvious
(e.g. a distinct bordered section with copy like "This is a draft, not a verdict — adjust
anything before committing to it").

### 3. Evaluation report
After confirming, call the quantitative evaluation (and qualitative, if creative text was
provided) and render:
- The confirmed benchmark (A) again at the top, for reference, with its reasoning
- Quantitative results: one row per metric with a colored verdict badge (🔴 Below
  benchmark / 🟡 Within benchmark / 🟢 Above benchmark / ⚪ No benchmark available), the
  actual value, the benchmark range, and specific feedback text
- An overall feedback summary
- If qualitative text was provided: tone-fit score (1-5) and message-clarity score (1-5),
  each with a reasoning string, plus an overall qualitative feedback summary
- A closing note: "Every number above traces back to: the agent's research → the benchmark
  you reviewed and approved → this comparison. Nothing here was decided without your
  sign-off on (A)."

### 4. History sidebar
Persistent sidebar showing past evaluation runs (industry, channel, stage, business model,
campaign type, metric count, timestamp), most recent first, pulled from the
`evaluation_runs` Supabase table.

## Backend logic — implement exactly these prompts/schemas as Edge Functions

### Edge Function 1: `research-benchmarks` (two-pass deep research)
**Pass 1 — agent-driven search.** Call Gemini with function calling. Give it one tool:

```
Tool name: search_web
Description: Search the live web for marketing performance benchmark reports, industry KPI
studies, or analyst/agency data.
Parameters: { query: string (required) — a focused search query }
```

System instruction:
```
You are a research agent for digital marketers. Given a campaign context, decide what to
search for on the web to find real industry benchmark data for the relevant performance
metrics (e.g. CTR, conversion rate, CPA, ROAS, engagement rate -- whichever fit this
channel and campaign type). Call `search_web` with focused queries, one at a time. Issue
2 to 5 searches covering different angles (e.g. industry-specific benchmark reports,
company-stage/budget context, channel-specific studies). Once you have enough material,
stop calling tools.

Campaign context:
- Industry: {industry}
- Company stage: {stage}
- Business model: {business_model}
- Channel: {channel}
- Campaign type: {campaign_type}
```

Loop: on each Gemini turn, execute every `search_web` function call against Tavily
(`max_results: 6`, `search_depth: "advanced"`), feed the result count back as the function
response, and continue until Gemini stops calling tools or you hit 5 iterations. Dedupe all
results by URL across the whole loop. Record every query + result count as a trace step.

**Gap analysis — self-critique pass.** After pass 1, call Gemini once more with the
deduped results so far:
```
You already gathered the search results below for this campaign context. Review them
critically, as a research analyst would before finalizing a report. For which relevant
metrics is the evidence thin -- a single source, vague numbers, no mention of this
industry/company-stage/channel combination, or outdated data? Propose up to 3 additional,
more specific search queries that would plug those exact gaps (e.g. naming the missing
metric, a narrower sub-vertical, or a different angle like "annual report" / "case study" /
"benchmark 2026"). If coverage is already solid, propose fewer queries or none.

Campaign context: (same fields as above)

[Search results gathered so far]
{search_results}

Respond with this JSON schema only:
{
  "gaps": "string (what's thin or missing, 1-3 sentences)",
  "followup_queries": ["string", "..."]
}
```

**Pass 2 — gap-fill.** Run each `followup_queries` entry directly through Tavily (same
params), tag these trace entries `phase: "gap-fill"`, and merge new unique-by-URL results
into the deduped set. Return: the full deduped result list, the full trace (both phases),
and the `gaps` string.

### Edge Function 2: `synthesize-benchmark`
One Gemini call, `response_mime_type: "application/json"`:
```
Using ONLY the search results gathered below, synthesize a reasonable performance
benchmark standard for this campaign context. For each metric that is actually relevant to
this channel and campaign type, infer a reasonable range grounded in the search results --
do not invent numbers that aren't supported by the sources. Where multiple sources give
different numbers for the same metric, reconcile them into one range and say so in the
reasoning (e.g. "sources range from X to Y; using the overlap"). Prefer metrics backed by
more than one source, and if a metric relies on only one weak or tangential source, say so
explicitly in its reasoning rather than presenting it with false confidence. If the sources
don't give enough signal for a metric at all, say so instead of guessing.
Respond entirely in English, even if the source material is in Korean or another language.

Campaign context: (same fields)

[Search results]
{search_results}

Respond with this JSON schema only:
{
  "metrics": [
    {
      "name": "string (e.g. CTR, Conversion rate, CPA, ROAS, Engagement rate)",
      "reasonable_range": "string (e.g. '1.5% - 3%')",
      "reasoning": "string (why this range, referencing the context/sources)",
      "sources": ["string (title + url)", "..."]
    }
  ],
  "context_notes": "string (caveats: data quality, how well the sources match this exact context, what to treat with caution)"
}
```

### Edge Function 3: `evaluate-quantitative`
One Gemini call, `response_mime_type: "application/json"`, called with the **marketer's
confirmed/edited** benchmark (not the raw model output):
```
Compare the marketer's actual performance metrics against the CONFIRMED benchmark standard
below (the marketer has already reviewed and approved this standard, possibly editing it).
For each actual metric provided, find the matching benchmark metric if one exists, classify
the result, and give concrete feedback. If an actual metric has no matching benchmark,
still report it with verdict "No benchmark available" and brief context. Respond entirely
in English.

Confirmed benchmark standard:
{benchmark_json}

Actual performance metrics (as reported by the marketer, free text):
{actual_metrics}

Respond with this JSON schema only:
{
  "results": [
    {
      "metric": "string",
      "actual": "string",
      "benchmark": "string (the matching benchmark range, or 'N/A')",
      "verdict": "string (one of: Below benchmark / Within benchmark / Above benchmark / No benchmark available)",
      "feedback": "string (concrete, specific feedback)"
    }
  ],
  "overall_feedback": "string (short overall read on performance against the approved standard)"
}
```

### Edge Function 4: `evaluate-qualitative` (only called if creative text was provided)
```
You are an LLM-judge evaluating marketing creative or customer-response text for this
campaign context. Score tone fit and message clarity. Be specific and cite phrases from the
text in your reasoning. Respond entirely in English.

Campaign context:
- Industry: {industry}
- Business model: {business_model}
- Channel: {channel}

Text to evaluate:
{creative_text}

Respond with this JSON schema only:
{
  "tone_fit_score": "integer 1-5",
  "tone_fit_reason": "string",
  "clarity_score": "integer 1-5",
  "clarity_reason": "string",
  "overall_feedback": "string"
}
```

## Important implementation details
- The commit gate is the core differentiator of this product — do not let the UI skip or
  auto-confirm it under any circumstance.
- When rendering any LLM-generated text that may contain "$" dollar amounts, make sure your
  markdown/text renderer does not interpret "$...$" as LaTeX math (this bit the original
  Streamlit prototype — Lovable's React stack won't have this issue by default, but keep it
  in mind if you add any markdown-rendering library).
- Quantitative evaluation must always be run against the benchmark values as currently
  edited in the UI at confirm-time, not the agent's original proposal.
- Handle the case where Gemini's function call arrives with a missing/empty `query`
  argument gracefully (skip it, don't crash the research loop).

## Out of scope for this build (future work, don't build yet)
A separate RAG-based auto-eval + Q&A tab over past reports — not needed for v1.
