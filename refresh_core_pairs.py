import os
import json
import time
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("PPLX_API_KEY")
MODEL = os.getenv("GEMINI_MODEL") or os.getenv("PPLX_MODEL", "gemini-2.5-flash")
MAX_MODEL_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
RETRY_BACKOFF_SECONDS = float(os.getenv("GEMINI_RETRY_BACKOFF_SECONDS", "10"))
MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096"))
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.5-flash-lite"
    ).split(",")
    if m.strip()
]

OUTPUT_JSON = os.getenv("OUTPUT_JSON", "core_pairs_latest.json")
ANALYSIS_TIMEFRAME = os.getenv("ANALYSIS_TIMEFRAME", "1H / 4H focus, daily context")

PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD"
]

RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "analysis_timestamp_bst",
        "live_rates_timestamp_utc",
        "market_regime",
        "usd_bias",
        "top_risks",
        "macro_themes",
        "core_pairs",
        "top5",
        "secondary",
        "avoid",
        "risk_calendar",
        "what_changed",
        "bond_yields",
        "commodities",
        "correlation_notes",
        "checklist",
    ],
    "properties": {
        "analysis_timestamp_bst": {"type": "string"},
        "live_rates_timestamp_utc": {"type": "string"},
        "market_regime": {"type": "string"},
        "usd_bias": {"type": "string"},
        "top_risks": {"type": "array", "items": {"type": "string"}},
        "macro_themes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["title", "severity", "summary", "tag"],
                "properties": {
                    "title": {"type": "string"},
                    "severity": {"type": "string"},
                    "summary": {"type": "string"},
                    "tag": {"type": "string"},
                },
            },
        },
        "core_pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "pair",
                    "status",
                    "bias",
                    "live_spot",
                    "day_change_pct",
                    "trigger",
                    "target",
                    "invalidation",
                    "catalyst",
                    "confidence_pct",
                    "summary",
                ],
                "properties": {
                    "pair": {"type": "string"},
                    "status": {"type": "string"},
                    "bias": {"type": "string"},
                    "live_spot": {"type": "STRING"},
                    "day_change_pct": {"type": "STRING"},
                    "trigger": {"type": "string"},
                    "target": {"type": "string"},
                    "invalidation": {"type": "string"},
                    "catalyst": {"type": "string"},
                    "confidence_pct": {"type": "INTEGER"},
                    "summary": {"type": "string"},
                },
            },
        },
        "top5": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "rank",
                    "pair",
                    "setup",
                    "live_spot",
                    "entry_zone",
                    "stop",
                    "target",
                    "rr",
                    "confidence_pct",
                    "catalyst",
                    "invalidation_risk",
                ],
                "properties": {
                    "rank": {"type": "INTEGER"},
                    "pair": {"type": "string"},
                    "setup": {"type": "string"},
                    "live_spot": {"type": "STRING"},
                    "entry_zone": {"type": "string"},
                    "stop": {"type": "string"},
                    "target": {"type": "string"},
                    "rr": {"type": "string"},
                    "confidence_pct": {"type": "INTEGER"},
                    "catalyst": {"type": "string"},
                    "invalidation_risk": {"type": "string"},
                },
            },
        },
        "secondary": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pair", "spot", "bias", "notes"],
                "properties": {
                    "pair": {"type": "string"},
                    "spot": {"type": "STRING"},
                    "bias": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
        "avoid": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pair", "reason"],
                "properties": {
                    "pair": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "risk_calendar": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["date_bst", "time_bst", "event", "ccy", "impact"],
                "properties": {
                    "date_bst": {"type": "string"},
                    "time_bst": {"type": "string"},
                    "event": {"type": "string"},
                    "ccy": {"type": "string"},
                    "impact": {"type": "string"},
                },
            },
        },
        "what_changed": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["development", "fx_impact"],
                "properties": {
                    "development": {"type": "string"},
                    "fx_impact": {"type": "string"},
                },
            },
        },
        "bond_yields": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["country", "yield", "trend", "cb_rate", "cb_note"],
                "properties": {
                    "country": {"type": "string"},
                    "yield": {"type": "string"},
                    "trend": {"type": "string"},
                    "cb_rate": {"type": "string"},
                    "cb_note": {"type": "string"},
                },
            },
        },
        "commodities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "ticker", "value", "change", "context", "context_class"],
                "properties": {
                    "name": {"type": "string"},
                    "ticker": {"type": "string"},
                    "value": {"type": "string"},
                    "change": {"type": "string"},
                    "context": {"type": "string"},
                    "context_class": {"type": "string"},
                },
            },
        },
        "correlation_notes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pair_a", "pair_b", "correlation", "implication"],
                "properties": {
                    "pair_a": {"type": "string"},
                    "pair_b": {"type": "string"},
                    "correlation": {"type": "string"},
                    "implication": {"type": "string"},
                },
            },
        },
        "checklist": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["item", "status", "notes"],
                "properties": {
                    "item": {"type": "string"},
                    "status": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
    },
}

CLIENT = genai.Client(api_key=API_KEY) if API_KEY else None

PROMPT_TEMPLATE = """
You are the FX Intelligence Dashboard engine.

Return STRICT VALID JSON only. No markdown. No code fences.

The JSON must have EXACTLY these top-level keys, all populated:
- analysis_timestamp_bst
- live_rates_timestamp_utc
- market_regime
- usd_bias
- top_risks (array of strings)
- macro_themes (array of objects: title, severity, summary, tag)
- core_pairs (array: pair, status, bias, live_spot, day_change_pct, trigger, target, invalidation, catalyst, confidence_pct, summary)
- top5 (array: rank, pair, setup, live_spot, entry_zone, stop, target, rr, confidence_pct, catalyst, invalidation_risk)
- secondary (array: pair, spot, bias, notes)
- avoid (array: pair, reason)
- risk_calendar (array: date_bst, time_bst, event, ccy, impact)
- what_changed (array: development, fx_impact)
- bond_yields (array: country, yield, trend, cb_rate, cb_note)
- commodities (array: name, ticker, value, change, context, context_class)
- correlation_notes (array: pair_a, pair_b, correlation, implication)
- checklist (array: item, status, notes)

Pairs: {pairs}
Timeframe: {timeframe}

Live FX snapshot:
{fx_snapshot}
""".strip()


def fetch_latest_rates():
    url = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR,GBP,JPY,CHF,AUD,CAD,NZD"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def derive_core_spots(data):
    rates = data["rates"]
    eurusd = rates["EUR"]
    gbpusd = rates["GBP"]
    usdjpy = 1 / rates["JPY"] if rates["JPY"] != 0 else None
    usdchf = 1 / rates["CHF"] if rates["CHF"] != 0 else None
    audusd = rates["AUD"]
    usdcad = 1 / rates["CAD"] if rates["CAD"] != 0 else None
    nzdusd = rates["NZD"]
    return {
        "EUR/USD": round(eurusd, 4),
        "GBP/USD": round(gbpusd, 4),
        "USD/JPY": round(usdjpy, 4) if usdjpy else None,
        "USD/CHF": round(usdchf, 4) if usdchf else None,
        "AUD/USD": round(audusd, 4),
        "USD/CAD": round(usdcad, 4) if usdcad else None,
        "NZD/USD": round(nzdusd, 4),
    }


def build_prompt(fx_snapshot):
    return PROMPT_TEMPLATE.format(
        pairs=", ".join(PAIRS),
        timeframe=ANALYSIS_TIMEFRAME,
        fx_snapshot=json.dumps(fx_snapshot, indent=2)
    )


def call_model(prompt):
    models_to_try = [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]
    last_exc = None

    for model_name in models_to_try:
        for attempt in range(1, MAX_MODEL_RETRIES + 1):
            try:
                response = CLIENT.models.generate_content(
                    model=model_name,
                    contents=(
                        "You are a macro FX analyst returning strict JSON for an automated dashboard.\n\n"
                        + prompt
                    ),
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=MAX_OUTPUT_TOKENS,
                        response_mime_type="application/json",
                        response_schema=RESPONSE_SCHEMA,
                    ),
                )
                if isinstance(getattr(response, "parsed", None), dict):
                    return response.parsed
                try:
                    return parse_response_json(response.text)
                except json.JSONDecodeError as exc:
                    last_exc = exc
                    if attempt < MAX_MODEL_RETRIES:
                        delay = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        print(
                            f"Model {model_name} returned malformed JSON (attempt {attempt}/{MAX_MODEL_RETRIES}). "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        continue
                    break
            except genai_errors.ClientError as exc:
                message = str(exc)
                if "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
                    last_exc = exc
                    print(f"Quota exhausted for {model_name}. Trying fallback model...")
                    break
                raise RuntimeError(f"Model request failed: {exc}") from exc
            except genai_errors.ServerError as exc:
                last_exc = exc
                message = str(exc)
                is_unavailable = "UNAVAILABLE" in message or "high demand" in message.lower()
                if is_unavailable and attempt < MAX_MODEL_RETRIES:
                    delay = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    print(
                        f"Model {model_name} unavailable (attempt {attempt}/{MAX_MODEL_RETRIES}). "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    continue
                break
            except Exception as exc:
                body = getattr(exc, "body", None)
                if body:
                    raise RuntimeError(f"Model request failed: {exc}\nResponse body: {body}") from exc
                raise RuntimeError(f"Model request failed: {exc}") from exc

    raise RuntimeError(
        f"Model request failed after retries across models {models_to_try}: {last_exc}"
    ) from last_exc


def extract_json_text(response_text):
    return response_text.strip()


def parse_response_json(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def enrich_payload(payload, rates_raw):
    utc_now = datetime.now(timezone.utc)
    try:
        bst_now = utc_now.astimezone(ZoneInfo("Europe/London"))
    except ZoneInfoNotFoundError:
        # Fallback when tz database is missing on the host environment.
        bst_now = utc_now
    payload["generated_utc"] = utc_now.isoformat()
    payload["generated_bst"] = bst_now.strftime("%Y-%m-%d %H:%M:%S %Z")
    payload["live_rates"] = derive_core_spots(rates_raw)
    payload["live_rates_raw"] = rates_raw
    return payload


def main():
    if not API_KEY:
        raise SystemExit("Missing GEMINI_API_KEY environment variable")
    if CLIENT is None:
        raise SystemExit("Unable to initialize OpenAI-compatible Gemini client")

    rates_raw = fetch_latest_rates()
    prompt = build_prompt(rates_raw)
    payload = call_model(prompt)
    payload = enrich_payload(payload, rates_raw)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
