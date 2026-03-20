"""Entry point for python3 -m secnano._subagent <base64_task_json>"""
from __future__ import annotations

import sys

from secnano.subagent.subagent_entry import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
