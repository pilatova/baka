#!/usr/bin/env python3
import argparse
from datetime import datetime
from collections import defaultdict
import json
import os


def get_json_files(directory):
    file_paths = []
    for root, dirs, files in os.walk(directory):
        parts = os.path.normpath(root).split(os.sep)

        if any(p.startswith('citing') for p in parts):
            for file in files:
                if file.endswith('.json'):
                    file_paths.append(os.path.join(root, file))
    return file_paths


def valid_date(date_s):
    if not isinstance(date_s, str):
        return False
    try:
        datetime.strptime(date_s, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def get_authors_data(directory, au_id):
    author_folder = os.path.join(directory, au_id)
    if not os.path.exists(author_folder) or not os.path.isdir(author_folder):
        raise Exception(f"Couldn't find {au_id} author's folder in {os.path.abspath(directory)}")

    citing_works_info = []
    seen_works_eids = set()
    for json_file in get_json_files(author_folder):
        with open(json_file, 'r') as f:
            try:
                data = json.load(f)
                if "abstracts-retrieval-response" in data:
                    data = data["abstracts-retrieval-response"]
                
                core = data.get('coredata', {})
                eid =core.get('eid')
                if eid in seen_works_eids:
                    continue
                seen_works_eids.add(eid)
                info = {
                    'eid': eid,
                    'title': core.get('dc:title'),
                    'publication_date': core.get('prism:coverDate'),
                    'venue_id': core.get('source-id'),
                    'venue_name': core.get('prism:publicationName', 'Unknown Venue'),
                    'authors': {}
                }
                if not valid_date(info['publication_date']):
                    print(f"Warning: Invalid date '{info['publication_date']}' for {info['eid']} at {json_file}. Skipping.")
                    continue
                if not info['venue_id']:
                    info['venue_id'] = core.get('dc:publisher')
                    info['venue_name'] = info['venue_id'] or 'Unknown Venue'

                raw_authors = (data.get('authors', ) or {}).get('author', [])
                if isinstance(raw_authors, dict):
                    raw_authors = [raw_authors]
                
                for au in raw_authors:
                    au_id = au.get('@auid')
                    pref = au.get('preferred-name', {})
                    info['authors'][au_id] = (
                        pref.get('ce:given-name', 'Unknown'),
                        pref.get('ce:surname', 'Unknown')
                    )

                citing_works_info.append(info)

            except json.JSONDecodeError as e:
                print(f"Couldn't read json data from {json_file}: {e}")
    return citing_works_info


def calculate_DRS(sorted_works, p = 1):
    if len(sorted_works) == 0:
        return 0, [], [], [], {}, {}
    
    # counted bibliographic variables
    authors_count = defaultdict(int)
    venues_count = defaultdict(int)
    author_names = {}
    venue_names = {}

    total_drs = 0
    scores = []
    rs = []
    determining_vars = []
    for work in sorted_works:
        current_max_r = 0
        current_max_r_vars = []

        for au_id in work['authors']:
            if au_id is None:
                continue
            if authors_count[au_id] > current_max_r:
                current_max_r = authors_count[au_id]
                current_max_r_vars = [('author', au_id)]
            elif current_max_r > 0 and authors_count[au_id] == current_max_r:
                current_max_r_vars.append(('author', au_id))

        if work['venue_id'] is not None:
            if venues_count[work['venue_id']] > current_max_r:
                current_max_r = venues_count[work['venue_id']]
                current_max_r_vars = [('venue', work['venue_id'])]
            elif current_max_r > 0 and venues_count[work['venue_id']] == current_max_r:
                current_max_r_vars.append(('venue', work['venue_id']))
        
        contribution = (1 + current_max_r) ** (-p)
        total_drs += contribution
        scores.append((contribution))
        rs.append(current_max_r)
        determining_vars.append(current_max_r_vars.copy())

        for au_id in work['authors']:
            authors_count[au_id] += 1
            author_names[au_id] = work['authors'][au_id]

        venues_count[work['venue_id']] += 1
        venue_names[work['venue_id']] = work['venue_name']

    assert abs(sum(scores) - total_drs) < 1e-8
    assert len(sorted_works) == len(rs)
    assert len(sorted_works) == len(scores)
    assert len(sorted_works) == len(determining_vars)
    return total_drs, scores, rs, determining_vars, author_names, venue_names


def calculate_DRS_vector(sorted_works, p_values = [0, 0.5, 1, 2]):
    if len(sorted_works) == 0:
        return [0] * len(p_values), []
    
    # counted bibliographic variables
    authors_count = defaultdict(int)
    venues_count = defaultdict(int)

    rs = []
    for work in sorted_works:
        current_max_r = 0

        for au_id in work['authors']:
            if au_id is None:
                continue
            if authors_count[au_id] > current_max_r:
                current_max_r = authors_count[au_id]

        if work['venue_id'] is not None:
            if venues_count[work['venue_id']] > current_max_r:
                current_max_r = venues_count[work['venue_id']]
        
        rs.append(current_max_r)

        for au_id in work['authors']:
            authors_count[au_id] += 1
        if work['venue_id']:
            venues_count[work['venue_id']] += 1

    score_vector = []
    for p in p_values:
        total_drs = sum((1 + r) ** (-p) for r in rs)
        score_vector.append(total_drs)

    return score_vector, rs


def process_all_scientists(au_ids, cache_dir, p_values = [0, 0.5, 1, 2], output_file="drsc_results.jsonl"):
    with open(output_file, 'w') as out_f:
        for au_id in au_ids:
            works_data = get_authors_data(cache_dir, au_id)
            
            sorted_works = sorted(works_data, key=lambda x: (x['publication_date'], x['eid']))
            
            if len(p_values) == 1:
                drs, scores, rs, determining_vars, author_names, venue_names = calculate_DRS(sorted_works, p_values[0])

                audit_trail = []
                for i, work in enumerate(sorted_works):
                    audit_trail.append({
                        "eid": work['eid'],
                        "date": work['publication_date'],
                        "order": i,
                        "r": rs[i],
                        "score": scores[i],
                        "penalty_vars": [
                                {"type": var_type, "id": var_id} 
                                for var_type, var_id in determining_vars[i]
                            ]
                    })

                record = {
                    "au_id": au_id,
                    "p": p_values[0],
                    "total_drs": drs,
                    "citing_count": len(sorted_works),
                    "lookup": {
                        "venues": venue_names,
                        "authors": {au_id: (f"{names[1]}, {names[0]}" if names else 'Unknown') for au_id, names in author_names.items()}
                    },
                    "audit": audit_trail
                }

                out_f.write(json.dumps(record) + "\n")

            else:
                vector, rs = calculate_DRS_vector(sorted_works, p_values)

                record = {
                    "au_id": au_id,
                    "p_values": p_values,
                    "drs_vector": vector,
                    "citing_count": len(sorted_works)
                }
                out_f.write(json.dumps(record) + "\n")


def main():
    parser = argparse.ArgumentParser(description='Process author\'s data from json files and compute DRSC')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--au-id', help="Single Author's ID (folder name)")
    group.add_argument('--id-file', help='File containing newline separated list of Author IDs')

    parser.add_argument('--directory', 
        help='Directory with authors\' json data', required=False, 
        default='./authors_cache')
    parser.add_argument('--p-values', type=float, nargs='+', default=[1.0], 
        help='Space-separated list of tunable p parameter values to compute')
    parser.add_argument('--output', default='drsc_results.jsonl', help='Output JSONL filename')

    args = parser.parse_args()

    if args.id_file:
        if not os.path.exists(args.id_file):
            print(f"Error: {args.id_file} not found.")
            return
        with open(args.id_file, 'r') as f:
            au_ids = [line.strip() for line in f if line.strip()]
    else:
        au_ids = [args.au_id]
    
    process_all_scientists(au_ids, args.directory, args.p_values, args.output)


if __name__ == '__main__':
    main()


