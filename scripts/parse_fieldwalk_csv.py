#!/usr/bin/env python3
"""Convert the weekly AppFolio "Fieldwalk Directory" unit-list export into properties.seed.json.

Usage: parse_fieldwalk_csv.py <input.csv> <output properties.seed.json path>

The AppFolio export groups units under property header rows ("-> Address"),
followed by one row per unit, then a blank-name subtotal row, repeated per
property, with a final grand-total row. This pulls out just the real
property/unit rows.
"""
import csv
import json
import sys
import datetime

SEED_COMMENT = (
    "Auto-generated from the weekly property list email. Do not hand-edit — "
    "edits here are overwritten on the next sync. Use the app's 'Manage properties' "
    "screen for one-off additions instead."
)


def parse_num(val):
    val = (val or '').strip()
    if not val:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0


def clean_address(addr):
    # AppFolio often exports "Nickname - Full Address" where Full Address starts
    # with Nickname verbatim; collapse that safely without touching real
    # hyphenated street names (e.g. "10-12 Atkinson St"), which never have
    # spaces around the dash.
    if ' - ' in addr:
        part1, rest = addr.split(' - ', 1)
        if rest.startswith(part1):
            return rest
    return addr


def parse_fieldwalk_csv(path):
    properties = []
    current = None
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))

    for row in rows[1:]:  # skip header row ("Unit Name,Bedrooms,Bathrooms")
        if not row or all(not (c or '').strip() for c in row):
            continue
        name = (row[0] or '').strip() if len(row) > 0 else ''
        beds_raw = row[1] if len(row) > 1 else ''
        baths_raw = row[2] if len(row) > 2 else ''

        if name.startswith('->'):
            addr = clean_address(name[2:].strip())
            current = {'address': addr, 'units': []}
            properties.append(current)
            continue
        if name.lower() == 'total':
            continue
        if not name:
            continue  # per-property subtotal row
        if current is None:
            continue

        current['units'].append({
            'label': name,
            'bedrooms': int(round(parse_num(beds_raw))),
            'bathrooms': parse_num(baths_raw),
        })
    return properties


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.csv> <output properties.seed.json>", file=sys.stderr)
        sys.exit(1)
    csv_path, out_path = sys.argv[1], sys.argv[2]

    properties = parse_fieldwalk_csv(csv_path)
    if not properties:
        print("ERROR: parsed zero properties from the input file — refusing to overwrite. "
              "Check that the attachment downloaded correctly and matches the expected export format.",
              file=sys.stderr)
        sys.exit(1)

    try:
        with open(out_path) as f:
            existing = json.load(f)
        existing_count = len(existing.get('properties', []))
        if existing_count > 0 and len(properties) < existing_count * 0.5:
            print(f"ERROR: new file has {len(properties)} properties vs {existing_count} currently on file "
                  "— more than a 50% drop. Refusing to overwrite; this smells like a truncated or wrong "
                  "attachment. Investigate before forcing an update.", file=sys.stderr)
            sys.exit(1)
    except FileNotFoundError:
        pass

    out = {
        '_comment': SEED_COMMENT,
        'updatedAt': datetime.datetime.utcnow().isoformat() + 'Z',
        'properties': properties,
    }
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
        f.write('\n')

    unit_count = sum(len(p['units']) for p in properties)
    print(f"Wrote {len(properties)} properties, {unit_count} units to {out_path}")


if __name__ == '__main__':
    main()
