import json
import os
from pathlib import Path

JSON_PATH = Path(os.getenv("CORE_JSON", "core_pairs_latest.json"))
TEMPLATE_PATH = Path(os.getenv("DASHBOARD_TEMPLATE", "dashboard_template.html"))
OUTPUT_PATH = Path(os.getenv("DASHBOARD_OUTPUT", "dashboard_generated.html"))


def badge_class(status: str) -> str:
    s = (status or "").lower()
    if "trade" in s:
        return "trade"
    if "watch" in s:
        return "watch"
    return "neutral"


with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

cards = []
for p in data.get("core_pairs", []):
    cards.append(f"""
    <article class="pair-card {badge_class(p.get("status", ""))}">
      <div class="pair-head">
        <h3>{p.get("pair", "")}</h3>
        <span class="status">{p.get("status", "")}</span>
      </div>
      <div class="bias">{p.get("bias", "")}</div>
      <div class="spot">{p.get("live_spot", "")}</div>
      <dl>
        <dt>Trigger</dt><dd>{p.get("trigger", "")}</dd>
        <dt>Target</dt><dd>{p.get("target", "")}</dd>
        <dt>Invalidation</dt><dd>{p.get("invalidation", "")}</dd>
        <dt>Catalyst</dt><dd>{p.get("catalyst", "")}</dd>
        <dt>Confidence</dt><dd>{p.get("confidence_pct", "")}%</dd>
      </dl>
      <p>{p.get("summary", "")}</p>
    </article>
    """)

html = TEMPLATE_PATH.read_text(encoding="utf-8")
html = html.replace(
    "__ANALYSIS_TIMESTAMP__",
    data.get("analysis_timestamp_bst", data.get("generated_bst", ""))
)
html = html.replace("__CORE_PAIR_CARDS__", "\n".join(cards))

OUTPUT_PATH.write_text(html, encoding="utf-8")
print(f"Wrote {OUTPUT_PATH}")
