import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

from search import search_web

load_dotenv()

MODEL_NAME = "gemini-3.5-flash-lite"
MAX_SEARCH_STEPS = 4

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


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
metrics (e.g. CTR, conversion rate, CPA, ROAS, engagement rate -- whichever fit this \
channel and campaign type). Call `search_web` with focused queries, one at a time. Issue \
2 to {max_steps} searches covering different angles (e.g. industry-specific benchmark \
reports, company-stage/budget context, channel-specific studies). Once you have enough \
material, stop calling tools.

Campaign context:
- Industry: {industry}
- Company stage: {stage}
- Business model: {business_model}
- Channel: {channel}
- Campaign type: {campaign_type}
"""

SYNTHESIZE_PROMPT = """\
Using ONLY the search results gathered below, synthesize a reasonable performance \
benchmark standard for this campaign context. For each metric that is actually relevant \
to this channel and campaign type, infer a reasonable range grounded in the search \
results -- do not invent numbers that aren't supported by the sources. If the sources \
don't give enough signal for a metric, say so instead of guessing.
Respond entirely in English, even if the source material is in Korean or another language.

Campaign context:
- Industry: {industry}
- Company stage: {stage}
- Business model: {business_model}
- Channel: {channel}
- Campaign type: {campaign_type}

[Search results]
{search_results}

Respond with this JSON schema only:
{{
  "metrics": [
    {{
      "name": "string (e.g. CTR, Conversion rate, CPA, ROAS, Engagement rate)",
      "reasonable_range": "string (e.g. '1.5% - 3%')",
      "reasoning": "string (why this range, referencing the context/sources)",
      "sources": ["string (title + url)", "..."]
    }}
  ],
  "context_notes": "string (caveats: data quality, how well the sources match this exact context, what to treat with caution)"
}}
"""

QUANT_EVAL_PROMPT = """\
Compare the marketer's actual performance metrics against the CONFIRMED benchmark \
standard below (the marketer has already reviewed and approved this standard, possibly \
editing it). For each actual metric provided, find the matching benchmark metric if one \
exists, classify the result, and give concrete feedback. If an actual metric has no \
matching benchmark, still report it with verdict "No benchmark available" and brief \
context. Respond entirely in English.

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
      "verdict": "string (one of: Below benchmark / Within benchmark / Above benchmark / No benchmark available)",
      "feedback": "string (concrete, specific feedback)"
    }}
  ],
  "overall_feedback": "string (short overall read on performance against the approved standard)"
}}
"""

QUAL_EVAL_PROMPT = """\
You are an LLM-judge evaluating marketing creative or customer-response text for this \
campaign context. Score tone fit and message clarity. Be specific and cite phrases from \
the text in your reasoning. Respond entirely in English.

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


def research_benchmarks(industry, stage, business_model, channel, campaign_type, on_step=None):
    client = _get_client()
    config = types.GenerateContentConfig(
        tools=[SEARCH_TOOL],
        system_instruction=AGENT_SYSTEM_PROMPT.format(
            max_steps=MAX_SEARCH_STEPS,
            industry=industry,
            stage=stage,
            business_model=business_model,
            channel=channel,
            campaign_type=campaign_type,
        ),
    )
    contents = [types.Content(role="user", parts=[types.Part(text="Begin researching now.")])]

    all_results = []
    trace = []

    for _ in range(MAX_SEARCH_STEPS):
        response = client.models.generate_content(model=MODEL_NAME, contents=contents, config=config)
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


def synthesize_benchmark(industry, stage, business_model, channel, campaign_type, search_results):
    client = _get_client()
    results_text = "\n\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content'][:500]}" for r in search_results
    )
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=SYNTHESIZE_PROMPT.format(
            industry=industry,
            stage=stage,
            business_model=business_model,
            channel=channel,
            campaign_type=campaign_type,
            search_results=results_text,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def evaluate_quantitative(benchmark, actual_metrics_text):
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=QUANT_EVAL_PROMPT.format(
            benchmark_json=json.dumps(benchmark, ensure_ascii=False, indent=2),
            actual_metrics=actual_metrics_text,
        ),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def evaluate_qualitative(creative_text, industry, business_model, channel):
    client = _get_client()
    response = client.models.generate_content(
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
