"""
Package entrypoint so the demo runs with either:

    python -m backend.dialogues
    python -m backend.dialogues.demo
"""

from .demo import main

if __name__ == "__main__":
    raise SystemExit(main())
