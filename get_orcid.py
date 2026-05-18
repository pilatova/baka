#!/usr/bin/env python3

import argparse
import csv
import time
import sys
import io
from tqdm import tqdm
from orcidfetch import Orcid


def split_authfull(name_string):
    if "," in name_string:
        parts = name_string.split(",", 1)
        lastname = parts[0].strip()
        firstname = parts[1].strip()
    else:
        parts = name_string.rsplit(" ", 1)
        firstname = parts[0].strip()
        lastname = parts[-1].strip()
    return firstname, lastname


def process_tsv(input_stream, name_col, affil_col):
    # Fix for rows starting with \ufeff issue
    input_data = io.TextIOWrapper(input_stream.buffer, encoding='utf-8-sig')
    reader = csv.DictReader(input_data, delimiter="\t")
    if not reader.fieldnames:
        print("Error: Empty input or missing header.", file=sys.stderr)
        return

    new_cols = ["orcid", "confidence", "method"]
    idx = reader.fieldnames.index(affil_col) + 1
    output_fields = reader.fieldnames[:idx] + new_cols + reader.fieldnames[idx:]
    writer = csv.DictWriter(sys.stdout, fieldnames=output_fields, delimiter="\t")
    writer.writeheader()

    data = list(reader)

    for row in tqdm(data, desc="Fetching ORCIDs", unit="researcher", file=sys.stderr):
        authfull = row.get(name_col, "").strip()
        affiliation = row.get(affil_col, "").strip()

        if not authfull:
            row.update({"orcid": "NULL", "confidence": "NULL", "method": "NULL"})
            writer.writerow(row)
            continue

        firstname, lastname = split_authfull(authfull)
        try:
            author_search_name = f"{firstname} {lastname}"
            lookup = Orcid(author_name=author_search_name, affiliation=affiliation)
            
            row["orcid"] = lookup.orcid if lookup.orcid else "NULL"
            row["confidence"] = lookup.confidence if lookup.orcid else "NULL"
            row["method"] = lookup.method if lookup.orcid else "NULL"

        except ValueError as _:
            # This catches the "not enough values to unpack" bug from the orcidfetch library
            tqdm.write(f"Library Bug for {authfull}: Skipping due to internal unpacking error.", file=sys.stderr)
            row.update({"orcid": "LIB_ERROR", "confidence": "NULL", "method": "NULL"})

        except Exception as e:
            tqdm.write(f"Error for {authfull}: {e}", file=sys.stderr)
            row.update({"orcid": "ERROR", "confidence": "NULL", "method": "NULL"})

        writer.writerow(row)
        time.sleep(0.5)  # Speed limit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ORCIDs from redirected TSV stream containing name and affiliation (compatible only with the Elsevier dataset format).")
    parser.add_argument('--name_col', default='authfull', help="Name of the column containing the researcher's name.")
    parser.add_argument('--affil_col', default='inst_name', help="Name of the column containing the researcher's affiliation.")
    args = parser.parse_args()
    
    process_tsv(sys.stdin, args.name_col, args.affil_col)
