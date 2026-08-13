"""Rotate persisted settings secrets without exposing their values.

Run from ``backend/`` after configuring the new current key and one or more old
decryption-only keys::

    python -m app.cli.rotate_secrets --dry-run
    python -m app.cli.rotate_secrets
"""

from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.services.secret_rotation_service import rotate_saved_secrets


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate AllHaven settings ciphertext")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="verify every ciphertext and report the rotation count without writing",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        result = rotate_saved_secrets(db, dry_run=args.dry_run)
    mode = "would rotate" if args.dry_run else "rotated"
    print(
        f"Verified {result['scanned']} encrypted value(s); {mode} "
        f"{result['rotated']} value(s) in {result['rows_changed']} row(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
