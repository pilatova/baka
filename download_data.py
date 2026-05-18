#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
import requests

import pybliometrics
from pybliometrics.scopus import ScopusSearch, AbstractRetrieval
from pybliometrics.exception import (
    Scopus401Error, Scopus403Error, Scopus404Error, Scopus429Error, ScopusServerError
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("thesis_data_fetch.log"), logging.StreamHandler()]
)

def build_query(query, start_year=None, end_year=None):
    """Adds year constraints to a Scopus query string."""
    if start_year:
        query += f' AND PUBYEAR AFT {start_year - 1}'
    if end_year:
        query += f' AND PUBYEAR BEF {end_year}'
    return query

def fetch_abstract(eid):
    """Retrieves abstract data using pybliometrics."""
    try:
        # view='FULL' is necessary to get the bibliography/references
        return AbstractRetrieval(eid, view='FULL')
    
    except (Scopus401Error, Scopus403Error):
        logging.critical(f"Authentication Failed when fetching {eid}. Check your API Key or VPN/IP access.")
        exit(1)
    except Scopus429Error:
        logging.critical(f"Quota Exceeded at {eid}. Stopping.")
        exit(1)
    except (ScopusServerError, Scopus404Error, requests.exceptions.ConnectionError, 
            requests.exceptions.Timeout) as e:
        logging.warning(f"Network/Server issue. Skipping {eid}: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error while fetching {eid}: {e}")
    return None

def save_json(folder_path, eid, scopus_cache_base=None):
    """Creates a symlink to the pybliometrics cache."""
    if scopus_cache_base is None:
        # Standard pybliometrics location for the current user
        scopus_cache_base = Path.home() / ".cache/pybliometrics/Scopus/abstract_retrieval/FULL"

    folder_path.mkdir(parents=True, exist_ok=True)
    cache_source = Path(scopus_cache_base) / eid
    link_target = folder_path / f"{eid}.json"

    if not cache_source.exists():
        logging.warning(f"Pybliometrics cache source {cache_source} missing.")

    if link_target.exists():
        logging.debug(f"Link {link_target} already exists, skipping.")
        return

    try:
        link_target.symlink_to(cache_source)
        logging.debug(f"Linked {eid} to cache {cache_source}.")
    except Exception:
        logging.exception(f"Failed to create symlink for {eid}.")

def is_citing(citing_paper, target_eid):
    """Verifies if target_eid is in the references of citing_paper."""
    if not target_eid.startswith('2-s2.0-'):
        logging.error(f"Wrong format for {target_eid}, doesn't start with 2-s2.0-.")
    
    refs = citing_paper.references
    if not refs:
        return False
    
    # Check if numerical ID part matches
    return any(ref.id and f"2-s2.0-{ref.id.split('-')[-1]}" == target_eid
               for ref in refs)

def main():
    parser = argparse.ArgumentParser(description="Fetch Scopus publications and citations.")
    # Author identification (exclusive group: use one or the other)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--orcid', help="Author's ORCID")
    group.add_argument('--author-id', help="Author's Scopus ID (numerical part)")
    # Year ranges filter
    parser.add_argument('--work-start', type=int, help="Author publication start year (inclusive)")
    parser.add_argument('--work-end', type=int, help="Author publication end year (exclusive)")
    parser.add_argument('--cite-start', type=int, help="Citing works start year (inclusive)")
    parser.add_argument('--cite-end', type=int, help="Citing works end year (exclusive)")
    
    parser.add_argument('--scopus-cache', default=str(Path.home() / ".cache/pybliometrics/Scopus/abstract_retrieval/FULL"),
        help="Path to the pybliometrics FULL abstract cache")
    parser.add_argument('--cache-dir', default='./authors_cache', help="Storage directory")
    args = parser.parse_args()

    pybliometrics.init()
    
    if args.orcid:
        base_query = f'ORCID({args.orcid})'
        id_label = args.orcid
    else:
        base_query = f'AU-ID({args.author_id})'
        id_label = args.author_id
    author_query = build_query(base_query, args.work_start, args.work_end)
    search = ScopusSearch(author_query)
    
    if not search.results:
        logging.info(f"No results found for query: {author_query}.")
        return

    author_base_path = Path(args.cache_dir) / id_label
    logging.info(f"Found {len(search.results)} works for {id_label}.")

    # Process Author's Works
    for eid in search.get_eids():
        paper = fetch_abstract(eid)
        if not paper:
            continue

        # Organize by author's publication year
        pub_year = paper.coverDate[:4] if paper.coverDate else "Unknown"
        year_folder = author_base_path / pub_year
        
        logging.info(f"Processing Work: {eid} (year: {pub_year})")
        save_json(year_folder, eid, scopus_cache_base=args.scopus_cache)

        cited_count = paper.citedby_count or 0
        if cited_count == 0:
            logging.info(f"0 citations reported, skipping citation search for {eid}.")
            continue
        logging.info(f"Searching for <= {cited_count} reported citations for {eid}.")

        # Search for citing Works within specific year range
        cite_query = build_query(f'REF({paper.eid})', args.cite_start, args.cite_end)
        citing_search = ScopusSearch(cite_query)
        
        if not citing_search.results:
            logging.info(f'No citing works found for {paper.eid}.')
            continue
    
        logging.info(f"Found {len(citing_search.results)} citing works for {paper.eid}.")

        # Process citing Works
        work_citations_folder = year_folder / f"citing_{eid}"
        false_positives = 0
        for c_eid in citing_search.get_eids():
            citing_paper = fetch_abstract(c_eid)
            if not citing_paper:
                continue
            if not is_citing(citing_paper, eid):
                logging.debug(f"False positive: {citing_paper.eid} does not cite {eid}.")
                false_positives += 1
                continue

            # Organize citations by their own publication year
            c_year = citing_paper.coverDate[:4] if citing_paper.coverDate else "Unknown"
            c_year_folder = work_citations_folder / c_year
            save_json(c_year_folder, c_eid, scopus_cache_base=args.scopus_cache)
        logging.info(f"Found {false_positives} FP citing works for {eid} (year range: {args.cite_start} - {args.cite_end})")

    logging.info(f"Extraction completed for {args.author_id or args.orcid}.")

if __name__ == '__main__':
    main()