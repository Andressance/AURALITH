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
PROJECT_ROOT = MIGRATIONS_DIR.parents[2]


def main() -> int:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    print(f"Applying database migrations from {MIGRATIONS_DIR}", flush=True)
    command.upgrade(config, "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
