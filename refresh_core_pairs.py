import os
import re
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
MAX_MODEL_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("GEMINI_RETRY_BACKOFF_SECONDS", "10"))
MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))
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
                    "live_spot": {"type": "string"},
                    "day_change_pct": {"type": "string"},
                    "trigger": {"type": "string"},
                    "target": {"type": "string"},
                    "invalidation": {"type": "string"},
                    "catalyst": {"type": "string"},
                    "confidence_pct": {"type": "integer"},
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
                    "rank": {"type": "integer"},
                    "pair": {"type": "string"},
                    "setup": {"type": "string"},
                    "live_spot": {"type": "string"},
                    "entry_zone": {"type": "string"},
                    "stop": {"type": "string"},
                    "target": {"type": "string"},
                    "rr": {"type": "string"},
                    "confidence_pct": {"type": "integer"},
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
                    "spot": {"type": "string"},
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

Macro themes instruction (run this each morning):
"You are an expert FX macro analyst. Based on today's market conditions,
identify the top 5 macro themes currently driving G10 FX markets.

For each theme provide:
- A concise title
- A detailed narrative explanation covering the key data points,
  central bank positions, and market reactions
- An importance label (CRITICAL / HIGH / MEDIUM) and category descriptor

Classification framework:

SEVERITY LEVELS:
- CRITICAL = moving markets intraday right now, binary risk present, affecting multiple pairs simultaneously
- HIGH = structural or near-term catalyst, directional but more predictable
- MEDIUM = background context, relevant but not actively driving price today

CATEGORY DESCRIPTORS:
- PRIMARY DRIVER = single biggest force moving markets today (max one theme per day)
- DEFINING THEME = regime-defining condition likely to persist for days/weeks
- STRUCTURAL = persistent background force framing all trades
- ACTIONABLE DIVERGENCE = directly tradeable divergence via a specific pair right now
- [EVENT NAME + DATE] = tied to a specific upcoming catalyst with explicit date (example: BOJ HIKE RISK APR 28)

Classification decision logic:
- First ask: "Is this theme causing live intraday moves now, or is it structural backdrop?"
- If yes (live intraday): classify as CRITICAL
- If no and still directional/catalyst-driven: classify as HIGH
- If mostly context/background: classify as MEDIUM

Strict macro output constraints:
- Return exactly 5 macro themes ranked by current impact
- Each macro theme "severity" field MUST be one of: CRITICAL, HIGH, MEDIUM
- Each macro theme "tag" field MUST be in this exact format: SEVERITY - CATEGORY
- Example tags: "CRITICAL - PRIMARY DRIVER", "HIGH - BOJ HIKE RISK APR 28"
- Ensure at most one theme has CATEGORY PRIMARY DRIVER

Include specific data:
- Current rates, yields, and price levels with exact figures
- Central bank meeting dates and probability estimates
- Geopolitical developments and their FX impact
- Which currency pairs are most affected and how

Format as 5 ranked macro theme cards suitable for a professional
FX trading dashboard. Today's date is {today}".

Commodity strip instruction (run this each morning):
"For the FX dashboard commodity strip, provide a snapshot of
the following 4 instruments as of today [{today}]:

1. Gold (XAU/USD)
    - Current price
    - One-line directional note (e.g. Risk-off spike)
    - Context note (e.g. recent close date or key level)

2. WTI Crude Oil
    - Current price or level
    - One-line driver note (e.g. Hormuz blockade)
    - Context note (e.g. gap open size)

3. DXY (US Dollar Index)
    - Current level
    - Day-over-day change %
    - One-line context (e.g. Risk-off open)

4. Gold/Oil Ratio
    - Current ratio (Gold price divided by WTI price)
    - One-line assessment (e.g. Extreme, Elevated)
    - Historical context (e.g. Hist. median ~15x)

Keep each field very short: price, one directional word/phrase,
one context note. This is a dashboard tile, not a paragraph."

Strict commodity output constraints:
- commodities array MUST contain exactly 4 entries in this order:
  1) Gold (XAU/USD)
  2) WTI Crude Oil
  3) DXY (US Dollar Index)
  4) Gold/Oil Ratio
- Gold/Oil Ratio value MUST be formatted as nX (example: 27.84x)
- For each commodity item fields MUST map as:
  - name: instrument display name
  - ticker: short code (XAU/USD, WTI, DXY, XAU/WTI)
  - value: current price/level/ratio string
  - change: short directional/driver note
  - context: short context note
  - context_class: one of positive, negative, neutral

Additional requirements:
- Populate all required sections beyond macro themes using current market context.
- Keep values internally consistent with the live FX snapshot below.

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
    today_str = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/London")).strftime("%d %b %Y")
    return PROMPT_TEMPLATE.format(
        today=today_str,
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


def parse_response_json(text):
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()

    # Normalize common model output artifacts before parsing.
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")

    def _extract_first_object(s):
        start = s.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        return None

    def _cleanup_json(s):
        # Remove trailing commas before object/array close.
        out = []
        i = 0
        in_string = False
        escape = False
        while i < len(s):
            ch = s[i]
            if in_string:
                out.append(ch)
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                i += 1
                continue
            if ch == '"':
                in_string = True
                out.append(ch)
                i += 1
                continue
            if ch == ",":
                j = i + 1
                while j < len(s) and s[j] in " \t\r\n":
                    j += 1
                if j < len(s) and s[j] in "]}":
                    i += 1
                    continue
            out.append(ch)
            i += 1
        return "".join(out)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        extracted = _extract_first_object(cleaned)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                return json.loads(_cleanup_json(extracted))
        raise


def enrich_payload(payload, rates_raw):
    commodities = payload.get("commodities") or []
    for item in commodities:
        name = str(item.get("name", "")).lower()
        ticker = str(item.get("ticker", "")).upper()
        is_gold_oil = "gold/oil" in name or ticker in {"XAU/WTI", "GOLD/OIL"}
        if not is_gold_oil:
            continue

        raw_val = str(item.get("value", "")).strip()
        if not raw_val:
            continue

        # Normalize ratio formatting to nX, e.g. 27.84x.
        match = re.search(r"-?\d+(?:\.\d+)?", raw_val.replace(",", ""))
        if not match:
            continue
        value = float(match.group(0))
        decimals = 2 if "." in match.group(0) else 0
        item["value"] = f"{value:.{decimals}f}x"

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
        raise SystemExit("Missing GEMINI_API_KEY or PPLX_API_KEY environment variable")
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

