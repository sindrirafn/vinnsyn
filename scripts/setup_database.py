"""Create or update the standalone Vinnsyn market archive schema."""
from __future__ import annotations

from pathlib import Path

from vinnsyn.db import connect, transaction


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_FILES = [
    PROJECT_ROOT / "sql" / "00_create_parse_iso_date.sql",
    PROJECT_ROOT / "sql" / "21_create_market_job_tables.sql",
    PROJECT_ROOT / "sql" / "22_create_market_historical_discoveries.sql",
    PROJECT_ROOT / "sql" / "23_add_historical_retry_queue.sql",
    PROJECT_ROOT / "sql" / "24_create_historical_capture_documents.sql",
    PROJECT_ROOT / "sql" / "25_create_live_listing_documents.sql",
    PROJECT_ROOT / "sql" / "26_market_taxonomy_and_cleanup.sql",
]


def statements(sql: str) -> list[str]:
    """Split trusted migrations while respecting SQL quotes and comments."""
    values: list[str] = []
    current: list[str] = []
    in_single_quote = in_double_quote = in_line_comment = False
    index = 0
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
                current.append(char)
            index += 1
            continue
        if not in_single_quote and not in_double_quote and char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue
        if char == "'" and not in_double_quote:
            current.append(char)
            if in_single_quote and next_char == "'":
                current.append(next_char)
                index += 2
                continue
            in_single_quote = not in_single_quote
            index += 1
            continue
        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(char)
            index += 1
            continue
        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                values.append(statement)
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    statement = "".join(current).strip()
    return values + ([statement] if statement else [])


@transaction()
def main() -> None:
    with connect() as connection, connection.cursor() as cursor:
        for sql_file in SQL_FILES:
            for statement in statements(sql_file.read_text(encoding="utf-8")):
                cursor.execute(statement)
            print(f"Applied {sql_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
