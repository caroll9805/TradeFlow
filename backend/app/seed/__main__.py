"""Usage:
    python -m app.seed            # reference/configuration data only
    python -m app.seed --demo     # + SIMULATED demo dataset (clearly labelled, removable)
"""
import sys

from app.core.database import SessionLocal
from app.seed.base import seed_reference
from app.seed.demo import seed_demo


def main() -> None:
    db = SessionLocal()
    try:
        seed_reference(db)
        print("Reference data: OK")
        if "--demo" in sys.argv:
            print("SIMULATED demo data:", seed_demo(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
