import html
import json
import os
from pathlib import Path

JSON_PATH = Path(os.getenv("CORE_JSON", "core_pairs_latest.json"))
TEMPLATE_PATH = Path(os.getenv("DASHBOARD_TEMPLATE", "fx_orginal_template.html"))
OUTPUT_PATH = Path(os.getenv("DASHBOARD_OUTPUT", "dashboard_generated.html"))


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


def build_core_pair_cards(pairs):
  out = []
  for p in pairs:
    conf = p.get("confidence_pct", 0)
    out.append(
      '<div class="pair-card '
      + pair_class(p.get("bias", ""), p.get("status", ""))
      + '">'
      '<div class="pair-header">'
      '<span class="pair-name">'
      + s(p.get("pair", ""))
      + "</span>"
      '<span class="'
      + badge_class(p.get("status", ""))
      + '">'
      + s(p.get("status", ""))
      + "</span>"
      '<span class="'
      + bias_class(p.get("bias", ""))
      + '">'
      + s(p.get("bias", ""))
      + "</span>"
      "</div>"
      '<div class="pair-spot-row"><span class="pair-spot">'
      + s(p.get("live_spot", ""))
      + "</span><span class=\"pair-chg\">"
      + s(p.get("day_change_pct", ""))
      + "</span></div>"
      '<div class="pair-body">'
      '<div class="pair-detail-row"><span class="pair-label">Trigger</span><span class="pair-value mono">'
      + s(p.get("trigger", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Target</span><span class="pair-value mono">'
      + s(p.get("target", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Invalidation</span><span class="pair-value mono">'
      + s(p.get("invalidation", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Catalyst</span><span class="pair-value">'
      + s(p.get("catalyst", ""))
      + "</span></div>"
      '<div class="pair-detail-row"><span class="pair-label">Confidence</span><div class="conf-bar-wrap">'
      '<div class="conf-bar"><div class="conf-fill '
      + conf_level(conf)
      + '" style="width:'
      + s(conf)
      + '%"></div></div><span class="conf-pct">'
      + s(conf)
      + "%</span></div></div></div>"
      '<div class="pair-notes">'
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
    direction_cls = "dir-buy" if "BUY" in setup else "dir-sell" if "SELL" in setup else "dir-buy"
    conf = int(t.get("confidence_pct", 0) or 0)
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
      '<div class="setup-field"><span class="sf-label">Live Spot</span><span class="sf-val">'
      + s(t.get("live_spot", ""))
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
  rows = []
  for y in yields:
    note = y.get("cb_note", "")
    note_style = " style=\"color:var(--red)\"" if "hik" in note.lower() else " style=\"color:var(--amber)\"" if "cut" in note.lower() else ""
    rows.append(
      "<tr>"
      "<td><strong>"
      + s(y.get("country"))
      + "</strong></td>"
      '<td class="mono">'
      + s(y.get("yield"))
      + "%</td>"
      '<td class="trend-up">'
      + s(y.get("trend"))
      + "</td>"
      '<td class="mono"'
      + note_style
      + ">"
      + s(y.get("cb_rate"))
      + " "
      + s(note)
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


with open(JSON_PATH, "r", encoding="utf-8") as f:
  d = json.load(f)

html_text = TEMPLATE_PATH.read_text(encoding="utf-8")

live_rates = d.get("live_rates") or d.get("live_rates_snapshot") or {}
top5 = d.get("top5") or d.get("top_5_setups") or []
secondary = d.get("secondary") or d.get("secondary_pairs") or []

html_text = html_text.replace("__ANALYSIS_TIMESTAMP__", s(d.get("analysis_timestamp_bst", d.get("generated_bst", ""))))
html_text = html_text.replace("__MARKET_REGIME__", s(d.get("market_regime", "")))
html_text = html_text.replace("__USD_BIAS__", s(d.get("usd_bias", "")))
html_text = html_text.replace("__TOP_RISKS__", s(", ".join(d.get("top_risks", []))))
html_text = html_text.replace("__RATES_STRIP__", rates_strip(live_rates))
html_text = html_text.replace("__MACRO_THEMES__", build_macro_themes(d.get("macro_themes", [])))
html_text = html_text.replace("__CORE_PAIR_CARDS__", build_core_pair_cards(d.get("core_pairs", [])))
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