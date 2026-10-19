"""Ajoute la racine du dépôt au chemin des imports, pour que pytest trouve cleaning.py."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))