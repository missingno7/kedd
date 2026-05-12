from __future__ import annotations

import subprocess
import sys

COMMANDS = [
    [sys.executable, "-m", "kegg.cli", "scan", "--data-dir", "game_data"],
    [sys.executable, "-m", "kegg.cli", "extract-images", "--data-dir", "game_data", "--out", "output/images"],
    [sys.executable, "-m", "kegg.cli", "analyze-bob", "--data-dir", "game_data", "--out", "output/bob"],
    [sys.executable, "-m", "kegg.cli", "extract-exe", "--exe", "game_data/KE.EXE", "--out", "output/exe"],
]

for command in COMMANDS:
    print("\n$", " ".join(command))
    subprocess.run(command, check=True)
