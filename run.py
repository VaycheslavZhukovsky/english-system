#!/usr/bin/env python3
"""Entry point: python run.py [command]"""
import sys
from pathlib import Path

# Стрелки и редактирование ввода в терминале (Unix)
try:
    import readline  # noqa: F401
except ImportError:
    pass

# Fix stdin encoding only if needed
if hasattr(sys.stdin, "reconfigure"):
    try:
        enc = sys.stdin.encoding or "utf-8"
        if enc.lower() not in ("utf-8", "utf8"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))

from app.main import main

if __name__ == "__main__":
    main()
