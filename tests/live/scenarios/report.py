# -*- coding: utf-8 -*-
"""Write master live-scenario reports (MD + HTML) under scratch/."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _esc(text: Any) -> str:
	return html.escape(str(text or ""), quote=True)


def write_master_reports(payload: dict[str, Any], scratch_dir: Path) -> dict[str, str]:
	"""Write ``live_scenario_report.md`` + ``.html`` (+ JSON) into scratch_dir."""
	scratch_dir.mkdir(parents=True, exist_ok=True)
	stamp = payload.get("run_id") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	summary = payload.get("summary") or {}
	rows = payload.get("rows") or []
	fixtures = payload.get("fixtures") or {}

	md_path = scratch_dir / "live_scenario_report.md"
	html_path = scratch_dir / "live_scenario_report.html"
	json_path = scratch_dir / "live_scenario_report.json"
	# Also keep stamped copies for sibling merge history
	stamped_json = scratch_dir / "live_scenario_reports" / f"live_scenarios_{stamp}.json"
	stamped_json.parent.mkdir(parents=True, exist_ok=True)

	json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
	stamped_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

	# --- Markdown ---
	md_lines = [
		f"# Live scenario report (`{stamp}`)",
		"",
		f"Generated: {payload.get('generated_at', '')}",
		"",
		"## Summary",
		"",
		f"- **PASS**={summary.get('PASS', 0)}",
		f"- **SKIP**={summary.get('SKIP', 0)}",
		f"- **FAIL**={summary.get('FAIL', 0)}",
		f"- **TOTAL**={summary.get('TOTAL', 0)}",
		"",
		"## Fixtures",
		"",
		f"- Repo fixtures: `{fixtures.get('repo_fixtures', 'tests/fixtures')}`",
		f"- Workdir: `{fixtures.get('fixture_dir', '')}`",
		f"- INTERPRETER_TEST_DATA_DIR base: `{fixtures.get('base', '')}`",
		"",
		"## Models",
		"",
		", ".join(f"`{m}`" for m in (payload.get("models") or [])) or "(none)",
		"",
		"## Scenarios",
		"",
		"| id | category | tier | kind | model | status | seconds | artifacts | notes |",
		"|---|---|---|---|---|---|---|---|---|",
	]
	for r in rows:
		arts = r.get("artifacts_checked") or []
		art_bits = []
		for a in arts:
			flag = "OK" if a.get("ok") else "MISS"
			art_bits.append(f"{Path(str(a.get('path',''))).name}:{flag}:{a.get('bytes',0)}b")
		art_s = "; ".join(art_bits) if art_bits else "-"
		detail = str(r.get("detail") or "").replace("|", "/").replace("\n", " ")[:160]
		md_lines.append(
			"| `{id}` | {cat} | {tier} | {kind} | `{model}` | **{status}** | {sec} | {arts} | {notes} |".format(
				id=r.get("id"),
				cat=r.get("category", ""),
				tier=r.get("tier", ""),
				kind=r.get("kind", ""),
				model=r.get("model", ""),
				status=r.get("status"),
				sec=r.get("seconds", 0),
				arts=art_s.replace("|", "/"),
				notes=detail,
			)
		)

	md_lines.extend(
		[
			"",
			"## Commands (how to re-run)",
			"",
			"```powershell",
			'$env:INTERPRETER_TEST_DATA_DIR = "D:\\tmp"',
			"$env:INTERPRETER_YES = \"1\"",
			"D:\\henv\\Scripts\\python.exe scripts/run_live_scenarios.py",
			"# Sibling tiers:",
			"D:\\henv\\Scripts\\python.exe scripts/run_live_scenarios.py --tier easy --merge-report",
			"D:\\henv\\Scripts\\python.exe scripts/run_live_scenarios.py --tier medium --merge-report",
			"```",
			"",
		]
	)
	md_path.write_text("\n".join(md_lines), encoding="utf-8")

	# --- HTML ---
	rows_html = []
	for r in rows:
		status = str(r.get("status") or "")
		cls = {"PASS": "pass", "FAIL": "fail", "SKIP": "skip"}.get(status, "")
		arts = r.get("artifacts_checked") or []
		art_html = "<br/>".join(
			_esc(f"{Path(str(a.get('path',''))).name}: {'OK' if a.get('ok') else 'MISS'} ({a.get('bytes',0)}b)")
			for a in arts
		) or "-"
		rows_html.append(
			"<tr class='{cls}'>"
			"<td><code>{id}</code></td>"
			"<td>{cat}</td><td>{tier}</td><td>{kind}</td>"
			"<td><code>{model}</code></td>"
			"<td class='status'>{status}</td>"
			"<td>{sec}</td>"
			"<td>{arts}</td>"
			"<td>{notes}</td>"
			"</tr>".format(
				cls=cls,
				id=_esc(r.get("id")),
				cat=_esc(r.get("category")),
				tier=_esc(r.get("tier")),
				kind=_esc(r.get("kind")),
				model=_esc(r.get("model")),
				status=_esc(status),
				sec=_esc(r.get("seconds")),
				arts=art_html,
				notes=_esc(str(r.get("detail") or "")[:300]),
			)
		)

	html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Live scenario report { _esc(stamp) }</title>
<style>
body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 2rem; background: #0f1419; color: #e7ecf1; }}
h1,h2 {{ color: #f5f7fa; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
th, td {{ border: 1px solid #2a3440; padding: 0.45rem 0.55rem; vertical-align: top; }}
th {{ background: #1a222c; text-align: left; }}
tr.pass td.status {{ color: #3dd68c; font-weight: 700; }}
tr.fail td.status {{ color: #ff6b6b; font-weight: 700; }}
tr.skip td.status {{ color: #f0c14a; font-weight: 700; }}
code {{ background: #1a222c; padding: 0.1rem 0.3rem; border-radius: 3px; }}
.summary span {{ margin-right: 1rem; }}
.pass-c {{ color: #3dd68c; }} .fail-c {{ color: #ff6b6b; }} .skip-c {{ color: #f0c14a; }}
</style>
</head>
<body>
<h1>Live scenario report <code>{_esc(stamp)}</code></h1>
<p>Generated: {_esc(payload.get('generated_at',''))}</p>
<div class="summary">
  <span class="pass-c">PASS={summary.get('PASS',0)}</span>
  <span class="skip-c">SKIP={summary.get('SKIP',0)}</span>
  <span class="fail-c">FAIL={summary.get('FAIL',0)}</span>
  <span>TOTAL={summary.get('TOTAL',0)}</span>
</div>
<h2>Fixtures</h2>
<ul>
  <li>Repo: <code>{_esc(fixtures.get('repo_fixtures','tests/fixtures'))}</code></li>
  <li>Workdir: <code>{_esc(fixtures.get('fixture_dir',''))}</code></li>
  <li>Base: <code>{_esc(fixtures.get('base',''))}</code></li>
</ul>
<h2>Scenarios</h2>
<table>
<thead>
<tr><th>id</th><th>category</th><th>tier</th><th>kind</th><th>model</th><th>status</th><th>sec</th><th>artifacts</th><th>notes</th></tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</body>
</html>
"""
	html_path.write_text(html_doc, encoding="utf-8")

	return {
		"md": str(md_path),
		"html": str(html_path),
		"json": str(json_path),
		"stamped_json": str(stamped_json),
	}


def merge_report_rows(
	existing: dict[str, Any] | None,
	incoming: dict[str, Any],
) -> dict[str, Any]:
	"""Merge sibling tier runs by scenario id (incoming wins on conflict)."""
	by_id: dict[str, dict[str, Any]] = {}
	if existing:
		for row in existing.get("rows") or []:
			by_id[str(row.get("id"))] = row
	for row in incoming.get("rows") or []:
		by_id[str(row.get("id"))] = row
	rows = list(by_id.values())
	summary = {
		"PASS": sum(1 for r in rows if r.get("status") == "PASS"),
		"SKIP": sum(1 for r in rows if r.get("status") == "SKIP"),
		"FAIL": sum(1 for r in rows if r.get("status") == "FAIL"),
		"TOTAL": len(rows),
	}
	models = list(
		dict.fromkeys(
			list((existing or {}).get("models") or []) + list(incoming.get("models") or [])
		)
	)
	return {
		"run_id": incoming.get("run_id") or (existing or {}).get("run_id"),
		"generated_at": datetime.now(timezone.utc).isoformat(),
		"fixtures": incoming.get("fixtures") or (existing or {}).get("fixtures") or {},
		"models": models,
		"summary": summary,
		"rows": rows,
		"merged": True,
	}
