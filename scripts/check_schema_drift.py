import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import models  # noqa: F401 - register SQLModel table metadata
from config import settings


def metadata_table_names() -> set[str]:
    return set(SQLModel.metadata.tables.keys())


def database_table_names(database_url: str | None = None) -> set[str]:
    engine = create_engine(database_url or settings.DATABASE_URL)
    return set(inspect(engine).get_table_names())


def compare_table_names(actual_tables: Iterable[str], expected_tables: Iterable[str]) -> dict[str, list[str]]:
    actual = set(actual_tables)
    expected = set(expected_tables)
    return {
        "missing_in_database": sorted(expected - actual),
        "extra_in_database": sorted(actual - expected),
    }


def check_schema_drift(database_url: str | None = None) -> dict[str, list[str]]:
    return compare_table_names(database_table_names(database_url), metadata_table_names())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check database tables against SQLModel metadata.")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL for this check.")
    parser.add_argument(
        "--metadata-only",
        "--print-metadata",
        dest="metadata_only",
        action="store_true",
        help="Print metadata table names without connecting.",
    )
    args = parser.parse_args()

    if args.metadata_only:
        print(json.dumps(sorted(metadata_table_names()), ensure_ascii=False, indent=2))
        return 0

    result = check_schema_drift(args.database_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["missing_in_database"] or result["extra_in_database"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
