# Live scenario fixtures (source of truth)

Committed raw inputs for automated live/interactive scenarios.
Runtime workdirs copy from here into `INTERPRETER_TEST_DATA_DIR`
(default copy target: `$INTERPRETER_TEST_DATA_DIR/live_scenario_fixtures/`).

## Layout

```
tests/fixtures/
  input/                 # raw inputs used by scenarios
    sales.json
    sales.csv
    editable.csv
    notes.txt
    brief.md
    sample.png           # 1x1 PNG
    sample.pdf           # minimal PDF
  expected/              # example expected outputs (documentation / soft checks)
    sales_from_json.csv
    summary_example.txt
    report_example.txt
  output/                # reserved; runtime writes go to INTERPRETER_TEST_DATA_DIR
```

## Env

```powershell
$env:INTERPRETER_TEST_DATA_DIR = "D:\tmp"   # workdir — never hardcode in tests
D:\henv\Scripts\python.exe scripts/run_live_scenarios.py
```

Reports (gitignored): `scratch/live_scenario_report.md` and `.html`.
