"""Clean the raw Seoul bike-sharing CSV and write the clean CSV.

Run from the project root:
    python src/clean_data.py

Cleaning rules (documented for the report, section 2 Data):
  1. Strip thousands commas from rented_bikes and cast it to int.
     Rows where rented_bikes is not a number (e.g. "n/a") are dropped,
     because the target cannot be imputed.
  2. Fill missing temp_c and humidity_pct with the median of the same season.
  3. Normalise holiday labels to "Holiday" / "No Holiday".
  4. Drop rows whose hour is outside 0-23.
  5. Parse and validate datetime (YYYY-MM-DD HH:MM:SS); drop unparseable rows.
  6. Drop exact duplicate rows (first occurrence is kept).
Output keeps the same 10 columns in the original order.
"""

RAW_PATH = "data/raw_seoul_bike_2025.csv"
CLEAN_PATH = "data/clean_seoul_bike_2025.csv"
COLUMNS = ["datetime", "rented_bikes", "hour", "temp_c", "humidity_pct",
           "wind_ms", "rain_mm", "snow_cm", "season", "holiday"]
FILL_COLUMNS = ["temp_c", "humidity_pct"]


def split_row(line):
    """Split one CSV line, respecting double-quoted fields such as "1,204"."""
    fields, current, in_quotes = [], "", False
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            fields.append(current.strip())
            current = ""
        else:
            current += ch
    fields.append(current.strip())
    return fields


def to_number(text):
    """Return a float, or None for missing / non-numeric text."""
    try:
        return float(text.replace(",", "").strip())
    except ValueError:
        return None


def valid_datetime(text):
    """Check the YYYY-MM-DD HH:MM:SS layout and simple value ranges."""
    try:
        date_part, time_part = text.split(" ")
        y, m, d = date_part.split("-")
        hh, mm, ss = time_part.split(":")
        parts = [y, m, d, hh, mm, ss]
        if not all(p.isdigit() for p in parts) or len(y) != 4:
            return False
        return 1 <= int(m) <= 12 and 1 <= int(d) <= 31 and int(hh) < 24 and int(mm) < 60
    except ValueError:
        return False


def normalise_holiday(text):
    """Map spelling variants such as 'no holiday' or 'Holliday' to two labels."""
    return "No Holiday" if text.strip().lower().startswith("no") else "Holiday"


def median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def main():
    with open(RAW_PATH, encoding="utf-8") as f:
        lines = [line.rstrip("\r\n") for line in f if line.strip()]

    header = split_row(lines[0])
    idx = {name: header.index(name) for name in COLUMNS}

    rows, seen, dropped = [], set(), 0
    for line in lines[1:]:
        raw = split_row(line)
        if len(raw) != len(header):
            dropped += 1
            continue
        rec = {name: raw[idx[name]] for name in COLUMNS}

        bikes = to_number(rec["rented_bikes"])
        hour = to_number(rec["hour"])
        if bikes is None or hour is None or not 0 <= hour <= 23:
            dropped += 1
            continue
        if not valid_datetime(rec["datetime"]):
            dropped += 1
            continue

        rec["rented_bikes"] = str(int(bikes))
        rec["hour"] = str(int(hour))
        rec["holiday"] = normalise_holiday(rec["holiday"])

        key = tuple(rec[name] for name in COLUMNS)
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        rows.append(rec)

    # Median fill, computed per season from the observed values only.
    for col in FILL_COLUMNS:
        by_season = {}
        for rec in rows:
            value = to_number(rec[col])
            if value is not None:
                by_season.setdefault(rec["season"], []).append(value)
        for rec in rows:
            if to_number(rec[col]) is None:
                fill = median(by_season.get(rec["season"], []))
                rec[col] = "" if fill is None else str(round(fill, 2))

    with open(CLEAN_PATH, "w", encoding="utf-8") as f:
        f.write(",".join(COLUMNS) + "\n")
        for rec in rows:
            f.write(",".join(rec[name] for name in COLUMNS) + "\n")

    print(f"Read {len(lines) - 1} raw rows, dropped {dropped}, wrote {len(rows)} rows to {CLEAN_PATH}")


if __name__ == "__main__":
    main()
