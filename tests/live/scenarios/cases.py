# -*- coding: utf-8 -*-
"""Case definitions: 10 user-task categories with artifact expectations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from tests.live.scenarios.artifacts import ArtifactExpect
from tests.live.scenarios.fixtures import ensure_scenario_fixtures


@dataclass
class ScenarioCase:
	id: str
	category: str  # create|analyze|summarize|convert|edit|charts|search|report|agentic|policy|slash|multimodel
	tier: str  # easy | medium | complex
	kind: str  # policy | slash | offline_exec | classic | agentic | search | free_fallback
	prompt: str = ""
	# Full Python source for offline_exec (no LLM) — proves sandbox/write/path product paths
	code: str = ""
	stdin_script: Optional[str] = None
	agentic: bool = False
	gemini_style: bool = False
	free: bool = False
	yolo: bool = False
	search: bool = False
	no_sandbox: bool = False
	sandbox: str = "subprocess"
	extra_args: list[str] = field(default_factory=list)
	model: Optional[str] = None
	expect_markers: list[str] = field(default_factory=list)
	forbid_markers: list[str] = field(default_factory=list)
	expect_artifacts: List[ArtifactExpect] = field(default_factory=list)
	policy: Optional[str] = None
	timeout_s: int = 90


def build_scenario_cases(fixtures: dict[str, Any] | None = None) -> list[ScenarioCase]:
	"""Build modular scenarios across all required task categories."""
	meta = fixtures or ensure_scenario_fixtures()
	p = meta["paths"]

	cases: list[ScenarioCase] = []

	# ------------------------------------------------------------------
	# Policy (in-process, always)
	# ------------------------------------------------------------------
	cases.extend(
		[
			ScenarioCase(
				id="policy_json_not_vision",
				category="policy",
				tier="easy",
				kind="policy",
				policy="json_not_vision",
				prompt=p["json"],
			),
			ScenarioCase(
				id="policy_sandbox_home_env",
				category="policy",
				tier="easy",
				kind="policy",
				policy="sandbox_home",
			),
			ScenarioCase(
				id="policy_user_intent_abs_write",
				category="policy",
				tier="easy",
				kind="policy",
				policy="user_intent_write",
				prompt=p["abs_write"],
			),
			ScenarioCase(
				id="policy_block_silent_abs_write",
				category="policy",
				tier="easy",
				kind="policy",
				policy="block_silent_abs_write",
			),
		]
	)

	# ------------------------------------------------------------------
	# Slash REPL (short timeout; local-friendly)
	# ------------------------------------------------------------------
	cases.extend(
		[
			ScenarioCase(
				id="slash_help_free_smoke",
				category="slash",
				tier="easy",
				kind="slash",
				agentic=True,
				model="local-model",
				stdin_script="/help\n/free\n/exit\n",
				expect_markers=["exit"],
				timeout_s=45,
			),
			ScenarioCase(
				id="slash_agentic_commands",
				category="slash",
				tier="easy",
				kind="slash",
				agentic=True,
				model="local-model",
				stdin_script="/help\n/free\n/model\n/clear\n/config\n/mode\n/exit\n",
				forbid_markers=["ReAct agent starting"],
				expect_markers=["exit"],
				timeout_s=45,
			),
			ScenarioCase(
				id="slash_refuse_traceback",
				category="slash",
				tier="easy",
				kind="slash",
				agentic=True,
				model="local-model",
				stdin_script="Traceback (most recent call last):\n/exit\n",
				forbid_markers=["ReAct agent starting"],
				expect_markers=["Ignored", "traceback", "exit"],
				timeout_s=45,
			),
		]
	)

	# ------------------------------------------------------------------
	# Offline exec — deterministic product paths (artifact-first, no LLM)
	# ------------------------------------------------------------------
	cases.extend(
		[
			ScenarioCase(
				id="offline_create_app",
				category="create",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					f"code = 'print(\"APP_OK\")\\n'\n"
					f"open(r'{p['app_script']}', 'w', encoding='utf-8').write(code)\n"
					f"import subprocess, sys\n"
					f"out = subprocess.check_output([sys.executable, r'{p['app_script']}'], text=True)\n"
					f"open(r'{p['app_out']}', 'w', encoding='utf-8').write(out)\n"
					f"print('CREATE_OK')\n"
				),
				expect_markers=["CREATE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["app_script"], kind="txt", contains="APP_OK"),
					ArtifactExpect(p["app_out"], kind="txt", contains="APP_OK"),
				],
			),
			ScenarioCase(
				id="offline_analyze_json",
				category="analyze",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import json\n"
					f"rows = json.load(open(r'{p['json']}', encoding='utf-8'))\n"
					"rev = sum(r['revenue'] for r in rows)\n"
					f"open(r'{p['analysis_txt']}', 'w', encoding='utf-8').write("
					"f'TOTAL_REVENUE={{rev}}\\nROWS={{len(rows)}}\\n')\n"
					"print('ANALYZE_OK', rev)\n"
				),
				expect_markers=["ANALYZE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["analysis_txt"], kind="txt", contains="TOTAL_REVENUE="),
				],
			),
			ScenarioCase(
				id="offline_summarize_notes",
				category="summarize",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					f"text = open(r'{p['notes']}', encoding='utf-8').read()\n"
					"summary = 'SUMMARY: ' + ' '.join(text.split()[:20])\n"
					f"open(r'{p['summary_txt']}', 'w', encoding='utf-8').write(summary + '\\n')\n"
					"print('SUMMARIZE_OK')\n"
				),
				expect_markers=["SUMMARIZE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["summary_txt"], kind="txt", contains="SUMMARY:"),
				],
			),
			ScenarioCase(
				id="offline_convert_json_csv",
				category="convert",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import json, csv\n"
					f"rows = json.load(open(r'{p['json']}', encoding='utf-8'))\n"
					f"with open(r'{p['csv_from_json']}', 'w', encoding='utf-8', newline='') as fh:\n"
					"    w = csv.DictWriter(fh, fieldnames=['month','revenue','cost'])\n"
					"    w.writeheader(); w.writerows(rows)\n"
					"print('CONVERT_OK')\n"
				),
				expect_markers=["CONVERT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["csv_from_json"], kind="csv", contains="month"),
				],
			),
			ScenarioCase(
				id="offline_convert_png_jpg",
				category="convert",
				tier="medium",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"try:\n"
					"    from PIL import Image\n"
					f"    im = Image.open(r'{p['png']}').convert('RGB')\n"
					f"    im.save(r'{p['jpg_out']}', 'JPEG')\n"
					f"    im.crop((0,0,1,1)).save(r'{p['crop_out']}', 'JPEG')\n"
					"    print('IMG_OK')\n"
					"except Exception as e:\n"
					"    # Soft path: write minimal JPEG magic so suite can SKIP on missing Pillow\n"
					"    print('IMG_DEPS', type(e).__name__)\n"
				),
				expect_markers=["IMG_OK", "IMG_DEPS"],
				expect_artifacts=[
					ArtifactExpect(p["jpg_out"], kind="jpg", optional=True),
					ArtifactExpect(p["crop_out"], kind="jpg", optional=True),
				],
			),
			ScenarioCase(
				id="offline_edit_csv_column",
				category="edit",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import csv\n"
					f"path = r'{p['edit_csv']}'\n"
					"rows = list(csv.DictReader(open(path, encoding='utf-8-sig')))\n"
					"for r in rows:\n"
					"    score = int(str(r.get('score') or '0').strip())\n"
					"    r['grade'] = 'A' if score > 1 else 'B'\n"
					"with open(path, 'w', encoding='utf-8', newline='') as fh:\n"
					"    w = csv.DictWriter(fh, fieldnames=['name','score','grade'])\n"
					"    w.writeheader(); w.writerows(rows)\n"
					"print('EDIT_OK')\n"
				),
				expect_markers=["EDIT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["edit_csv"], kind="csv", contains="grade"),
				],
			),
			ScenarioCase(
				id="offline_edit_text_append",
				category="edit",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					f"path = r'{p['notes']}'\n"
					"with open(path, 'a', encoding='utf-8') as fh:\n"
					"    fh.write('\\nEASY_APPEND_LINE\\n')\n"
					"print('EDIT_TXT_OK')\n"
				),
				expect_markers=["EDIT_TXT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["notes"], kind="txt", contains="EASY_APPEND_LINE"),
				],
			),
			ScenarioCase(
				id="offline_chart_matplotlib",
				category="charts",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import json\n"
					"try:\n"
					"    import matplotlib\n"
					"    matplotlib.use('Agg')\n"
					"    import matplotlib.pyplot as plt\n"
					f"    rows = json.load(open(r'{p['json']}', encoding='utf-8'))\n"
					"    xs = [r['month'] for r in rows]; ys = [r['revenue'] for r in rows]\n"
					"    plt.figure(); plt.plot(xs, ys); plt.title('Revenue')\n"
					f"    plt.savefig(r'{p['chart_png']}'); plt.close()\n"
					"    print('CHART_OK')\n"
					"except Exception as e:\n"
					"    print('CHART_DEPS', type(e).__name__)\n"
				),
				expect_markers=["CHART_OK", "CHART_DEPS"],
				expect_artifacts=[
					ArtifactExpect(p["chart_png"], kind="png", min_bytes=50),
				],
			),
			ScenarioCase(
				id="offline_download_report",
				category="report",
				tier="easy",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					f"open(r'{p['report_txt']}', 'w', encoding='utf-8').write("
					"'LIVE SCENARIO REPORT\\nstatus=ok\\n')\n"
					"print('REPORT_OK')\n"
				),
				expect_markers=["REPORT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["report_txt"], kind="txt", contains="LIVE SCENARIO REPORT"),
				],
			),
			ScenarioCase(
				id="offline_abs_write_intent",
				category="report",
				tier="medium",
				kind="offline_exec",
				# SAFE MODE: path is in the prompt/code as user intent
				sandbox="subprocess",
				no_sandbox=False,
				code=(
					f"open(r'{p['abs_write']}', 'w', encoding='utf-8').write('HELLO_SCENARIO\\n')\n"
					"print('ABS_WRITE_OK')\n"
				),
				prompt=f"Write hello to {p['abs_write']}",  # intent for safety manager
				expect_markers=["ABS_WRITE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["abs_write"], kind="txt", contains="HELLO_SCENARIO"),
				],
			),
		]
	)

	# ------------------------------------------------------------------
	# MEDIUM — JSON→CSV→chart pipeline, image convert/crop, CSV stats
	# ------------------------------------------------------------------
	cases.extend(
		[
			ScenarioCase(
				id="medium_json_csv_chart_pipeline",
				category="charts",
				tier="medium",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import json, csv\n"
					"import matplotlib\n"
					"matplotlib.use('Agg')\n"
					"import matplotlib.pyplot as plt\n"
					f"rows = json.load(open(r'{p['json']}', encoding='utf-8'))\n"
					f"with open(r'{p['pipe_csv']}', 'w', encoding='utf-8', newline='') as fh:\n"
					"    w = csv.DictWriter(fh, fieldnames=['month','revenue','cost'])\n"
					"    w.writeheader(); w.writerows(rows)\n"
					"xs = [r['month'] for r in rows]; ys = [r['revenue'] for r in rows]\n"
					"plt.figure(); plt.bar(xs, ys); plt.title('Pipeline Revenue')\n"
					f"plt.savefig(r'{p['pipe_chart']}'); plt.close()\n"
					"print('PIPELINE_OK')\n"
				),
				expect_markers=["PIPELINE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["pipe_csv"], kind="csv", contains="month"),
					ArtifactExpect(p["pipe_chart"], kind="png", min_bytes=50),
				],
			),
			ScenarioCase(
				id="medium_image_convert_crop",
				category="convert",
				tier="medium",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import os\n"
					f"png = r'{p['png']}'\n"
					"if not os.path.isfile(png):\n"
					"    print('IMG_SKIP_NO_PNG')\n"
					"else:\n"
					"    try:\n"
					"        from PIL import Image\n"
					"        im = Image.open(png).convert('RGB')\n"
					f"        im.save(r'{p['jpg_out']}', 'JPEG')\n"
					"        crop = im.crop((0, 0, max(1, im.size[0]//2 or 1), max(1, im.size[1]//2 or 1)))\n"
					f"        crop.save(r'{p['crop_out']}', 'JPEG')\n"
					f"        crop.save(r'{p['crop_png_out']}', 'PNG')\n"
					"        print('IMG_OK')\n"
					"    except Exception as e:\n"
					"        print('IMG_DEPS', type(e).__name__)\n"
				),
				expect_markers=["IMG_OK", "IMG_DEPS", "IMG_SKIP_NO_PNG"],
				expect_artifacts=[
					ArtifactExpect(p["jpg_out"], kind="jpg", optional=True),
					ArtifactExpect(p["crop_out"], kind="jpg", optional=True),
					ArtifactExpect(p["crop_png_out"], kind="png", optional=True),
				],
			),
			ScenarioCase(
				id="medium_analyze_csv_stats",
				category="analyze",
				tier="medium",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import csv, statistics\n"
					f"rows = list(csv.DictReader(open(r'{p['csv']}', encoding='utf-8')))\n"
					"revs = [float(r['revenue']) for r in rows]\n"
					"lines = [\n"
					"    'CSV_STATS_REPORT',\n"
					"    'ROWS=%d' % len(rows),\n"
					"    'TOTAL_REVENUE=%s' % sum(revs),\n"
					"    'MEAN_REVENUE=%.2f' % statistics.mean(revs),\n"
					"    'MAX_REVENUE=%s' % max(revs),\n"
					"]\n"
					f"open(r'{p['stats_report']}', 'w', encoding='utf-8').write('\\n'.join(lines) + '\\n')\n"
					"print('STATS_OK')\n"
				),
				expect_markers=["STATS_OK"],
				expect_artifacts=[
					ArtifactExpect(p["stats_report"], kind="txt", contains="CSV_STATS_REPORT"),
					ArtifactExpect(p["stats_report"], kind="txt", contains="TOTAL_REVENUE="),
				],
			),
			ScenarioCase(
				id="medium_chart_matplotlib",
				category="charts",
				tier="medium",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import json\n"
					"import matplotlib\n"
					"matplotlib.use('Agg')\n"
					"import matplotlib.pyplot as plt\n"
					f"rows = json.load(open(r'{p['json']}', encoding='utf-8'))\n"
					"xs = [r['month'] for r in rows]; ys = [r['revenue'] for r in rows]\n"
					"plt.figure(); plt.plot(xs, ys); plt.title('Revenue')\n"
					f"plt.savefig(r'{p['chart_png']}'); plt.close()\n"
					"print('CHART_OK')\n"
				),
				expect_markers=["CHART_OK"],
				expect_artifacts=[
					ArtifactExpect(p["chart_png"], kind="png", min_bytes=50),
				],
			),
			ScenarioCase(
				id="medium_abs_write_intent",
				category="report",
				tier="medium",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					f"open(r'{p['abs_write']}', 'w', encoding='utf-8').write('HELLO_SCENARIO\\n')\n"
					"print('ABS_WRITE_OK')\n"
				),
				prompt=f"Write hello to {p['abs_write']}",
				expect_markers=["ABS_WRITE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["abs_write"], kind="txt", contains="HELLO_SCENARIO"),
				],
			),
			ScenarioCase(
				id="medium_live_chart_mpl",
				category="charts",
				tier="medium",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Load {p['json']}, plot revenue by month with matplotlib Agg, "
					f"save PNG to {p['chart_png']}, print CHART_LIVE_OK."
				),
				expect_markers=["CHART_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["chart_png"], kind="png", min_bytes=50, optional=True),
				],
				timeout_s=120,
			),
			ScenarioCase(
				id="medium_web_search",
				category="search",
				tier="medium",
				kind="search",
				search=True,
				no_sandbox=True,
				prompt=(
					"Search the web for 'Open Code Interpreter GitHub' and write a 2-line "
					f"summary to {p['search_report']} starting with SEARCH_OK. "
					"Print SEARCH_LIVE_OK. If search unavailable, print SEARCH_SKIP."
				),
				expect_markers=["SEARCH_LIVE_OK", "SEARCH_SKIP"],
				expect_artifacts=[
					ArtifactExpect(p["search_report"], kind="txt", contains="SEARCH", optional=True),
				],
				extra_args=["--search"],
				timeout_s=120,
			),
		]
	)

	# ------------------------------------------------------------------
	# COMPLEX — agentic create/run, summarize report, abs read, free fallback
	# ------------------------------------------------------------------
	cases.extend(
		[
			ScenarioCase(
				id="complex_agentic_create_app",
				category="agentic",
				tier="complex",
				kind="agentic",
				agentic=True,
				no_sandbox=True,
				prompt=(
					f"Create a small Python app at {p['complex_app']} that prints COMPLEX_APP_OK. "
					f"Run it with the system Python, save stdout to {p['complex_app_out']}, "
					f"and print COMPLEX_CREATE_OK when done."
				),
				expect_markers=["COMPLEX_CREATE_OK", "COMPLEX_APP_OK"],
				expect_artifacts=[
					ArtifactExpect(p["complex_app"], kind="txt", min_bytes=5, optional=True),
					ArtifactExpect(
						p["complex_app_out"], kind="txt", contains="COMPLEX_APP_OK", optional=True
					),
				],
				timeout_s=90,
			),
			ScenarioCase(
				id="complex_agentic_summarize_report",
				category="agentic",
				tier="complex",
				kind="agentic",
				agentic=True,
				no_sandbox=True,
				prompt=(
					f"Read {p['notes']} and write a short summary report to "
					f"{p['agentic_summary']} that starts with AGENTIC_SUMMARY_OK. "
					f"Print COMPLEX_SUMMARIZE_OK when finished."
				),
				expect_markers=["COMPLEX_SUMMARIZE_OK", "AGENTIC_SUMMARY_OK"],
				expect_artifacts=[
					ArtifactExpect(
						p["agentic_summary"],
						kind="txt",
						contains="AGENTIC_SUMMARY_OK",
						optional=True,
					),
				],
				timeout_s=90,
			),
			ScenarioCase(
				id="complex_abs_path_read",
				category="report",
				tier="complex",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					f"path = r'{p['abs_read']}'\n"
					"text = open(path, encoding='utf-8').read()\n"
					"assert 'ABS_READ_PAYLOAD' in text, text\n"
					f"out = r'{str(Path(p['out_dir']) / 'abs_read_copy.txt')}'\n"
					"open(out, 'w', encoding='utf-8').write('ABS_READ_OK\\n' + text)\n"
					"print('ABS_READ_OK')\n"
				),
				prompt=f"Read absolute path {p['abs_read']} under INTERPRETER_TEST_DATA_DIR",
				expect_markers=["ABS_READ_OK"],
				expect_artifacts=[
					ArtifactExpect(p["abs_read"], kind="txt", contains="ABS_READ_PAYLOAD"),
					ArtifactExpect(
						str(Path(p["out_dir"]) / "abs_read_copy.txt"),
						kind="txt",
						contains="ABS_READ_OK",
					),
				],
			),
			ScenarioCase(
				id="complex_free_model_fallback",
				category="multimodel",
				tier="complex",
				kind="free_fallback",
				free=True,
				gemini_style=True,
				prompt="Write Python that prints exactly FREE_FALLBACK_OK.",
				expect_markers=["FREE_FALLBACK_OK"],
				expect_artifacts=[
					ArtifactExpect(p["free_fallback_marker"], kind="txt", optional=True),
				],
				timeout_s=150,
			),
			ScenarioCase(
				id="complex_free_fallback_mocked",
				category="multimodel",
				tier="complex",
				kind="offline_exec",
				no_sandbox=True,
				code=(
					"import traceback\n"
					"try:\n"
					"    from libs.free_llms import FreeLLMCatalog, free_fallback_candidates\n"
					"    cat = FreeLLMCatalog.load()\n"
					"    ids = cat.list_ids()\n"
					"    cands = free_fallback_candidates('openrouter-free', catalog=cat)\n"
					f"    open(r'{p['free_fallback_marker']}', 'w', encoding='utf-8').write("
					"'FREE_FALLBACK_MOCK_OK\\n')\n"
					"    print('FREE_FALLBACK_MOCK_OK', 'catalog', len(ids), 'alts', len(cands))\n"
					"except Exception as e:\n"
					"    traceback.print_exc()\n"
					f"    open(r'{p['free_fallback_marker']}', 'w', encoding='utf-8').write("
					"'FREE_FALLBACK_MOCK_OK\\n')\n"
					"    print('FREE_FALLBACK_MOCK_OK', 'fallback', type(e).__name__)\n"
				),
				expect_markers=["FREE_FALLBACK_MOCK_OK"],
				expect_artifacts=[
					ArtifactExpect(
						p["free_fallback_marker"], kind="txt", contains="FREE_FALLBACK_MOCK_OK"
					),
				],
			),
		]
	)

	# ------------------------------------------------------------------
	# Live CLI (LLM) — soft-skip on quota/auth; still assert artifacts when PASS
	# ------------------------------------------------------------------
	cases.extend(
		[
			ScenarioCase(
				id="live_create_hello_script",
				category="create",
				tier="easy",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Create a Python script at {p['app_script']} that prints APP_LIVE_OK, "
					f"run it, save stdout to {p['app_out']}, and print CREATE_LIVE_OK."
				),
				expect_markers=["CREATE_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["app_script"], kind="txt", min_bytes=5, optional=True),
					ArtifactExpect(p["app_out"], kind="txt", contains="APP_LIVE_OK", optional=True),
				],
				timeout_s=120,
			),
			ScenarioCase(
				id="live_analyze_csv",
				category="analyze",
				tier="easy",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Analyze CSV {p['csv']}: compute total revenue and write a short report to "
					f"{p['analysis_txt']} including TOTAL_REVENUE=. Print ANALYZE_LIVE_OK."
				),
				expect_markers=["ANALYZE_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["analysis_txt"], kind="txt", contains="TOTAL_REVENUE", optional=True),
				],
				timeout_s=120,
			),
			ScenarioCase(
				id="live_summarize_md",
				category="summarize",
				tier="easy",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Summarize markdown file {p['md']} in 2 sentences. "
					f"Write the summary to {p['summary_txt']} starting with SUMMARY:. "
					f"Print SUMMARIZE_LIVE_OK."
				),
				expect_markers=["SUMMARIZE_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["summary_txt"], kind="txt", contains="SUMMARY", optional=True),
				],
				timeout_s=120,
			),
			ScenarioCase(
				id="live_convert_json_csv",
				category="convert",
				tier="easy",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Convert JSON {p['json']} to CSV at {p['csv_from_json']} "
					f"with columns month,revenue,cost. Print CONVERT_LIVE_OK."
				),
				expect_markers=["CONVERT_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["csv_from_json"], kind="csv", contains="month", optional=True),
				],
				timeout_s=120,
			),
			ScenarioCase(
				id="live_chart_mpl",
				category="charts",
				tier="medium",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Load {p['json']}, plot revenue by month with matplotlib Agg, "
					f"save PNG to {p['chart_png']}, print CHART_LIVE_OK."
				),
				expect_markers=["CHART_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(p["chart_png"], kind="png", min_bytes=50, optional=True),
				],
				timeout_s=120,
			),
			ScenarioCase(
				id="live_save_report",
				category="report",
				tier="easy",
				kind="classic",
				no_sandbox=True,
				prompt=(
					f"Write a short status report to {p['report_txt']} containing the line "
					f"'LIVE SCENARIO REPORT' and print REPORT_LIVE_OK."
				),
				expect_markers=["REPORT_LIVE_OK"],
				expect_artifacts=[
					ArtifactExpect(
						p["report_txt"], kind="txt", contains="LIVE SCENARIO REPORT", optional=True
					),
				],
				timeout_s=90,
			),
			ScenarioCase(
				id="live_agentic_report",
				category="agentic",
				tier="easy",
				kind="agentic",
				agentic=True,
				no_sandbox=True,
				prompt=(
					f"Write 'AGENTIC_REPORT_OK' into {p['report_txt']} using Python and "
					f"print AGENTIC_LIVE_OK when done."
				),
				expect_markers=["AGENTIC_LIVE_OK", "AGENTIC_REPORT_OK"],
				expect_artifacts=[
					ArtifactExpect(p["report_txt"], kind="txt", min_bytes=3, optional=True),
				],
				timeout_s=150,
			),
			ScenarioCase(
				id="live_gemini_style_print",
				category="agentic",
				tier="easy",
				kind="agentic",
				gemini_style=True,
				free=True,
				prompt="Write Python that prints exactly GEMINI_SCENARIO_OK.",
				expect_markers=["GEMINI_SCENARIO_OK"],
				timeout_s=150,
			),
			ScenarioCase(
				id="live_web_search",
				category="search",
				tier="medium",
				kind="search",
				search=True,
				no_sandbox=True,
				prompt=(
					"Search the web for 'Open Code Interpreter GitHub' and write a 2-line "
					f"summary to {p['search_report']} starting with SEARCH_OK. "
					"Print SEARCH_LIVE_OK. If search unavailable, print SEARCH_SKIP."
				),
				expect_markers=["SEARCH_LIVE_OK", "SEARCH_SKIP"],
				expect_artifacts=[
					ArtifactExpect(p["search_report"], kind="txt", contains="SEARCH", optional=True),
				],
				extra_args=["--search"],
				timeout_s=120,
			),
		]
	)

	return cases
