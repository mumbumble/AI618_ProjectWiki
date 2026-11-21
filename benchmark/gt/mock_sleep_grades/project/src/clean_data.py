"""Clean the raw STAT2101 student sleep survey.

Run from the project root:
    python src/clean_data.py

Reads  data/raw_student_sleep_survey_2026.csv
Writes data/clean_student_sleep_survey_2026.csv

Steps:
  1. parse messy numeric text ("7h", "six and half", "N/A", "abc")
  2. drop invalid rows (missing or out-of-range grade/sleep, etc.)
  3. drop duplicate student_id rows, keeping the first valid one
  4. impute missing work_hours and study_hours with the column median
"""

RAW_PATH = "data/raw_student_sleep_survey_2026.csv"
CLEAN_PATH = "data/clean_student_sleep_survey_2026.csv"

COLUMNS = ["student_id", "gender", "year", "sleep_hours", "work_hours",
           "study_hours", "caffeine_cups", "course_grade"]
NUMERIC = COLUMNS[2:]
VALID_RANGE = {
    "year": (1, 4),
    "sleep_hours": (3, 12),
    "work_hours": (0, 40),
    "study_hours": (0, 30),
    "caffeine_cups": (0, 8),
    "course_grade": (0, 100),
}
IMPUTE_COLUMNS = ["work_hours", "study_hours"]
NUMBER_WORDS = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def parse_hours(raw):
    """Turn messy numeric text into a float, or None if missing or unreadable."""
    text = raw.strip().lower()
    if text in ("", "na", "n/a", "nan"):
        return None
    if text.endswith("h"):
        text = text[:-1].strip()
    if text.endswith(" and half"):
        base = text[:-len(" and half")].strip()
        return NUMBER_WORDS[base] + 0.5 if base in NUMBER_WORDS else None
    try:
        return float(text)
    except ValueError:
        return None


def read_rows(path):
    """Read the raw CSV into a list of dicts with parsed numeric fields."""
    with open(path, encoding="utf-8") as handle:
        lines = [line.strip() for line in handle if line.strip()]
    header = [name.strip() for name in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        raw = dict(zip(header, [field.strip() for field in line.split(",")]))
        row = {"student_id": raw.get("student_id", ""), "gender": raw.get("gender", "")}
        for column in NUMERIC:
            row[column] = parse_hours(raw.get(column, ""))
        rows.append(row)
    return rows


def is_valid(row):
    """A row is valid when every value is inside its range. Missing imputed columns are allowed."""
    for column, (low, high) in VALID_RANGE.items():
        value = row[column]
        if value is None:
            if column in IMPUTE_COLUMNS:
                continue
            return False
        if not low <= value <= high:
            return False
    return True


def drop_invalid(rows):
    """Keep the first valid row for each student_id."""
    kept, seen = [], set()
    for row in rows:
        if row["student_id"] in seen or not is_valid(row):
            continue
        seen.add(row["student_id"])
        kept.append(row)
    return kept


def median(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def impute_median(rows, column):
    """Fill missing values in one column with the median of the observed values."""
    observed = [row[column] for row in rows if row[column] is not None]
    fill = median(observed)
    count = 0
    for row in rows:
        if row[column] is None:
            row[column] = fill
            count += 1
    return fill, count


def format_value(column, value):
    if column in ("year", "caffeine_cups"):
        return str(int(value))
    return f"{value:.1f}"


def write_rows(path, rows):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(",".join(COLUMNS) + "\n")
        for row in rows:
            fields = [row["student_id"], row["gender"]]
            fields += [format_value(column, row[column]) for column in NUMERIC]
            handle.write(",".join(fields) + "\n")


def main():
    rows = read_rows(RAW_PATH)
    print(f"Raw rows read: {len(rows)}")

    clean = drop_invalid(rows)
    print(f"Rows kept after removing duplicates and invalid values: {len(clean)}")
    print(f"Rows dropped: {len(rows) - len(clean)}")

    for column in IMPUTE_COLUMNS:
        fill, count = impute_median(clean, column)
        print(f"Imputed {count} missing {column} value(s) with median {fill:.1f}")

    assert all(row[column] is not None for row in clean for column in NUMERIC)
    write_rows(CLEAN_PATH, clean)
    print(f"Wrote {len(clean)} rows to {CLEAN_PATH}")


if __name__ == "__main__":
    main()
