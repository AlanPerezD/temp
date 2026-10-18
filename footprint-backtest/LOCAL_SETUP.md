# Moving this project to Claude Code on your computer

## What moves and what does not
| Item | Moves with `--teleport`? | How you get it |
|---|---|---|
| Full conversation history | Yes | `claude --teleport` |
| Code, docs, results, your 21 chart labels (branch `ccr-58e4f006-txlukd`) | Yes (git) | `git clone` + checkout |
| Market data (874 MB, paid, git-ignored) | **No** | `python rebuild_data.py` (costs Databento credit) |
| Databento API key | **No** | new key in `footprint-backtest/.env` |
| Python packages | **No** | `pip install -r requirements.txt` |
| Cloud-only extras (artifact tools, stop hook, MCP connectors) | No | not needed locally |

## Steps (Windows PowerShell, Mac or Linux)
1. **Install Claude Code** and sign in with the SAME claude.ai account: https://code.claude.com/docs/en/quickstart
   then `claude auth login`.
2. **Clone the repo and get the branch**
   ```
   git clone https://github.com/AlanPerezD/temp.git
   cd temp
   git checkout ccr-58e4f006-txlukd
   ```
3. **Pull the cloud session into your terminal** (needs a clean git state; run from inside the clone):
   ```
   claude --teleport session_01W2tFiBsJwzP55dv72YfFKH
   ```
   Alternatives: `claude --teleport` (pick from a list), `/teleport` inside Claude Code, or on claude.ai/code open this
   session and choose **Open in > Terminal** to copy the command. You get the whole conversation; new work then stays
   local (use `/remote-control` if you want to keep steering from your phone).
4. **Python environment** (Python 3.12 or 3.13):
   ```
   cd footprint-backtest
   python -m venv .venv
   .venv\Scripts\activate          # Windows;  Mac/Linux: source .venv/bin/activate
   pip install -r requirements.txt  # if something breaks: pip install -r requirements.lock.txt
   ```
5. **New Databento key**: https://databento.com/portal/keys. Revoke the key pasted in the old chat. Then create
   `footprint-backtest/.env` containing one line: `DATABENTO_API_KEY=db-...` (the file is git-ignored; never commit it).
6. **Rebuild only the data you need** (shows the plan and cost first; nothing is bought until you add `--download`):
   ```
   python rebuild_data.py --tier nq               # plan: ~$13, the FTMO Nasdaq edge
   python rebuild_data.py --tier nq --download
   python rebuild_data.py --free --download       # free: EIA inventories, CFTC COT, FRED OVX
   ```
   `--tier oil` (~$21, the oil research) and `--tier mcl` (~$5, tick/footprint work) are optional.
7. **Check it works** (no data needed): `python -m unittest discover -p "test_*.py"`. With the nq tier:
   `python index_ftmo_sim.py NQ` should show the 15:00 ET results in `strategies/FTMO_ADAPTATION_nasdaq_close_momentum.md`.

## Good to know
- The repo is **public** on GitHub: everything committed (code, `strategies/` write-ups, `labels.csv`, the root project's
  CSVs) is visible to anyone. Make it private in GitHub > Settings if you want. Market data is never committed.
- `footprint-backtest/CLAUDE.md` is the project memory Claude Code reads automatically (rules, map, findings).
- The data is not in git on purpose: Databento's terms do not allow redistributing it, and the repo is public.
