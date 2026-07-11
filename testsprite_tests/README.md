# TestSprite Backend Suite — Open Code Interpreter

This folder holds **backend / CLI integration tests** for TestSprite GitHub App Pre-Check.

This project is a **command-line tool only** (no website, no frontend UI).
`tmp/config.json` sets `"type": "backend"`.

## Cases
| ID | Focus |
|---|---|
| TC001 | CLI `--help` / `--version` |
| TC002 | Modular backend imports |
| TC003 | Safety manager SAFE-mode blocking |
| TC004 | Agent pipeline happy path (mocked LLM) |
| TC005 | SafetyGuard blocks before execution |
| TC006 | Full `unittest` suite regression |

## Run locally
```bash
source .venv/bin/activate
python -m unittest discover -s testsprite_tests -p 'TC*.py' -v
```
