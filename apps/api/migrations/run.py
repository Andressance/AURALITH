"""Run Alembic migrations at container start.

``alembic upgrade head`` finds alembic.ini by looking in the current directory,
which is fragile inside an image: if the file is missing or relocated the deploy
dies with "No 'script_location' key found in configuration", a message that says
nothing about the real cause. This entry point builds the same configuration in
code from its own location, so the only thing it depends on is this package's
path inside the image.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

MIGRATIONS_DIR = Path(__file__).resolve().parent


def _import_roots(start: Path, depth: int = 4) -> list[Path]:
    """Candidate import roots for both supported layouts.

    The repository root (apps/api/migrations) and the API directory built on its own
    (/app/migrations, where app.py is the module and there is no apps/ package).
    Walking up avoids IndexError from a short parents sequence.
    """
    roots, current = [start], start
    for _ in range(depth):
        if current.parent == current:
            break
        current = current.parent
        roots.append(current)
    return roots


def main() -> int:
    for root in _import_roots(MIGRATIONS_DIR):
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    print(f"Applying database migrations from {MIGRATIONS_DIR}", flush=True)
    command.upgrade(config, "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
