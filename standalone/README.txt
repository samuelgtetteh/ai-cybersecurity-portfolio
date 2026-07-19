RegMap - Standalone
===================

A self-contained copy of the RegMap security platform. Everything it needs is in
this folder: the application code (app/backend), the trained models
(app/models), the reference data (app/data), and the compliance toolkit
(app/control-advisor). No Docker required.

HOW TO RUN
----------
Windows:        double-click  run.cmd
Linux / macOS:  open a terminal in this folder and run:  ./run.sh
                (first time only:  chmod +x run.sh)

What happens on the FIRST run:
  1. The launcher detects your operating system.
  2. It creates a private virtual environment in .venv (kept inside this folder).
  3. It installs the required Python packages (a few minutes, one time).
  4. It starts the API and, on Windows/macOS, opens your browser.

Every later run just starts the API immediately.

Then open:  http://localhost:8000
Others on your network can reach it at:  http://<this-machine-ip>:8000

REQUIREMENTS
------------
  * Python 3.10+ (3.11 or 3.12 recommended). If it's missing, the launcher tells
    you where to get it.
  * nmap is optional (enables the richer scan engine). Without it, the built-in
    TCP scanner still works.
      Debian/Ubuntu:  sudo apt install -y nmap
      Windows:        https://nmap.org/download.html

USEFUL
------
  * Change the port:   set REGMAP_PORT=8600   (Windows)  /  REGMAP_PORT=8600 ./run.sh
  * Data (verdicts):   stored in verdicts.db in this folder.
  * To reset the environment, delete the .venv folder; it rebuilds on next run.

NOTES
-----
  * The conversational interview uses a local Qwen model that is NOT bundled
    (size). Without it, the interview falls back to standard questions; the rest
    of the platform is unaffected. To enable it, place the model directory at
    app/models/qwen2.5-1.5b-instruct.
  * Only scan networks you own or are explicitly authorized to test.
