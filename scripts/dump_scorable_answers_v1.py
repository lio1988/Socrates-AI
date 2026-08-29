"""Print every field of every scorable answer, so scoring cannot truncate one.

Why this exists.

The Q3 council was first scored 30/32 and the best baseline 32/32, supporting a
conclusion that the council had lost a distinction one of its own seats found
unaided. That was wrong. The council answer had been read through two of its six
synthesis fields; the missing criterion was stated in ``crucial_stress_test``,
which has no baseline counterpart. Baselines were scored whole, the council was
scored truncated, and the asymmetry ran one way — against CED — because the
extra fields are exactly what the CED contract adds.

So the rule is: score every field or none. This prints every field, and prints a
field count so a short read is visible as a short read rather than assumed to be
the whole answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _content(raw: str) -> Dict[str, Any]:
    parsed = json.loads(raw)
    inner = parsed.get("content")
    return inner if isinstance(inner, dict) else parsed


def iter_answers_v1(path: Path) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield (label, all-fields) for a council run or a baseline collection."""

    document = json.loads(path.read_text(encoding="utf-8"))
    for row in document.get("samples", ()):
        answer = row.get("answer")
        if answer:
            yield f"{row.get('label')} #{row.get('sample_index')}", _content(answer)
    for turn in document.get("turns", ()):
        raw = turn.get("assistant_output_sanitized")
        if not raw:
            continue
        label = (
            f"{turn.get('dialogue_phase')}/{turn.get('role_seat')}"
            f" [{turn.get('model')}] accepted={turn.get('ced_move_accepted')}"
        )
        try:
            yield label, _content(raw)
        except ValueError:
            yield label, {"__unparsed__": raw}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        print("usage: dump_scorable_answers_v1.py FILE [substring-filter]")
        return 2
    path = Path(argv[1])
    needle = argv[2].lower() if len(argv) > 2 else None
    shown = 0
    for label, fields in iter_answers_v1(path):
        if needle and needle not in label.lower():
            continue
        shown += 1
        print("\n" + "=" * 72)
        print(f"{label}  |  {len(fields)} fields: {sorted(fields)}")
        print("=" * 72)
        for name in sorted(fields):
            value = fields[name]
            text = value if isinstance(value, str) else json.dumps(
                value, ensure_ascii=False, indent=1
            )
            print(f"\n--[{name}]--\n{text}")
    print(f"\n{shown} answers printed, every field of each.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
