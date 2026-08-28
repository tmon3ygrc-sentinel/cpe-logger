You are operating within the DARKSWORD GRC Intelligence Platform. 
The pipeline code lives at C:\Work\GRC\darksword\notion_logger_v7.py.
Agent briefings are in C:\Work\GRC\darksword\.claude\
Session board/backlog: C:\Work\GRC\boards\BOARD.md — read FIRST each session.
Mount boards\, not darksword\ (darksword contains the protected Scheduled\
subfolder; any ancestor mount request will be refused).
Default role is ARCHITECT unless told otherwise.
Never push to git without confirmation.
Never modify .env files.
Current build: 8c399cb on main.
## Environment seams (recurring gotchas — check before assuming "it just works")

- **npm global install ≠ install-time setup ran.** `npm install -g <pkg>`
  reporting success only means the package files landed on disk. If the
  package has a `postinstall` script (common for CLIs shipping a native
  binary/shim), npm's `allow-scripts` gate can silently defer it — you'll
  see a `npm warn allow-scripts` line, easy to miss when scanning for the
  actual error. Result: CLI *looks* updated (new files present) but still
  runs old code until the script is explicitly approved.
  - Global installs CANNOT use `npm approve-scripts <pkg>` — that command
    only works inside a project with a package.json and hard-fails
    (EGLOBAL/ENOMATCH) against `-g`. npm's own warning message suggests a
    fix that doesn't work for this case — known npm bug, not user error.
  - Correct fix, scoped not blanket:
    `npm install -g --allow-scripts=<pkg> <pkg>`
  - Traced 2026-07-03: Claude Code CLI login hit a redirect-URI bug
    (`cocallback`) on a stale build; `npm install -g` alone didn't fix it
    because the postinstall got gated. Re-running with `--allow-scripts`
    scoped to the package fixed it clean.

- **This project's venv is `C:\Work\GRC\.venv` — always activate it
  explicitly before any `pip` command, never assume it's already active.**
  Other project venvs exist side-by-side on this machine (e.g. the old
  `GRC-OCEG` project). Running `pip install -r requirements.txt` while a
  *different* venv is activated silently installs into the wrong
  environment — no error, no warning, just a Darksword pipeline that's
  quietly missing whatever wasn't in that install. And since
  `requirements.txt` only ever gets updated when someone notices a gap, any
  package that was originally added ad hoc (`pip install <pkg>` without a
  matching `requirements.txt` commit) doesn't survive a rebuild — it just
  isn't declared, so the reinstall never restores it.
  - Before any `pip install -r requirements.txt`: confirm which venv is
    active first — check the prompt prefix, or run
    `python -c "import sys; print(sys.prefix)"` and verify it's
    `C:\Work\GRC\.venv`.
  - Explicit activation, every time, not "it was probably still active
    from earlier": `& C:\Work\GRC\.venv\Scripts\Activate.ps1`
  - Any manually `pip install`-ed package must get a matching
    `requirements.txt` commit in the same session — otherwise it's one
    rebuild away from silently vanishing.
  - Traced 2026-08-20: `torch` and `OTXv2` (and, separately, `bs4` on
    2026-08-14) went missing from `C:\Work\GRC\.venv` because a
    `pip install -r requirements.txt` was run on 2026-08-10 while
    `C:\Work\GRC-OCEG\.venv` was the active venv, against a
    `requirements.txt` that never declared those packages — they'd only
    ever been installed ad hoc. Full forensics: `boards\BOARD.md`,
    2026-08-20 OPS entries.

## Lab architecture

Phoenix Lab includes physical hardware, not only VMs — the existing
VM-based infra (`PHX-DC-01`, `pfSense-Core.vmx`, tracked/frozen via
Terraform per `boards\BOARD.md`'s 2026-07-21 reconciliation) is still
real and unchanged; this adds a physical node alongside it, it does not
replace it.

- **Current node: `phx-kali-01`** — Raspberry Pi, aarch64.
- **IP:** `10.0.40.153`, on the `HardOps-Lab-5G` network segment
  (`10.0.40.x`).
- **Auth:** SSH key-based (no password auth).
- **Management:** headless, administered from Windows via SSH.

