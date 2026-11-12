"""Write hearth-live-session.html from the measured JSON files. No new numbers."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "bench" / "live" / "2026-11-12.json",
    ROOT / "bench" / "live" / "2026-11-12-tools.json",
    ROOT / "bench" / "live" / "2026-11-12-broad.json",
)
TARGET = ROOT / "hearth-live-session.html"


def _bars(turns: list[dict], width: int = 640, height: int = 160) -> str:
    measured = [turn for turn in turns if not turn.get("error")]
    peak = max(
        (
            int(turn.get("read") or 0)
            + int(turn.get("write") or 0)
            + int(turn.get("uncached") or 0)
            for turn in measured
        ),
        default=1,
    )
    slot = width / max(len(measured), 1)
    parts = []
    for index, turn in enumerate(measured):
        read = int(turn.get("read") or 0)
        bar_h = 0 if peak == 0 else round(read / peak * (height - 28))
        x = round(index * slot + 8)
        y = height - 24 - bar_h
        color = "#9a3412" if turn.get("kind") == "break" else "#1d4e49"
        if bar_h == 0:
            bar_h = 4
            y = height - 24 - bar_h
        parts.append(
            f'<rect x="{x}" y="{y}" width="{max(int(slot) - 16, 8)}" height="{bar_h}" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x}" y="{height - 8}" font-size="11" fill="#444">{turn.get("turn")}</text>'
        )
    return f'<svg viewBox="0 0 {width} {height}" width="100%" role="img">{"".join(parts)}</svg>'


def _session_cards(data: dict) -> str:
    note = html.escape(str(data.get("chart_note") or ""))
    cards = []
    for session in data["sessions"]:
        summary = session["summary"]
        scale = session["per_1000_sessions"]
        ratio = float(summary["session_ratio"]) * 100
        cards.append(
            f"""
            <section>
              <h2>{html.escape(session["title"])}</h2>
              <p class="model">{html.escape(session["model"])}</p>
              <p class="big">{ratio:.1f}% <span>of the uncached bill</span></p>
              <p>This session cost ${html.escape(summary["actual_usd"])}. The same tokens with no cache would have cost ${html.escape(summary["baseline_usd"])}. Saved ${html.escape(summary["saved_usd"])}.</p>
              <h3>Cached input tokens on each turn</h3>
              {_bars(session["turns"])}
              <p class="note">{note}</p>
              <p>One thousand sessions at this measured rate would cost ${html.escape(scale["actual_usd"])} instead of ${html.escape(scale["baseline_usd"])}, a saving of ${html.escape(scale["saved_usd"])}. That line is the measured session multiplied by 1,000. It is not another run.</p>
            </section>
            """
        )
    return "".join(cards)


def main() -> None:
    blocks = []
    for source in SOURCES:
        data = json.loads(source.read_text())
        origin = html.escape(str(data.get("cache_origin") or ""))
        origin_html = f"<p>{origin}</p>" if origin else ""
        blocks.append(
            f"""
            <section>
              <h2>Run {html.escape(str(data["run_id"]))}</h2>
              <p>{html.escape(str(data["case"]))}</p>
              {origin_html}
              <p class="note">Raw counts: <code>{html.escape(source.name)}</code>. Dollars come from those counts and the sourced price list.</p>
            </section>
            {_session_cards(data)}
            """
        )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Hearth live sessions, 12 Nov 2026</title>
<style>
  body {{ margin: 0; background: #f4f1ea; color: #1c1917; font: 18px/1.5 Georgia, serif; }}
  main {{ max-width: 820px; margin: 0 auto; padding: 48px 24px 80px; }}
  h1 {{ font-size: 40px; line-height: 1.15; margin-bottom: 8px; }}
  h2 {{ margin-bottom: 0; }}
  .model {{ color: #57534e; margin-top: 4px; }}
  .big {{ font-size: 42px; margin: 12px 0; }}
  .big span {{ font-size: 18px; }}
  section {{ background: white; border: 1px solid #e7e5e4; padding: 24px; margin: 20px 0; }}
  .note {{ color: #57534e; font-size: 15px; }}
  rect {{ rx: 2; }}
</style>
</head>
<body>
<main>
  <h1>Measured sessions on the models that cached.</h1>
  <p>12 Nov 2026. One session asks questions. One session calls tools. One session uses the models that answered under a $5 cap. Every dollar below is computed from the provider's token counts and the sourced price list.</p>
  {"".join(blocks)}
  <section>
    <h2>What this page does not say</h2>
    <p>gpt-oss is not here. Earlier calls returned no cache fields. Claude is not here. This Bedrock account still asks for the Anthropic use-case form. GPT-5.4, GPT-5.5, GPT-5.6 Luna, Grok 4.6, and Grok 4.7 returned HTTP 403 on this account. There is no direct OpenAI key. Gemini stopped on turn 7 of the question session because the key is on the free-tier quota. The older 42% figure in <code>docs/REPORT.md</code> is the offline simulator, not this bill.</p>
  </section>
</main>
</body>
</html>
"""
    TARGET.write_text(page)


if __name__ == "__main__":
    main()
