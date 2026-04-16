import html
import json
import os
from pathlib import Path
from datetime import datetime

JSON_PATH = Path(os.getenv("CORE_JSON", "core_pairs_latest.json"))
TEMPLATE_PATH = Path(os.getenv("DASHBOARD_TEMPLATE", "fx_orginal_template.html"))
OUTPUT_PATH = Path(os.getenv("DASHBOARD_OUTPUT", "dashboard_generated.html"))
CORE_PAIRS_TARGET = int(os.getenv("CORE_PAIRS_TARGET", "7"))

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
      card_attrs = ' data-pair-card="' + s(code) + '"'
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
      '<div class="setup-field"><span class="sf-label">R/R</span><span class="sf-val" style="color:var(--green)">'
      + s(t.get("rr", ""))
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
    icon = "✓" if status == "pass" else "✗" if status == "fail" else "-"
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

html_text = TEMPLATE_PATH.read_text(encoding="utf-8")

live_rates = d.get("live_rates") or d.get("live_rates_snapshot") or {}
top5 = d.get("top5") or d.get("top_5_setups") or []
secondary = d.get("secondary") or d.get("secondary_pairs") or []
core_pairs = ensure_core_pairs_count(d.get("core_pairs", []), top5, secondary, target=CORE_PAIRS_TARGET)
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
html_text = html_text.replace("__AVOID_CARDS__", avoid_cards(d.get("avoid", [])))
html_text = html_text.replace("__RISK_CALENDAR_ROWS__", risk_calendar_rows(d.get("risk_calendar", [])))
html_text = html_text.replace("__WHAT_CHANGED__", what_changed_rows(d.get("what_changed", [])))
html_text = html_text.replace("__BOND_YIELDS_ROWS__", bond_yields_rows(d.get("bond_yields", [])))
html_text = html_text.replace("__COMMODITIES_STRIP__", commodities_strip(d.get("commodities", [])))
html_text = html_text.replace("__CORRELATION_ROWS__", correlation_rows(d.get("correlation_notes", [])))
html_text = html_text.replace("__CHECKLIST_ROWS__", checklist_rows(d.get("checklist", [])))

OUTPUT_PATH.write_text(html_text, encoding="utf-8")
print(f"Wrote {OUTPUT_PATH}")