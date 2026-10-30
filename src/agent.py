import json
import os
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from search import search_web

load_dotenv()

MODEL_NAME = "gemini-3.5-flash-lite"
MAX_SEARCH_STEPS = 6
MAX_GAP_QUERIES = 5
MAX_BROADEN_QUERIES = 4
MIN_MENTIONS_FOR_COVERAGE = 2
MAX_API_RETRIES = 3
MIN_INDEPENDENT_DOMAINS_FOR_HIGH_CONFIDENCE = 2

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _generate_content(**kwargs):
    """Gemini occasionally returns a transient 503 (model overloaded) or 429 (rate limit)
    -- retry a couple of times with backoff before giving up, since these aren't real failures."""
    client = _get_client()
    for attempt in range(MAX_API_RETRIES):
        try:
            return client.models.generate_content(**kwargs)
        except errors.ServerError:
            if attempt == MAX_API_RETRIES - 1:
                raise
            time.sleep(2 * (attempt + 1))
        except errors.ClientError as e:
            if e.code != 429 or attempt == MAX_API_RETRIES - 1:
                raise
            time.sleep(5 * (attempt + 1))


def extract_metric_names(actual_metrics_text):
    """Pull out the metric names the marketer actually reported, e.g. 'CPM: $18' -> 'CPM',
    so the research pipeline can guarantee coverage of exactly what they asked about."""
    names = []
    for line in actual_metrics_text.splitlines():
        line = line.strip()
        if not line:
            continue
        name = line.split(":", 1)[0].strip() if ":" in line else line
        if name:
            names.append(name)
    return names


SEARCH_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_web",
            description=(
                "Search the live web for marketing performance benchmark reports, "
                "industry KPI studies, or analyst/agency data."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="A focused search query (Korean or English).",
                    )
                },
                required=["query"],
            ),
        )
    ]
)

AGENT_SYSTEM_PROMPT = """\
You are a research agent for digital marketers. Given a campaign context, decide what to \
search for on the web to find real industry benchmark data for the relevant performance \
metrics.

The marketer has reported these actual metrics and needs reliable benchmark data for EVERY \
one of them -- this is the top priority:
{actual_metrics}

In addition, also consider other standard metrics for this channel and campaign type that \
would add useful context (e.g. CTR, conversion rate, CPA, ROAS, engagement rate -- whichever \
are standard here). Call `search_web` with focused queries, one at a time. Issue up to \
{max_steps} searches: make sure every one of the marketer's reported metrics gets at least \
one dedicated, focused search before you spend searches on anything else, then cover \
industry-specific benchmark reports, company-stage/budget context, and channel-specific \
studies for additional metrics. Once you have solid coverage of all the marketer's reported \
metrics, stop calling tools.

Campaign context:
- Industry: {industry}
- Company stage: {stage}
- Business model: {business_model}
- Channel: {channel}
- Campaign type: {campaign_type}
- Audience type: {audience_type}
- Funnel stage: {funnel_stage}
"""

GAP_ANALYSIS_PROMPT = """\
You already gathered the search results below for this campaign context. Review them \
critically, as a research analyst would before finalizing a report.

The marketer specifically needs reliable benchmark data for these reported metrics -- \
checking their coverage is the top priority:
{actual_metrics}

For which of these -- or other relevant metrics -- is the evidence thin: a single source, \
vague numbers, no mention of this industry/company-stage/channel combination, or outdated \
data? Propose up to {max_queries} additional, more specific search queries that would plug \
those exact gaps, prioritizing any of the marketer's reported metrics that aren't well \
covered yet. If a narrow, industry-specific query is unlikely to return much, propose a \
broader query instead (e.g. drop the industry qualifier and search for the metric at the \
channel/campaign-type level only, or search for it as a general advertising benchmark). If \
coverage is already solid, propose fewer queries or none.

Campaign context:
- Industry: {industry}
- Company stage: {stage}
- Business model: {business_model}
- Channel: {channel}
- Campaign type: {campaign_type}
- Audience type: {audience_type}
- Funnel stage: {funnel_stage}

[Search results gathered so far]
{search_results}

Respond with this JSON schema only:
{{
  "gaps": "string (what's thin or missing, 1-3 sentences)",
  "followup_queries": ["string", "..."]
}}
"""

SYNTHESIZE_PROMPT = """\
Using the search results gathered below, synthesize a performance benchmark standard for \
this campaign context.

The marketer has reported these actual metrics and you MUST include a benchmark entry for \
EVERY one of them, using this exact metric name -- never omit one and never respond that \
there isn't enough data for it:
{actual_metrics}

When direct, industry-specific evidence is unavailable for a metric, do not refuse or leave \
it out. Instead fall back, in this order: (1) the best general {channel}/{campaign_type} \
benchmark the sources do support, even if not specific to "{industry}"; (2) if the sources \
give nothing usable at all for that metric, your own well-established general knowledge of \
typical {channel} benchmarks for that metric. Say plainly in the reasoning which of these \
you used (e.g. "No {industry}-specific data was found; this range reflects general {channel} \
benchmarks instead" or "Not covered by the search results; this is a general industry range \
from established marketing-benchmark knowledge, not directly sourced"). Leave "sources" \
empty only when you used general knowledge with no supporting search result.

Rate your confidence per metric as "High" (multiple matching, industry-specific sources, \
from different publishers), "Medium" (some relevant sources but not an exact match, or only \
one source), or "Low" (general/adjacent knowledge, not directly sourced). Note: "High" will \
be automatically downgraded afterward if fewer than two distinct-domain sources are listed \
for that metric, so only claim "High" when you're citing genuinely independent sources, not \
the same site twice.

Beyond the marketer's reported metrics, also include a few other standard metrics for this \
channel and campaign type that give useful additional context, following the same sourcing \
and confidence rules.

Where multiple sources give different numbers for the same metric, reconcile them into one \
range and say so in the reasoning (e.g. "sources range from X to Y; using the overlap"). \
Prefer metrics backed by more than one source, and if a metric relies on only one weak or \
tangential source, say so explicitly in its reasoning rather than presenting it with false \
confidence.
Respond entirely in English, even if the source material is in Korean or another language.

Campaign context:
- Industry: {industry}
- Company stage: {stage}
- Business model: {business_model}
- Channel: {channel}
- Campaign type: {campaign_type}
- Audience type: {audience_type}
- Funnel stage: {funnel_stage}

Marketer's actual metrics (reported, free text):
{actual_metrics_text}

[Search results]
{search_results}

Respond with this JSON schema only:
{{
  "metrics": [
    {{
      "name": "string (e.g. CTR, Conversion rate, CPA, ROAS, Engagement rate, CPM, AOV)",
      "reasonable_range": "string (e.g. '1.5% - 3%')",
      "confidence": "string (High / Medium / Low)",
      "reasoning": "string (why this range, referencing the context/sources, and noting if it's a general/broadened estimate rather than industry-specific)",
      "sources": [{{"title": "string (source/publisher title)", "url": "string (the exact URL from the search results above)"}}]
    }}
  ],
  "context_notes": "string (caveats: data quality, how well the sources match this exact context, what to treat with caution)"
}}
"""

QUANT_EVAL_PROMPT = """\
You are writing the quantitative section of a campaign performance report for a marketer. \
Compare the marketer's actual performance metrics against the CONFIRMED benchmark standard \
below (the marketer has already reviewed and approved this standard, possibly editing it). \
For each actual metric provided, find the matching benchmark metric, classify the result, \
and give concrete, specific feedback that reads like a performance analyst's notes -- not a \
generic restatement of the numbers.

If an actual metric genuinely has no matching entry in the confirmed benchmark (this should \
be rare, since the benchmark was built to cover the marketer's metrics), do not simply \
report "No benchmark available" and stop there -- instead use well-established general \
digital-marketing benchmark knowledge to give a reasoned, best-effort read on whether the \
actual number looks strong, typical, or weak for this channel, and set the verdict to \
"Estimated (general benchmark)" with that caveat stated plainly in the feedback.

Spend/volume context the marketer provided (may say "not provided"): {volume_context}
If it suggests a small sample size -- low spend, low impressions, or low click/conversion \
counts relative to what's typically needed for a stable read on that kind of metric -- flag \
that explicitly in that metric's feedback (e.g. "with this few conversions, this rate may \
not be statistically stable yet") instead of treating a small-sample number as a settled \
fact. If no volume context was given, do not invent a sample-size caveat.

{previous_run_section}

After scoring every metric, write:
- "overall_feedback": a short executive-summary paragraph (3-5 sentences) reading like the \
opening of a campaign performance report -- overall verdict, the strongest and weakest \
areas, the single most important takeaway, and (if previous-run data was given above) a \
one-clause note on the overall trend versus that previous run.
- "recommendations": 3 to 5 concrete, specific next-step actions the marketer could take to \
improve underperforming metrics, each one sentence, each actionable (not generic advice like \
"keep monitoring").

Respond entirely in English.

Confirmed benchmark standard:
{benchmark_json}

Actual performance metrics (as reported by the marketer, free text):
{actual_metrics}

Respond with this JSON schema only:
{{
  "results": [
    {{
      "metric": "string",
      "actual": "string",
      "benchmark": "string (the matching benchmark range, or 'N/A')",
      "verdict": "string (one of: Below benchmark / Within benchmark / Above benchmark / Estimated (general benchmark))",
      "feedback": "string (concrete, specific feedback)"
    }}
  ],
  "overall_feedback": "string",
  "recommendations": ["string", "..."]
}}
"""

QUAL_EVAL_PROMPT = """\
You are an LLM-judge evaluating marketing creative or customer-response text for this \
campaign context. Score tone fit and message clarity. Be specific and cite phrases from the \
text in your reasoning. Respond entirely in English.

Campaign context:
- Industry: {industry}
- Business model: {business_model}
- Channel: {channel}

Text to evaluate:
{creative_text}

Respond with this JSON schema only:
{{
  "tone_fit_score": "integer 1-5",
  "tone_fit_reason": "string",
  "clarity_score": "integer 1-5",
  "clarity_reason": "string",
  "overall_feedback": "string"
}}
"""


def research_benchmarks(
    industry,
    stage,
    business_model,
    channel,
    campaign_type,
    audience_type,
    funnel_stage,
    actual_metrics_text,
    on_step=None,
):
    config = types.GenerateContentConfig(
        tools=[SEARCH_TOOL],
        system_instruction=AGENT_SYSTEM_PROMPT.format(
            max_steps=MAX_SEARCH_STEPS,
            actual_metrics=actual_metrics_text,
            industry=industry,
            stage=stage,
            business_model=business_model,
            channel=channel,
            campaign_type=campaign_type,
            audience_type=audience_type,
            funnel_stage=funnel_stage,
        ),
    )
    contents = [types.Content(role="user", parts=[types.Part(text="Begin researching now.")])]

    all_results = []
    trace = []

    for _ in range(MAX_SEARCH_STEPS):
        response = _generate_content(model=MODEL_NAME, contents=contents, config=config)
        candidate = response.candidates[0]
        contents.append(candidate.content)

        function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
        if not function_calls:
            break

        for fc in function_calls:
            query = (fc.args or {}).get("query")
            if not query:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name="search_web",
                                    response={"error": "missing required 'query' argument"},
                                )
                            )
                        ],
                    )
                )
                continue
            if on_step:
                on_step(f"Searching: {query}")
            results = search_web(query)
            all_results.extend(results)
            trace.append({"query": query, "result_count": len(results)})

            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name="search_web",
                                response={"result_count": len(results)},
                            )
                        )
                    ],
                )
            )

    seen = set()
    deduped = []
    for r in all_results:
        if r["url"] in seen:
            continue
        seen.add(r["url"])
        deduped.append(r)

    return deduped, trace


def _find_gaps(
    industry, stage, business_model, channel, campaign_type, audience_type, funnel_stage, actual_metrics_text, search_results
):
    results_text = "\n\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content'][:400]}" for r in search_results
    )
    response = _generate_content(
        model=MODEL_NAME,
        contents=GAP_ANALYSIS_PROMPT.format(
            max_queries=MAX_GAP_QUERIES,
            actual_metrics=actual_metrics_text,
            industry=industry,
            stage=stage,
            business_model=business_model,
            channel=channel,
            campaign_type=campaign_type,
            audience_type=audience_type,
            funnel_stage=funnel_stage,
            search_results=results_text,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def _coverage_gaps(metric_names, search_results):
    """Which of the marketer's reported metrics are still barely mentioned in what we've
    gathered so far -- these need a broader, deliberately less-specific search."""
    thin = []
    for name in metric_names:
        name_l = name.lower()
        mentions = sum(
            1 for r in search_results if name_l in (r["title"] + " " + r["content"]).lower()
        )
        if mentions < MIN_MENTIONS_FOR_COVERAGE:
            thin.append(name)
    return thin


def deep_research_benchmarks(
    industry,
    stage,
    business_model,
    channel,
    campaign_type,
    audience_type,
    funnel_stage,
    actual_metrics_text,
    on_step=None,
):
    """Three-phase research: an agent-driven broad pass targeting the marketer's own metrics,
    a gap-filling pass that re-reads the results like an analyst, and a final broadening pass
    that deliberately drops specificity for any of the marketer's metrics that are still thin
    -- so a niche context degrades to a general benchmark instead of dead-ending with nothing."""
    metric_names = extract_metric_names(actual_metrics_text)

    deduped, trace = research_benchmarks(
        industry,
        stage,
        business_model,
        channel,
        campaign_type,
        audience_type,
        funnel_stage,
        actual_metrics_text,
        on_step=on_step,
    )

    if on_step:
        on_step("Reviewing coverage for gaps...")
    gap_analysis = _find_gaps(
        industry, stage, business_model, channel, campaign_type, audience_type, funnel_stage, actual_metrics_text, deduped
    )
    followup_queries = gap_analysis.get("followup_queries", [])[:MAX_GAP_QUERIES]

    seen = {r["url"] for r in deduped}
    for query in followup_queries:
        if on_step:
            on_step(f"Deepening: {query}")
        results = search_web(query)
        trace.append({"query": query, "result_count": len(results), "phase": "gap-fill"})
        for r in results:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            deduped.append(r)

    thin_metrics = _coverage_gaps(metric_names, deduped)[:MAX_BROADEN_QUERIES]
    for name in thin_metrics:
        query = f"{name} {channel} {campaign_type} industry benchmark average"
        if on_step:
            on_step(f"Broadening: {query}")
        results = search_web(query)
        trace.append({"query": query, "result_count": len(results), "phase": "broaden"})
        for r in results:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            deduped.append(r)

    return deduped, trace, gap_analysis.get("gaps", "")


def _source_domain(url):
    try:
        netloc = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def _enforce_confidence_rule(metrics):
    """A model can call its own single-source finding "High confidence" -- don't take that
    claim at face value. Downgrade to Medium in code (not just in the prompt) whenever fewer
    than MIN_INDEPENDENT_DOMAINS_FOR_HIGH_CONFIDENCE distinct-domain sources back the metric,
    so the badge the marketer sees always reflects real source diversity."""
    for m in metrics:
        domains = {_source_domain(s.get("url", "")) for s in m.get("sources", []) if s.get("url")}
        domains.discard("")
        if m.get("confidence") == "High" and len(domains) < MIN_INDEPENDENT_DOMAINS_FOR_HIGH_CONFIDENCE:
            m["confidence"] = "Medium"
            m["reasoning"] = (
                m.get("reasoning", "").rstrip()
                + " (Confidence adjusted to Medium: fewer than two independent-domain sources "
                "were confirmed for this range.)"
            )
    return metrics


def synthesize_benchmark(
    industry, stage, business_model, channel, campaign_type, audience_type, funnel_stage, actual_metrics_text, search_results
):
    results_text = "\n\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content'][:1100]}" for r in search_results
    )
    response = _generate_content(
        model=MODEL_NAME,
        contents=SYNTHESIZE_PROMPT.format(
            actual_metrics=", ".join(extract_metric_names(actual_metrics_text)) or "(none reported)",
            industry=industry,
            stage=stage,
            business_model=business_model,
            channel=channel,
            campaign_type=campaign_type,
            audience_type=audience_type,
            funnel_stage=funnel_stage,
            actual_metrics_text=actual_metrics_text,
            search_results=results_text,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    benchmark = json.loads(response.text)
    benchmark["metrics"] = _enforce_confidence_rule(benchmark.get("metrics", []))
    return benchmark


def evaluate_quantitative(benchmark, actual_metrics_text, volume_context=None, previous_run=None):
    if previous_run:
        prev_metrics_text = "\n".join(f"{m['metric']}: {m['actual']}" for m in previous_run["metrics"])
        previous_run_section = (
            f"Previous run for this exact context (same industry, channel, campaign type), "
            f"logged on {previous_run['timestamp'][:10]}:\n{prev_metrics_text}\n"
            "When relevant, note the direction and rough magnitude of change from this previous "
            "run in that metric's feedback and in the overall executive summary (e.g. \"CPM "
            "improved versus your last run\"). Don't speculate about the cause of the change "
            "beyond what the numbers show."
        )
    else:
        previous_run_section = (
            "No previous run exists for this exact industry/channel/campaign-type combination "
            "on file, so there is nothing to compare against -- do not reference a previous run."
        )

    response = _generate_content(
        model=MODEL_NAME,
        contents=QUANT_EVAL_PROMPT.format(
            benchmark_json=json.dumps(benchmark, ensure_ascii=False, indent=2),
            actual_metrics=actual_metrics_text,
            volume_context=volume_context.strip() if volume_context and volume_context.strip() else "not provided",
            previous_run_section=previous_run_section,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def evaluate_qualitative(creative_text, industry, business_model, channel):
    response = _generate_content(
        model=MODEL_NAME,
        contents=QUAL_EVAL_PROMPT.format(
            industry=industry,
            business_model=business_model,
            channel=channel,
            creative_text=creative_text,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)
