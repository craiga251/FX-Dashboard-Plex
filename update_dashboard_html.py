import html
import json
import os
import re
from pathlib import Path
from datetime import datetime

JSON_PATH = Path(os.getenv("CORE_JSON", "core_pairs_latest.json"))
TEMPLATE_PATH = Path(os.getenv("DASHBOARD_TEMPLATE", "fx_orginal_template.html"))
OUTPUT_PATH = Path(os.getenv("DASHBOARD_OUTPUT", "dashboard_generated.html"))
DAILY_BRIEF_PATH = Path(os.getenv("DAILY_BRIEF_PATH", "daily_dashboard_brief.txt"))
CORE_PAIRS_TARGET = int(os.getenv("CORE_PAIRS_TARGET", "7"))

PAIR_CODE_TO_LABEL = {
  "EURUSD": "EUR/USD",
  "GBPUSD": "GBP/USD",
  "AUDUSD": "AUD/USD",
  "NZDUSD": "NZD/USD",
  "USDJPY": "USD/JPY",
  "USDCHF": "USD/CHF",
  "USDCAD": "USD/CAD",
  "DXY": "DXY",
}

MANUAL_CONFIDENCE_MAP = {
  1: 35,
  2: 50,
  3: 65,
  4: 80,
  5: 90,
}

MONTH_NAME_MAP = {
  "JAN": 1,
  "JANUARY": 1,
  "FEB": 2,
  "FEBRUARY": 2,
  "MAR": 3,
  "MARCH": 3,
  "APR": 4,
  "APRIL": 4,
  "MAY": 5,
  "JUN": 6,
  "JUNE": 6,
  "JUL": 7,
  "JULY": 7,
  "AUG": 8,
  "AUGUST": 8,
  "SEP": 9,
  "SEPT": 9,
  "SEPTEMBER": 9,
  "OCT": 10,
  "OCTOBER": 10,
  "NOV": 11,
  "NOVEMBER": 11,
  "DEC": 12,
  "DECEMBER": 12,
}

SOURCE_BOND_YIELDS = [
  {"country": "US", "yield": "4.31%", "trend": "Rising", "cb_rate": "3.50-3.75%"},
  {"country": "Germany", "yield": "3.06%", "trend": "Rising", "cb_rate": "2.00%"},
  {"country": "UK", "yield": "4.81%", "trend": "Rising", "cb_rate": "3.75%"},
  {"country": "Japan", "yield": "2.49%", "trend": "29-yr high", "cb_rate": "0.75%"},
  {"country": "Australia", "yield": "4.97%", "trend": "Rising", "cb_rate": "4.10% (hiking)"},
  {"country": "Canada", "yield": "3.50%", "trend": "Rising", "cb_rate": "2.25%"},
  {"country": "New Zealand", "yield": "4.73%", "trend": "Rising", "cb_rate": "2.25% (hike bias)"},
  {"country": "Switzerland", "yield": "0.46%", "trend": "Rising", "cb_rate": "0.00%"},
]

SOURCE_MACRO_THEMES = [
  {
    "title": "Trump Hormuz Naval Blockade",
    "severity": "Critical",
    "summary": "Strait of Hormuz disruption risk keeps markets in risk-off mode and supports USD/JPY safe-haven flows.",
    "tag": "CRITICAL - Primary Driver",
  },
  {
    "title": "CPI Energy Shock - Fed Trapped",
    "severity": "Critical",
    "summary": "Energy-driven inflation keeps policy expectations uncertain and can increase FX volatility around US data.",
    "tag": "CRITICAL - Defining Theme",
  },
  {
    "title": "USD Ambiguity - Exporter vs. Political Risk",
    "severity": "High",
    "summary": "USD remains supported in risk-off phases but political risk and growth concerns cap follow-through strength.",
    "tag": "HIGH - Structural",
  },
  {
    "title": "CB Divergence - Still Actionable",
    "severity": "High",
    "summary": "Monetary policy divergence continues to drive relative value opportunities across major FX pairs.",
    "tag": "HIGH - Actionable Divergence",
  },
  {
    "title": "BOJ Trigger Risk Near Key Levels",
    "severity": "High",
    "summary": "USD/JPY remains highly sensitive to BOJ policy signaling and intervention rhetoric near critical levels.",
    "tag": "HIGH - BOJ Hike Risk",
  },
]


def s(value):
  return html.escape("" if value is None else str(value))


def normalize_pair_code(value):
  return re.sub(r"[^A-Z]", "", str(value or "").upper())


def pair_label_from_code(value):
  code = normalize_pair_code(value)
  return PAIR_CODE_TO_LABEL.get(code, str(value or "").strip())


def confidence_to_pct(value):
  try:
    score = int(str(value).strip())
  except Exception:
    return 45
  return MANUAL_CONFIDENCE_MAP.get(score, max(20, min(score, 100)))


def normalize_text(value):
  text = str(value or "")
  replacements = {
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\ufffd": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2192": "->",
    "\u2194": "<->",
    "\u26a0": "WARNING",
    "\u2610": "[ ]",
  }
  for old, new in replacements.items():
    text = text.replace(old, new)
  return text


def extract_first_number(text):
  match = re.search(r"-?\d+(?:\.\d+)?", normalize_text(text).replace(",", ""))
  return match.group(0) if match else ""


def extract_invalidation_level(text):
  cleaned = normalize_text(text).replace(",", "")

  directional_match = re.search(
    r"(?:above|below|over|under|>|<)\s*(-?\d+(?:\.\d+)?)",
    cleaned,
    flags=re.IGNORECASE,
  )
  if directional_match:
    return directional_match.group(1)

  all_numbers = re.findall(r"-?\d+(?:\.\d+)?", cleaned)
  if not all_numbers:
    return ""

  decimal_numbers = [num for num in all_numbers if "." in num]
  if decimal_numbers:
    return decimal_numbers[0]

  return all_numbers[0]


def extract_first_range(text):
  match = re.search(r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?", normalize_text(text))
  if not match:
    return ""
  return re.sub(r"\s*-\s*", "-", match.group(0))


def extract_first_json_object(text):
  raw = str(text or "")
  start = raw.find("{")
  if start == -1:
    return ""
  depth = 0
  in_string = False
  escape = False
  for index in range(start, len(raw)):
    char = raw[index]
    if in_string:
      if escape:
        escape = False
      elif char == "\\":
        escape = True
      elif char == '"':
        in_string = False
      continue
    if char == '"':
      in_string = True
    elif char == "{":
      depth += 1
    elif char == "}":
      depth -= 1
      if depth == 0:
        return raw[start:index + 1]
  return ""


def clean_line(value):
  return re.sub(r"\s+", " ", normalize_text(value).strip())


def clean_label(value):
  return re.sub(r"[^A-Za-z0-9/+ -]", "", clean_line(value)).strip(" :-")


def parse_brief_date(text):
  match = re.search(
    r"FX\s+INTELLIGENCE\s+DAILY\s+BRIEF\s*[—-]\s*(\d{1,2})\s+([A-Z]+)\s+(\d{4})",
    str(text or ""),
    flags=re.IGNORECASE,
  )
  if not match:
    return None
  day = int(match.group(1))
  month = MONTH_NAME_MAP.get(match.group(2).upper())
  year = int(match.group(3))
  if not month:
    return None
  return datetime(year, month, day)


def parse_brief_timestamp(text, machine_payload):
  brief_date = parse_brief_date(text)
  time_match = re.search(r"Spot prices as of\s*~?(\d{1,2}:\d{2})\s*BST", str(text or ""), flags=re.IGNORECASE)
  if brief_date and time_match:
    return brief_date.strftime("%Y-%m-%d") + " " + time_match.group(1) + " BST"
  if brief_date:
    return brief_date.strftime("%Y-%m-%d")

  machine_generated = (machine_payload or {}).get("generated")
  if machine_generated:
    try:
      dt = datetime.fromisoformat(str(machine_generated).replace("Z", "+00:00"))
      return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
      pass
  return ""


def split_numbered_sections(text):
  matches = list(re.finditer(r"(?m)^\s*(\d+)\.\s+(.+?)\s*$", str(text or "")))
  sections = {}
  for index, match in enumerate(matches):
    section_number = int(match.group(1))
    section_title = clean_line(match.group(2))
    body_start = match.end()
    body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
    sections[section_number] = {
      "title": section_title,
      "body": str(text[body_start:body_end]).strip(),
    }
  return sections


def split_paragraphs(text):
  return [
    clean_line(chunk)
    for chunk in re.split(r"\n\s*\n", str(text or ""))
    if clean_line(chunk)
  ]


def theme_title_from_paragraph(text):
  paragraph = clean_line(text)
  if ":" in paragraph:
    return clean_label(paragraph.split(":", 1)[0]) or "Macro Theme"
  first_sentence = paragraph.split(".", 1)[0]
  words = clean_label(first_sentence).split()
  return " ".join(words[:6]).strip() or "Macro Theme"


def theme_meta(paragraph, index):
  lower = paragraph.lower()
  if index == 0:
    return "CRITICAL", "CRITICAL - PRIMARY DRIVER"
  if "structural" in lower or ("usd" in lower and "weak" in lower):
    return "HIGH", "HIGH - STRUCTURAL"
  if "boj" in lower or "intervention" in lower or "fomc" in lower:
    return "HIGH", "HIGH - EVENT RISK"
  if "ecb" in lower or "tariff" in lower or "energy" in lower:
    return "HIGH", "HIGH - DEFINING THEME"
  return "MEDIUM", "MEDIUM - ACTIONABLE DIVERGENCE"


def build_manual_macro_sections(text):
  paragraphs = split_paragraphs(text)
  if not paragraphs:
    return {}, []

  market_regime = ""
  usd_bias = ""
  top_risks = []
  macro_themes = []

  for index, paragraph in enumerate(paragraphs[:5]):
    severity, tag = theme_meta(paragraph, index)
    title = theme_title_from_paragraph(paragraph)
    macro_themes.append({
      "title": title,
      "severity": severity,
      "summary": paragraph,
      "tag": tag,
    })
    if index > 0 and len(top_risks) < 3:
      top_risks.append(title)

  if paragraphs:
    market_regime = paragraphs[0]
  if len(paragraphs) > 1:
    usd_bias = paragraphs[1]

  what_changed = [
    {
      "development": theme.get("title", ""),
      "fx_impact": theme.get("summary", ""),
    }
    for theme in macro_themes[:4]
  ]
  return {
    "market_regime": market_regime,
    "usd_bias": usd_bias,
    "top_risks": top_risks,
    "macro_themes": macro_themes,
    "what_changed": what_changed,
  }, paragraphs


def parse_machine_pairs(machine_payload):
  pairs = {}
  for item in (machine_payload or {}).get("pairs", []):
    label = pair_label_from_code(item.get("pair", ""))
    code = normalize_pair_code(item.get("pair", ""))
    if not label or not code:
      continue
    pairs[label] = {
      "pair": label,
      "code": code,
      "spot": item.get("spot"),
      "trigger": "" if item.get("trigger_low") is None or item.get("trigger_high") is None else f"{item.get('trigger_low')}-{item.get('trigger_high')}",
      "target": "" if item.get("target_low") is None or item.get("target_high") is None else f"{item.get('target_low')}-{item.get('target_high')}",
      "invalidation": item.get("invalidation"),
      "rr": item.get("rr"),
      "confidence": item.get("confidence"),
      "notes": clean_line(item.get("notes", "")),
      "bias": clean_line(item.get("bias", "")).replace("_", " "),
      "direction": clean_line(item.get("direction", "")),
    }
  return pairs


def _bias_from_machine_item(item):
  direction = clean_line(item.get("direction", "")).lower()
  bias_text = clean_line(item.get("bias", "")).lower()
  if "short" in direction:
    return "Bearish"
  if "long" in direction:
    return "Bullish"
  if "bear" in bias_text:
    return "Bearish"
  if "bull" in bias_text:
    return "Bullish"
  return "Neutral"


def _status_from_machine_item(item):
  bias_text = clean_line(item.get("bias", "")).lower()
  if "trade" in bias_text:
    return "Trade"
  if "watch" in bias_text:
    return "Watch"
  return "Watch"


def _to_float(value, default=0.0):
  try:
    return float(value)
  except Exception:
    return float(default)


def build_machine_trade_overrides(machine_payload, raw_text):
  pairs_raw = (machine_payload or {}).get("pairs", [])
  if not isinstance(pairs_raw, list) or not pairs_raw:
    return {}

  core_pairs = []
  ranked = []

  for idx, item in enumerate(pairs_raw):
    label = pair_label_from_code(item.get("pair", ""))
    if not label:
      continue
    code = normalize_pair_code(item.get("pair", ""))
    dp = pair_dp(code)
    spot_raw = item.get("spot", "")
    try:
      spot_text = f"{float(spot_raw):.{dp}f}"
    except Exception:
      spot_text = str(spot_raw)
    bias = _bias_from_machine_item(item)
    status = _status_from_machine_item(item)
    confidence_pct = confidence_to_pct(item.get("confidence", 3))
    trigger = "" if item.get("trigger_low") is None or item.get("trigger_high") is None else f"{item.get('trigger_low')}-{item.get('trigger_high')}"
    target = "" if item.get("target_low") is None or item.get("target_high") is None else f"{item.get('target_low')}-{item.get('target_high')}"
    rr_raw = clean_line(item.get("rr", ""))
    rr_text = rr_raw if (":" in rr_raw or "x" in rr_raw.lower()) else (rr_raw + ":1" if rr_raw else "")

    row = {
      "pair": label,
      "status": status,
      "bias": bias,
      "live_spot": spot_text,
      "day_change_pct": "",
      "trigger": trigger,
      "target": target,
      "invalidation": str(item.get("invalidation", "")),
      "catalyst": clean_line(item.get("notes", "")),
      "confidence_pct": confidence_pct,
      "summary": clean_line(item.get("notes", "")),
      "setup": clean_line(item.get("direction", "")) or ("Long" if bias == "Bullish" else "Short" if bias == "Bearish" else "Setup"),
      "entry_zone": trigger,
      "stop": str(item.get("invalidation", "")),
      "rr": rr_text,
      "invalidation_risk": clean_line(item.get("notes", "")),
      "_rank_index": idx,
      "_rr_num": _to_float(item.get("rr", 0)),
    }

    core_pairs.append({k: row[k] for k in ["pair", "status", "bias", "live_spot", "day_change_pct", "trigger", "target", "invalidation", "catalyst", "confidence_pct", "summary"]})
    ranked.append(row)

  # Build Top 5 from strongest machine pairs when only machine JSON is present.
  ranked.sort(key=lambda r: (-int(r.get("confidence_pct", 0) or 0), -float(r.get("_rr_num", 0) or 0), int(r.get("_rank_index", 0) or 0)))
  top5 = []
  for rank, row in enumerate(ranked[:5], 1):
    top5.append({
      "rank": rank,
      "pair": row.get("pair", ""),
      "setup": row.get("setup", "Setup"),
      "live_spot": row.get("live_spot", ""),
      "entry_zone": row.get("entry_zone", ""),
      "stop": row.get("stop", ""),
      "target": row.get("target", ""),
      "rr": row.get("rr", ""),
      "confidence_pct": row.get("confidence_pct", 0),
      "catalyst": row.get("catalyst", ""),
      "invalidation_risk": row.get("invalidation_risk", ""),
    })

  top5_pairs = {row.get("pair", "") for row in top5}
  secondary = []
  for row in core_pairs:
    if row.get("pair", "") in top5_pairs:
      continue
    secondary.append({
      "pair": row.get("pair", ""),
      "spot": row.get("live_spot", ""),
      "bias": row.get("bias", "Neutral"),
      "notes": row.get("summary", ""),
    })

  return {
    "analysis_timestamp_bst": parse_brief_timestamp(raw_text, machine_payload),
    "core_pairs": core_pairs,
    "top5": top5,
    "secondary": secondary,
  }


def split_table_columns(line):
  return [part.strip() for part in re.split(r"\t+|\s{2,}", str(line or "").strip()) if part.strip()]


def parse_bias_field(value):
  parts = clean_line(value).split()
  if not parts:
    return "Watch", "Neutral"
  status = parts[0].title()
  bias = " ".join(parts[1:]).title() if len(parts) > 1 else "Neutral"
  return status, bias or "Neutral"


def parse_core_pairs_table(text, machine_pairs):
  core_pairs = []
  confidence_by_pair = {}
  for raw_line in str(text or "").splitlines():
    line = raw_line.strip()
    if not line or line.lower().startswith("pair"):
      continue
    columns = split_table_columns(line)
    if len(columns) < 7:
      continue
    label = columns[0]
    if normalize_pair_code(label) == "DXY":
      continue
    status, bias = parse_bias_field(columns[1])
    machine = machine_pairs.get(label, {})
    confidence_pct = confidence_to_pct(columns[6])
    confidence_by_pair[label] = confidence_pct
    core_pairs.append({
      "pair": label,
      "status": status,
      "bias": bias,
      "live_spot": machine.get("spot", "") or "",
      "day_change_pct": "",
      "trigger": columns[2],
      "target": columns[3],
      "invalidation": columns[4],
      "catalyst": machine.get("notes", ""),
      "confidence_pct": confidence_pct,
      "summary": machine.get("notes", "") or f"R/R {columns[5]}. Confidence {columns[6]}/5.",
    })
  return core_pairs, confidence_by_pair


def parse_labeled_block(text):
  fields = {}
  current_key = ""
  for raw_line in str(text or "").splitlines():
    line = raw_line.strip()
    if not line:
      continue
    match = re.match(r"^([A-Z][A-Z/ ]+):\s*(.*)$", line)
    if match:
      current_key = match.group(1).strip()
      fields[current_key] = clean_line(match.group(2))
      continue
    if current_key:
      fields[current_key] = clean_line(fields[current_key] + " " + line)
  return fields


def find_top5_headers(text):
  raw_text = str(text or "")
  setup_headers = []
  setup_matches = list(re.finditer(r"(?m)^\s*SETUP\s+(\d+)\s*:\s*(.+?)\s*$", raw_text))
  for match in setup_matches:
    setup_headers.append({
      "rank": int(match.group(1)),
      "pair": "",
      "header": clean_line(match.group(2)),
      "start": match.start(),
      "body_start": match.end(),
    })
  if setup_headers:
    return setup_headers

  plain_headers = []
  plain_matches = list(re.finditer(r"(?m)^\s*([A-Z]{3}/[A-Z]{3}|DXY)\s+[–-]\s+(.+?)\s*$", raw_text))
  for index, match in enumerate(plain_matches, 1):
    pair = clean_line(match.group(1))
    remainder = clean_line(match.group(2))
    plain_headers.append({
      "rank": index,
      "pair": pair,
      "header": pair + " - " + remainder,
      "start": match.start(),
      "body_start": match.end(),
    })
  return plain_headers


def parse_top5_setups(text, machine_pairs, confidence_by_pair, core_pairs):
  matches = find_top5_headers(text)
  setups = []
  setup_pairs = set()
  pair_lookup = {row.get("pair", ""): row for row in (core_pairs or [])}
  for index, match in enumerate(matches):
    rank = int(match.get("rank", index + 1) or (index + 1))
    header = clean_line(match.get("header", ""))
    body_start = int(match.get("body_start", 0) or 0)
    body_end = matches[index + 1].get("start") if index + 1 < len(matches) else len(text)
    fields = parse_labeled_block(text[body_start:body_end])
    header_parts = [part.strip() for part in re.split(r"\s+[–-]\s+", header) if part.strip()]
    pair = match.get("pair", "") or (header_parts[0] if header_parts else "")
    machine = machine_pairs.get(pair, {})
    core_pair = pair_lookup.get(pair, {})
    direction = " - ".join(header_parts[1:]) if len(header_parts) > 1 else clean_line(fields.get("BIAS", "Setup"))
    entry_zone = core_pair.get("trigger") or machine.get("trigger") or extract_first_range(fields.get("TRIGGER", ""))
    target_zone = core_pair.get("target") or machine.get("target") or extract_first_range(fields.get("TARGET", ""))
    stop_value = extract_invalidation_level(fields.get("INVALIDATION", "")) or extract_invalidation_level(core_pair.get("invalidation", ""))
    rr_value = clean_line(fields.get("RISK/REWARD", "")) or clean_line(machine.get("rr", ""))
    confidence_pct = confidence_by_pair.get(pair, confidence_to_pct(machine.get("confidence", 3)))
    if pair:
      setup_pairs.add(pair)
    setups.append({
      "rank": rank,
      "pair": pair,
      "setup": direction or "Setup",
      "live_spot": machine.get("spot", "") or core_pair.get("live_spot", ""),
      "entry_zone": entry_zone,
      "stop": stop_value,
      "target": target_zone,
      "rr": rr_value,
      "confidence_pct": confidence_pct,
      "catalyst": clean_line(fields.get("CATALYSTS", "")),
      "invalidation_risk": clean_line(fields.get("INVALIDATION", "")),
    })
  return setups, setup_pairs


def build_secondary_from_manual(core_pairs, setup_pairs, machine_pairs):
  secondary = []
  for row in core_pairs:
    pair = row.get("pair", "")
    if not pair or pair in setup_pairs:
      continue
    if str(row.get("status", "")).lower() == "avoid":
      continue
    machine = machine_pairs.get(pair, {})
    secondary.append({
      "pair": pair,
      "spot": row.get("live_spot", "") or machine.get("spot", ""),
      "bias": row.get("bias", "Neutral"),
      "notes": machine.get("notes", "") or row.get("summary", ""),
    })
  return secondary


def parse_avoid_list(text):
  avoid = []
  for raw_line in str(text or "").splitlines():
    line = raw_line.strip()
    if not line or line.lower().startswith("pair"):
      continue
    match = re.match(r"^([A-Z]{3}/[A-Z]{3}|DXY)\s*:\s*(.+)$", line)
    if not match:
      continue
    avoid.append({
      "pair": match.group(1),
      "reason": clean_line(match.group(2)),
    })
  return avoid


def infer_calendar_impact(event_name, risk_skew):
  text = (str(event_name or "") + " " + str(risk_skew or "")).lower()
  if any(keyword in text for keyword in ["fomc", "boj", "cpi", "retail sales", "scotus", "gdp"]):
    return "High"
  if any(keyword in text for keyword in ["sentiment", "commentary", "activity"]):
    return "Medium"
  return "Medium"


def parse_calendar(text):
  rows = []
  for raw_line in str(text or "").splitlines():
    line = raw_line.strip()
    if not line or line.lower().startswith("time"):
      continue
    columns = split_table_columns(line)
    if len(columns) < 5:
      continue
    date_time = columns[0]
    date_match = re.match(r"^(.*?)(?:\s+[–-]\s+(.+))?$", date_time)
    date_bst = clean_line(date_match.group(1)) if date_match else date_time
    time_bst = clean_line(date_match.group(2)) if date_match and date_match.group(2) else "TBC"
    event = columns[1]
    expected = columns[3]
    risk_skew = columns[4]
    rows.append({
      "date_bst": date_bst,
      "time_bst": time_bst,
      "event": f"{event} ({expected})",
      "ccy": columns[2],
      "impact": infer_calendar_impact(event, risk_skew),
    })
  return rows


def parse_correlation_notes(text):
  notes = []
  for raw_line in str(text or "").splitlines():
    line = raw_line.strip()
    if not line:
      continue
    match = re.match(r"^([^:]+):\s*(.+)$", line)
    if not match:
      continue
    heading = clean_line(match.group(1))
    implication = clean_line(match.group(2))
    parts_match = re.search(r"\(([^)]+)\)", heading)
    pair_b = clean_line(parts_match.group(1)) if parts_match else ""
    correlation_match = re.search(r"(>\s*0\.\d+|0\.\d+\+?|inverse)", implication, flags=re.IGNORECASE)
    correlation = correlation_match.group(1) if correlation_match else "Linked"
    notes.append({
      "pair_a": clean_label(re.sub(r"\([^)]*\)", "", heading)),
      "pair_b": pair_b,
      "correlation": correlation,
      "implication": implication,
    })
  return notes


def parse_checklist(text):
  items = []
  for raw_line in str(text or "").splitlines():
    line = clean_line(raw_line)
    if not line:
      continue
    items.append({
      "item": line,
      "status": "neutral",
      "notes": "",
    })
  return items


def parse_daily_brief(text):
  raw_text = str(text or "")
  json_blob = extract_first_json_object(raw_text)
  machine_payload = {}
  if json_blob:
    try:
      machine_payload = json.loads(json_blob)
    except json.JSONDecodeError:
      machine_payload = {}

  sections = split_numbered_sections(raw_text)
  if not sections:
    return build_machine_trade_overrides(machine_payload, raw_text)

  machine_pairs = parse_machine_pairs(machine_payload)
  overview_data, _ = build_manual_macro_sections(sections.get(1, {}).get("body", ""))
  core_pairs, confidence_by_pair = parse_core_pairs_table(sections.get(2, {}).get("body", ""), machine_pairs)
  top5, setup_pairs = parse_top5_setups(sections.get(3, {}).get("body", ""), machine_pairs, confidence_by_pair, core_pairs)

  for row in core_pairs:
    machine = machine_pairs.get(row.get("pair", ""), {})
    matching_setup = next((item for item in top5 if item.get("pair") == row.get("pair")), None)
    if matching_setup and matching_setup.get("catalyst"):
      row["catalyst"] = matching_setup.get("catalyst")
    elif machine.get("notes"):
      row["catalyst"] = machine.get("notes")
    if machine.get("notes"):
      row["summary"] = machine.get("notes")

  overrides = {
    "analysis_timestamp_bst": parse_brief_timestamp(raw_text, machine_payload),
    "core_pairs": core_pairs,
    "top5": top5,
    "secondary": build_secondary_from_manual(core_pairs, setup_pairs, machine_pairs),
    "avoid": parse_avoid_list(sections.get(4, {}).get("body", "")),
    "correlation_notes": parse_correlation_notes(sections.get(5, {}).get("body", "")),
    "risk_calendar": parse_calendar(sections.get(6, {}).get("body", "")),
    "checklist": parse_checklist(sections.get(7, {}).get("body", "")),
  }
  overrides.update(overview_data)
  return {key: value for key, value in overrides.items() if value}


def load_daily_brief_overrides(path):
  if not path.exists():
    return {}
  raw_text = path.read_text(encoding="utf-8")
  if not raw_text.strip():
    return {}
  return parse_daily_brief(raw_text)


def merge_dashboard_payload(base_payload, overrides):
  merged = dict(base_payload or {})
  for key, value in (overrides or {}).items():
    if value in (None, "", [], {}):
      continue
    merged[key] = value
  return merged


def cleanup_generated_html(text):
  cleaned = str(text or "")
  replacements = {
    "â€”": "-",
    "â€“": "-",
    "â€¦": "...",
    "â†”": "<->",
    "âš ": "!",
    "Â±": "+/-",
    "Â·": " | ",
    "…": "...",
    "—": "-",
    "–": "-",
    "→": "->",
    "↔": "<->",
    "⚠": "!",
    "☐": "[ ]",
  }
  for old, new in replacements.items():
    cleaned = cleaned.replace(old, new)
  return cleaned


def badge_class(status):
  st = (status or "").lower()
  if "trade" in st:
    return "badge badge-trade"
  if "watch" in st:
    return "badge badge-watch"
  return "badge badge-neutral"


def pair_class(bias, status):
  b = (bias or "").lower()
  if "watch" in (status or "").lower():
    return "watch-pair"
  if "bull" in b:
    return "bull"
  if "bear" in b:
    return "bear"
  return "neutral-pair"


def bias_class(bias):
  b = (bias or "").lower()
  if "bull" in b:
    return "bias bias-bull"
  if "bear" in b:
    return "bias bias-bear"
  return "bias bias-neutral"


def sev_class(severity):
  sev_upper = (severity or "").upper()
  if any(x in sev_upper for x in ["HIGH", "CRITICAL"]):
    return "tag-critical"
  if any(x in sev_upper for x in ["MED", "MODERATE"]):
    return "tag-high"
  return "tag-medium"


def impact_cls(impact):
  i = (impact or "").lower()
  if "critical" in i:
    return "badge badge-avoid"
  if "high" in i:
    return "badge badge-avoid"
  if "med" in i:
    return "badge badge-watch"
  return "badge badge-neutral"


def conf_level(pct):
  try:
    v = int(str(pct).replace("%", "").strip())
  except Exception:
    v = 0
  if v >= 67:
    return "high"
  if v >= 45:
    return "med"
  return "low"


def pair_code(pair_label):
  code = (pair_label or "").upper().replace("/", "").replace(" ", "")
  if len(code) == 6 and code.isalpha():
    return code
  return ""


def pair_dp(code):
  return 2 if code.endswith("JPY") else 4


def _parse_range_midpoint(text):
  raw = str(text or "")
  # Prefer explicit range parsing first (e.g. 1.1760-1.1800).
  range_match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", raw)
  if range_match:
    low = float(range_match.group(1))
    high = float(range_match.group(2))
    return (low + high) / 2

  level_match = re.search(r"\d+(?:\.\d+)?", raw)
  if not level_match:
    return None
  return float(level_match.group(0))


def _parse_level(text):
  match = re.search(r"\d+(?:\.\d+)?", str(text or ""))
  if not match:
    return None
  return float(match.group(0))


def _pip_factor(code):
  return 100 if str(code or "").endswith("JPY") else 10000


def format_rr_for_top5(rr_text, pair, setup, entry_zone, target, stop):
  raw = str(rr_text or "").strip()
  if not raw:
    return ""

  # Keep detailed user-provided R/R text untouched.
  if any(token in raw for token in ["(", "mid-", "pip"]):
    return raw

  # Expand compact values like "2.17x", "2.2", or "2.5:1" into midpoint + pip math text.
  compact = re.match(r"^\s*~?\s*(\d+(?:\.\d+)?)\s*(?::\s*1(?:\.0+)?)?\s*(?:x)?\s*$", raw, flags=re.IGNORECASE)
  if not compact:
    return raw

  ratio_from_input = float(compact.group(1))

  code = pair_code(pair)
  dp = pair_dp(code)
  entry_mid = _parse_range_midpoint(entry_zone)
  target_mid = _parse_range_midpoint(target)
  stop_level = _parse_level(stop)
  if entry_mid is None or target_mid is None or stop_level is None:
    return raw

  reward_pips = abs(target_mid - entry_mid) * _pip_factor(code)
  risk_pips = abs(entry_mid - stop_level) * _pip_factor(code)
  if risk_pips <= 0:
    return raw

  rr_prefix = "~" + f"{ratio_from_input:.1f}" + ":1"
  mid_label = "mid-entry" if any(x in str(setup or "").upper() for x in ["SHORT", "SELL"]) else "mid-trigger"

  return (
    rr_prefix
    + " ("
    + mid_label
    + " "
    + f"{entry_mid:.{dp}f}"
    + " -> mid-target "
    + f"{target_mid:.{dp}f}"
    + " = "
    + str(int(round(reward_pips)))
    + " pips; stop "
    + f"{stop_level:.{dp}f}"
    + " = "
    + str(int(round(risk_pips)))
    + " pips)."
  )


def rr_html_two_lines(rr_text):
  raw = str(rr_text or "").strip()
  if not raw:
    return ""
  split_at = raw.find(" (")
  if split_at == -1:
    return s(raw)
  head = raw[:split_at].strip()
  detail = raw[split_at + 1 :].strip()
  return s(head) + '<br><span class="rr-detail">' + s(detail) + "</span>"


def core_pair_from_top5(item):
  setup = (item.get("setup", "") or "").lower()
  if "buy" in setup or "long" in setup:
    bias = "Bullish"
  elif "sell" in setup or "short" in setup:
    bias = "Bearish"
  else:
    bias = "Neutral"

  return {
    "pair": item.get("pair", ""),
    "status": "Watch",
    "bias": bias,
    "live_spot": item.get("live_spot", ""),
    "day_change_pct": "",
    "trigger": item.get("entry_zone", ""),
    "target": item.get("target", ""),
    "invalidation": item.get("stop", ""),
    "catalyst": item.get("catalyst", ""),
    "confidence_pct": item.get("confidence_pct", 0),
    "summary": item.get("invalidation_risk", ""),
  }


def core_pair_from_secondary(item):
  return {
    "pair": item.get("pair", ""),
    "status": "Watch",
    "bias": item.get("bias", "Neutral"),
    "live_spot": item.get("spot", ""),
    "day_change_pct": "",
    "trigger": "Watch key levels",
    "target": "Directional follow-through",
    "invalidation": "No momentum confirmation",
    "catalyst": item.get("notes", ""),
    "confidence_pct": 45,
    "summary": item.get("notes", ""),
  }


def ensure_core_pairs_count(core_pairs, top5, secondary, target=6):
  merged = list(core_pairs or [])
  seen = set()
  for row in merged:
    code = pair_code(row.get("pair", ""))
    if code:
      seen.add(code)

  # If model returned more than target, keep first target to preserve ranking/order.
  if len(merged) >= target:
    return merged[:target]

  for row in (top5 or []):
    code = pair_code(row.get("pair", ""))
    if not code or code in seen:
      continue
    merged.append(core_pair_from_top5(row))
    seen.add(code)
    if len(merged) >= target:
      return merged

  for row in (secondary or []):
    code = pair_code(row.get("pair", ""))
    if not code or code in seen:
      continue
    merged.append(core_pair_from_secondary(row))
    seen.add(code)
    if len(merged) >= target:
      return merged

  return merged


def rates_strip(rates):
  items = []
  for pair, spot in rates.items():
    items.append(
      '<div class="ticker-item"><span class="status-label">'
      + s(pair)
      + '</span><span class="status-val">'
      + s(spot)
      + "</span></div>"
    )
  return "".join(items)


def build_macro_themes(themes):
  cards = []
  for i, t in enumerate(themes, 1):
    sev = (t.get("severity") or "").strip()
    sev_upper = sev.upper()
    cards.append(
      '<div class="macro-card">'
      '<div class="macro-card-header"><span style="font-size:13px">!</span>'
      '<span class="macro-theme-label">THEME '
      + s(i)
      + "</span></div>"
      '<div class="macro-title">'
      + s(t.get("title", ""))
      + "</div>"
      '<div class="macro-body">'
      + s(t.get("summary", ""))
      + "</div>"
      '<span class="macro-tag '
      + sev_class(sev)
      + '">'
      + s((t.get("tag") or sev_upper or "LOW"))
      + "</span>"
      "</div>"
    )
  return "\n".join(cards)


def ensure_macro_theme_count(themes, target=5):
  merged = list(themes or [])
  if len(merged) >= target:
    return merged[:target]

  seen_titles = {str(t.get("title", "")).strip().lower() for t in merged}
  for fallback in SOURCE_MACRO_THEMES:
    title = str(fallback.get("title", "")).strip().lower()
    if title and title in seen_titles:
      continue
    merged.append(fallback)
    seen_titles.add(title)
    if len(merged) >= target:
      break

  return merged


def build_core_pair_cards(pairs):
  out = []
  for p in pairs:
    conf = p.get("confidence_pct", 0)
    code = pair_code(p.get("pair", ""))
    bias_text = s(p.get("bias", ""))
    raw_status = str(p.get("status", "") or "")
    status_lower = raw_status.lower()
    if "active" in status_lower:
      status_text_raw = "Trade" if int(conf or 0) >= 65 else "Watch"
    else:
      status_text_raw = raw_status
    status_text = s(status_text_raw)
    spot_attrs = ''
    chg_attrs = ''
    card_attrs = ''
    if code:
      spot_attrs = ' data-pair="' + s(code) + '" data-dp="' + s(pair_dp(code)) + '"'
      chg_attrs = ' data-pair-chg="' + s(code) + '"'
      card_attrs = ' data-pair-card="' + s(code) + '" data-origin-spot="' + s(p.get("live_spot", "")) + '"'
    spot_text = '—' if code else s(p.get("live_spot", ""))
    chg_text = '' if code else s(p.get("day_change_pct", ""))
    out.append(
      '<div class="pair-card '
      + pair_class(p.get("bias", ""), p.get("status", ""))
      + '"'
      + card_attrs
      + '>'
      '<div class="pair-header">'
      '<span class="pair-name">'
      + s(p.get("pair", ""))
      + "</span>"
      '<span class="'
      + badge_class(status_text_raw)
      + '" data-role="badge">'
      + status_text
      + "</span>"
      '<span class="'
      + bias_class(p.get("bias", ""))
      + '" data-role="bias">'
      + bias_text
      + "</span>"
      "</div>"
      '<div class="pair-spot-row"><span class="pair-spot"'
      + spot_attrs
      + ">"
      + spot_text
      + "</span><span class=\"pair-chg\""
      + chg_attrs
      + ">"
      + chg_text
      + "</span></div>"
      '<div class="pair-body">'
      '<div class="pair-detail-row"><span class="pair-label">Trigger</span><span class="pair-value mono" data-role="trigger">'
      + s(p.get("trigger", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Target</span><span class="pair-value mono" data-role="target">'
      + s(p.get("target", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Invalidation</span><span class="pair-value mono" data-role="invalidation">'
      + s(p.get("invalidation", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Catalyst</span><span class="pair-value" data-role="catalyst">'
      + s(p.get("catalyst", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Confidence</span><div class="conf-bar-wrap">'
      '<div class="conf-bar"><div class="conf-fill '
      + conf_level(conf)
      + '" style="width:'
      + s(conf)
      + '%" data-role="confidence-fill"></div></div><span class="conf-pct" data-role="confidence-pct">'
      + s(conf)
      + "%</span></div></div></div>"
      '<div class="pair-notes" data-role="notes">'
      + s(p.get("summary", ""))
      + "</div>"
      "</div>"
    )
  return "\n".join(out)


def top5_rows(top5):
  out = []
  for t in top5:
    rank = int(t.get("rank", 0) or 0)
    setup = (t.get("setup", "") or "").upper()
    direction_cls = (
      "dir-buy"
      if ("BUY" in setup or "LONG" in setup)
      else "dir-sell"
      if ("SELL" in setup or "SHORT" in setup)
      else "dir-buy"
    )
    conf = int(t.get("confidence_pct", 0) or 0)
    code = pair_code(t.get("pair", ""))
    live_spot_attrs = ''
    if code:
      live_spot_attrs = ' data-pair="' + s(code) + '" data-dp="' + s(pair_dp(code)) + '"'
    live_spot_text = '—' if code else s(t.get("live_spot", ""))
    rr_text = format_rr_for_top5(
      t.get("rr", ""),
      t.get("pair", ""),
      setup,
      t.get("entry_zone", ""),
      t.get("target", ""),
      t.get("stop", ""),
    )
    rr_html = rr_html_two_lines(rr_text)
    out.append(
      '<div class="setup-card rank-'
      + s(rank or 1)
      + '">'
      '<div class="setup-row">'
      '<span class="setup-rank">'
      + s(rank)
      + "</span>"
      '<span class="setup-pair-name">'
      + s(t.get("pair", ""))
      + "</span>"
      '<span class="setup-direction '
      + direction_cls
      + '">'
      + s(setup or "SETUP")
      + "</span>"
      '<div class="setup-fields">'
      '<div class="setup-field"><span class="sf-label">Live Spot</span><span class="sf-val"'
      + live_spot_attrs
      + ">"
      + live_spot_text
      + "</span></div>"
      '<div class="setup-field"><span class="sf-label">Entry Zone</span><span class="sf-val">'
      + s(t.get("entry_zone", ""))
      + "</span></div>"
      '<div class="setup-field"><span class="sf-label">Stop</span><span class="sf-val" style="color:var(--red)">'
      + s(t.get("stop", ""))
      + "</span></div>"
      '<div class="setup-field"><span class="sf-label">Target</span><span class="sf-val" style="color:var(--green)">'
      + s(t.get("target", ""))
      + "</span></div>"
      '<div class="setup-field"><span class="sf-label">R/R</span><span class="sf-val rr-val" style="color:var(--green)">'
      + rr_html
      + "</span></div>"
      "</div>"
      '<div class="conf-indicator"><span style="font-size:12px;color:var(--green);font-weight:700">'
      + s(conf)
      + "%</span></div>"
      "</div>"
      '<div class="setup-body">'
      '<div class="setup-detail"><div class="sd-label">Catalyst</div><div class="sd-val">'
      + s(t.get("catalyst", ""))
      + "</div></div>"
      '<div class="setup-detail"><div class="sd-label">Invalidation / Risk</div><div class="sd-val">'
      + s(t.get("invalidation_risk", ""))
      + "</div></div>"
      "</div>"
      "</div>"
    )
  return "\n".join(out)


def secondary_rows(secondary):
  out = []
  for row in secondary:
    out.append(
      "<tr>"
      "<td><strong>"
      + s(row.get("pair", ""))
      + "</strong></td>"
      '<td class="mono">'
      + s(row.get("spot", ""))
      + "</td>"
      "<td>"
      + s(row.get("bias", ""))
      + "</td>"
      "<td>"
      + s(row.get("notes", ""))
      + "</td>"
      "</tr>"
    )
  return "\n".join(out)


def avoid_cards(avoid):
  out = []
  for a in avoid:
    out.append(
      '<div class="avoid-card"><span class="avoid-pair">'
      + s(a.get("pair", ""))
      + "</span><span class=\"avoid-reason\">"
      + s(a.get("reason", ""))
      + "</span></div>"
    )
  return "\n".join(out)


def risk_calendar_rows(items):
  out = []
  for item in items:
    out.append(
      "<tr>"
      "<td><strong>"
      + s(item.get("date_bst", ""))
      + "</strong></td>"
      '<td class="mono">'
      + s(item.get("time_bst", ""))
      + "</td>"
      "<td>"
      + s(item.get("event", ""))
      + "</td>"
      "<td>"
      + s(item.get("ccy", ""))
      + "</td>"
      '<td><span class="'
      + impact_cls(item.get("impact", ""))
      + '" style="font-size:10px">'
      + s(item.get("impact", ""))
      + "</span></td>"
      "</tr>"
    )
  return "\n".join(out)


def what_changed_rows(changes):
  out = []
  for c in changes:
    out.append(
      "<tr>"
      "<td>"
      + s(c.get("development", ""))
      + "</td>"
      "<td>"
      + s(c.get("fx_impact", ""))
      + "</td>"
      "</tr>"
    )
  return "\n".join(out)


def bond_yields_rows(yields):
  if not yields or len(yields) < 8:
    yields = SOURCE_BOND_YIELDS

  rows = []
  for y in yields:
    yield_value = str(y.get("yield", "") or "").strip()
    if yield_value and not yield_value.endswith("%"):
      yield_value += "%"

    cb_rate = str(y.get("cb_rate", "") or "").strip()
    cb_note = str(y.get("cb_note", "") or "").strip()
    cb_display = cb_rate if cb_rate else cb_note

    lower_cb = cb_display.lower()
    if "bias" in lower_cb or "cut" in lower_cb:
      note_style = " style=\"color:var(--amber)\""
    elif "hiking" in lower_cb or "hawk" in lower_cb:
      note_style = " style=\"color:var(--red)\""
    else:
      note_style = ""

    rows.append(
      "<tr>"
      "<td><strong>"
      + s(y.get("country"))
      + "</strong></td>"
      '<td class="mono">'
      + s(yield_value)
      + "</td>"
      '<td class="trend-up">'
      + s(y.get("trend"))
      + "</td>"
      '<td class="mono"'
      + note_style
      + ">"
      + s(cb_display)
      + "</td>"
      "</tr>"
    )
  midpoint = (len(rows) + 1) // 2
  left = "\n".join(rows[:midpoint])
  right = "\n".join(rows[midpoint:])
  return (
    '<div class="two-col">'
    '<div class="data-table-wrap"><table class="data-table">'
    '<thead><tr><th>Country</th><th>Yield</th><th>Trend</th><th>CB Rate</th></tr></thead>'
    '<tbody>'
    + left
    + "</tbody></table></div>"
    '<div class="data-table-wrap"><table class="data-table">'
    '<thead><tr><th>Country</th><th>Yield</th><th>Trend</th><th>CB Rate</th></tr></thead>'
    '<tbody>'
    + right
    + "</tbody></table></div>"
    "</div>"
  )


def commodities_strip(commodities):
  out = []
  for c in commodities:
    out.append(
      '<div class="commodity-tile">'
      "<div>"
      '<div class="commodity-name">'
      + s(c.get("name"))
      + " ("
      + s(c.get("ticker"))
      + ")</div>"
      '<div class="commodity-price">'
      + s(c.get("value"))
      + "</div></div>"
      '<div style="text-align:right">'
      '<div class="commodity-change ' + s(c.get("context_class", "")) + '">'
      + s(c.get("change"))
      + "</div>"
      '<div class="commodity-note">'
      + s(c.get("context"))
      + "</div></div></div>"
    )
  return "\n".join(out)


def correlation_rows(corr):
  out = []
  for c in corr:
    out.append(
      "<tr>"
      "<td>"
      + s(c.get("pair_a"))
      + "</td>"
      "<td>"
      + s(c.get("pair_b"))
      + "</td>"
      "<td>"
      + s(c.get("correlation"))
      + "</td>"
      "<td>"
      + s(c.get("implication"))
      + "</td>"
      "</tr>"
    )
  return "\n".join(out)


def checklist_rows(checklist):
  out = []
  for item in checklist:
    status = (item.get("status") or "").lower()
    icon = "[x]" if status == "pass" else "[!]" if status == "fail" else "[ ]"
    cls = "pass" if status == "pass" else "fail" if status == "fail" else "neutral"
    out.append(
      "<tr>"
      '<td class="check-icon '
      + cls
      + '">'
      + icon
      + "</td>"
      "<td>"
      + s(item.get("item"))
      + "</td>"
      "<td>"
      + s(item.get("notes"))
      + "</td>"
      "</tr>"
    )
  return "\n".join(out)


def short_analysis_date(value):
  ts = str(value or "").strip()
  if not ts:
    return ""
  try:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.strftime("%d %b %Y")
  except Exception:
    pass
  # Fallback for already-formatted strings like "2026-04-16 07:05:00 BST"
  parts = ts.replace("T", " ").split()
  if parts:
    try:
      dt = datetime.fromisoformat(parts[0])
      return dt.strftime("%d %b %Y")
    except Exception:
      return parts[0]
  return ts


with open(JSON_PATH, "r", encoding="utf-8") as f:
  d = json.load(f)

brief_overrides = load_daily_brief_overrides(DAILY_BRIEF_PATH)
if brief_overrides:
  d = merge_dashboard_payload(d, brief_overrides)

html_text = TEMPLATE_PATH.read_text(encoding="utf-8")

live_rates = d.get("live_rates") or d.get("live_rates_snapshot") or {}

# When a daily brief is present, trade ideas must come only from that brief.
trade_source = brief_overrides if brief_overrides else d
top5 = trade_source.get("top5") or trade_source.get("top_5_setups") or []
secondary = trade_source.get("secondary") or trade_source.get("secondary_pairs") or []
core_pairs = ensure_core_pairs_count(trade_source.get("core_pairs", []), top5, secondary, target=CORE_PAIRS_TARGET)
avoid = trade_source.get("avoid", [])

macro_themes = ensure_macro_theme_count(d.get("macro_themes", []), target=5)
analysis_ts = d.get("analysis_timestamp_bst", d.get("generated_bst", ""))
analysis_date_short = short_analysis_date(analysis_ts)

html_text = html_text.replace("__ANALYSIS_TIMESTAMP__", s(analysis_ts))
html_text = html_text.replace("__ANALYSIS_DATE_SHORT__", s(analysis_date_short))
html_text = html_text.replace("__MARKET_REGIME__", s(d.get("market_regime", "")))
html_text = html_text.replace("__USD_BIAS__", s(d.get("usd_bias", "")))
html_text = html_text.replace("__TOP_RISKS__", s(", ".join(d.get("top_risks", []))))
html_text = html_text.replace("__RATES_STRIP__", rates_strip(live_rates))
html_text = html_text.replace("__MACRO_THEMES__", build_macro_themes(macro_themes))
html_text = html_text.replace("__CORE_PAIR_CARDS__", build_core_pair_cards(core_pairs))
html_text = html_text.replace("__TOP5_ROWS__", top5_rows(top5))
html_text = html_text.replace("__SECONDARY_ROWS__", secondary_rows(secondary))
html_text = html_text.replace("__AVOID_CARDS__", avoid_cards(avoid))
html_text = html_text.replace("__RISK_CALENDAR_ROWS__", risk_calendar_rows(d.get("risk_calendar", [])))
html_text = html_text.replace("__WHAT_CHANGED__", what_changed_rows(d.get("what_changed", [])))
html_text = html_text.replace("__BOND_YIELDS_ROWS__", bond_yields_rows(d.get("bond_yields", [])))
html_text = html_text.replace("__COMMODITIES_STRIP__", commodities_strip(d.get("commodities", [])))
html_text = html_text.replace("__CORRELATION_ROWS__", correlation_rows(d.get("correlation_notes", [])))
html_text = html_text.replace("__CHECKLIST_ROWS__", checklist_rows(d.get("checklist", [])))
html_text = cleanup_generated_html(html_text)

OUTPUT_PATH.write_text(html_text, encoding="utf-8")
if brief_overrides:
  print(f"Applied daily brief overrides from {DAILY_BRIEF_PATH}")
print(f"Wrote {OUTPUT_PATH}")