import os
import json
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PPLX_API_KEY = os.getenv("GEMINI_API_KEY")
PPLX_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL = os.getenv("PPLX_MODEL", "gemini-2.0-flash")

OUTPUT_JSON = os.getenv("OUTPUT_JSON", "core_pairs_latest.json")
ANALYSIS_TIMEFRAME = os.getenv("ANALYSIS_TIMEFRAME", "1H / 4H focus, daily context")

PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD"
]

PROMPT_TEMPLATE = """
You are the FX Intelligence Dashboard engine.

Return STRICT VALID JSON only. No markdown. No code fences. No commentary outside JSON.

Build an FX dashboard refresh payload for these core pairs:
{pairs}

Requirements:
- Timeframe focus: {timeframe}
- Use current FX snapshot as the live anchor
- Produce a JSON object with these top-level keys:
  analysis_timestamp_bst
  live_rates_timestamp_utc
  market_regime
  usd_bias
  top_risks
  macro_themes
  core_pairs
  top5
  secondary
  avoid
  risk_calendar
  what_changed

Schema notes:
- top_risks: array of strings
- macro_themes: array of objects with keys: title, severity, summary
- core_pairs: array of objects with keys:
  pair, status, bias, live_spot, day_change_pct, trigger, target,
  invalidation, catalyst, confidence_pct, summary
- top5: array of objects with keys:
  rank, pair, setup, live_spot, entry_zone, stop, target, rr,
  confidence_pct, catalyst, invalidation_risk
- secondary: array of objects with keys: pair, spot, bias, notes
- avoid: array of objects with keys: pair, reason
- risk_calendar: array of objects with keys: date_bst, time_bst, event, ccy, impact
- what_changed: array of objects with keys: development, fx_impact

Guidance:
- Keep each summary concise and dashboard-ready
- Use explicit price levels where possible
- Confidence should be an integer percentage
- Respect the live snapshot below
- If a field is uncertain, still return a usable best-effort value

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


def call_perplexity(prompt):
    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a macro FX analyst returning strict JSON for an automated dashboard."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }
    r = requests.post(PPLX_URL, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def extract_json_text(response_json):
    return response_json["choices"][0]["message"]["content"].strip()


def parse_response_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def enrich_payload(payload, rates_raw):
    utc_now = datetime.now(timezone.utc)
    bst_now = utc_now.astimezone(ZoneInfo("Europe/London"))
    payload["generated_utc"] = utc_now.isoformat()
    payload["generated_bst"] = bst_now.strftime("%Y-%m-%d %H:%M:%S %Z")
    payload["live_rates"] = derive_core_spots(rates_raw)
    payload["live_rates_raw"] = rates_raw
    return payload


def main():
    if not PPLX_API_KEY:
        raise SystemExit("Missing PPLX_API_KEY environment variable")

    rates_raw = fetch_latest_rates()
    prompt = build_prompt(rates_raw)
    result = call_perplexity(prompt)
    content = extract_json_text(result)
    payload = parse_response_json(content)
    payload = enrich_payload(payload, rates_raw)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
