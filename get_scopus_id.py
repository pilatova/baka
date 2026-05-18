#!/usr/bin/env python3

import argparse
import csv
import sys
import io
import re
from tqdm import tqdm
import pybliometrics
from pybliometrics.scopus import AuthorSearch

def clean_query_string(text):
    # Removes anything in parentheses and extra whitespace because it results 
    # in Scopus search error
    if not text:
        return ""
    # Looks for '(' followed by anything until ')' and removes it
    cleaned = re.sub(r'\(.*?\)', '', text)
    # Remove extra spaces left behind
    return " ".join(cleaned.split()).strip()

def split_authfull(name_string):
    name_string = clean_query_string(name_string)
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

    output_fields = [name_col, affil_col, "scopus_id"]
    writer = csv.DictWriter(sys.stdout, fieldnames=output_fields, delimiter="\t", extrasaction='ignore')
    writer.writeheader()

    data = list(reader)
    for row in tqdm(data, desc="Searching Scopus", unit="author", file=sys.stderr):
        authfull = row.get(name_col, "").strip()
        if not authfull:
            writer.writerow({name_col: "", affil_col: "", "scopus_id": "NULL"})
            continue

        firstname, lastname = split_authfull(authfull)
        affiliation = clean_query_string(row.get(affil_col, "").strip())
        try:
            query = f"AUTHLAST({lastname}) AND AUTHFIRST({firstname}) AND SUBJAREA(MATH)"
            if affiliation:
                s = AuthorSearch(f'{query} AND AFFIL({affiliation})')
            if not affiliation or s.authors is None:
                s = AuthorSearch(query)

            if s.authors:
                ids = [a.eid.split('-')[-1] for a in s.authors]
                
                if len(ids) == 1:
                    row["scopus_id"] = ids[0]
                else:
                    # Store all potential IDs separated by a semicolon
                    row["scopus_id"] = ";".join(ids)
            else:
                row["scopus_id"] = "NOT_FOUND"

        except Exception as e:
            tqdm.write(f"Error for {authfull}: {e}", file=sys.stderr)
            row["scopus_id"] = "ERROR"

        writer.writerow(row)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch ORCIDs from redirected TSV stream containing name and affiliation (compatible only with the Elsevier dataset format).")
    parser.add_argument('--name_col', default='authfull', help="Name of the column containing the researcher's name.")
    parser.add_argument('--affil_col', default='inst_name', help="Name of the column containing the researcher's affiliation.")
    args = parser.parse_args()
    
    pybliometrics.init()
    process_tsv(sys.stdin, args.name_col, args.affil_col)
