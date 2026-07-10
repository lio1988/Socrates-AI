"""Recover one interrupted OpenClaw self-revision application transaction.

Usage:
    python scripts/openclaw_recover_revision.py <agent_id> <proposal_id>

The command reads the write-ahead journal and deterministically completes only a
state consistent with both registries. It does not evaluate a new proposal,
approve anything, or create new evidence.
"""

from __future__ import annotations

import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.dialogues.openclaw_identity import (                       # noqa: E402
    IdentityRegistry,
    SelfRevisionRegistry,
    SelfRevisionTransactionCoordinator,
    profile_fingerprint,
)

_W = 78


def main(argv=None, env=None) -> int:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env
    if len(argv) != 3:
        print("Usage: python scripts/openclaw_recover_revision.py "
              "<agent_id> <proposal_id>")
        return 2
    agent_id = str(argv[1]).strip()
    proposal_id = str(argv[2]).strip()

    identity_dir = pathlib.Path(env.get(
        "CED_IDENTITY_DIR", str(_ROOT / "runs" / "openclaw_identity")))
    lifecycle_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_DIR",
        str(_ROOT / "runs" / "openclaw_self_revisions"),
    ))
    transaction_dir = pathlib.Path(env.get(
        "CED_SELF_REVISION_TRANSACTION_DIR",
        str(_ROOT / "runs" / "openclaw_self_revision_transactions"),
    ))

    coordinator = SelfRevisionTransactionCoordinator(
        IdentityRegistry(identity_dir),
        SelfRevisionRegistry(lifecycle_dir),
        transaction_dir,
    )
    try:
        before = coordinator.load(agent_id, proposal_id)
        if before is None:
            print(f"No transaction found for {agent_id}/{proposal_id}")
            return 1
        profile = coordinator.recover(agent_id, proposal_id)
        after = coordinator.load(agent_id, proposal_id)
    except ValueError as exc:
        print(f"Recovery refused: {exc}")
        return 1

    print("=" * _W)
    print("  OPENCLAW SELF-REVISION RECOVERY")
    print("=" * _W)
    print(f"  agent       : {agent_id}")
    print(f"  proposal    : {proposal_id}")
    print(f"  before      : {before['state']}")
    print(f"  after       : {after['state']}")
    print(f"  identity    : {profile_fingerprint(profile)}")
    print("-" * _W)
    print("  Recovery completed an already prepared application transaction.")
    print("  No new proposal, evidence, approval, or authority was created.")
    print("=" * _W)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
