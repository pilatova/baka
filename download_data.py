#!/usr/bin/env python3

import argparse
import requests
import os
import json

import pybliometrics
from pybliometrics.scopus import ScopusSearch
from API_KEY import KEY


abstract_retrieval_url = 'https://api.elsevier.com/content/abstract/eid/'
headers = {'Accept': 'application/json', 'X-ELS-APIKey': KEY}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--orcid', help='Author\'s ORCID identifier', required=True)
    parser.add_argument('--start-year', '-s', type=int, help='Start year range for publications')
    parser.add_argument('--end-year', '-e', type=int, help='End year range for publications')
    parser.add_argument('--cache-dir', default='./authors_cache', help='Cache directory for storing data')
    args = parser.parse_args()
    pybliometrics.init()
    
    query = f'ORCID({args.orcid})'
    if args.start_year:
        query += f' AND PUBYEAR AFT {args.start_year - 1}'
    if args.end_year:
        query += f' AND PUBYEAR BEF {args.end_year}'

    orcid_search = ScopusSearch(query)
    assert orcid_search.results, f'Found no author with ORCID {args.orcid}'
    eids = orcid_search.get_eids()
    
    author_folder_path = os.path.join(args.cache_dir, args.orcid)
    if not os.path.exists(author_folder_path):
        os.makedirs(author_folder_path)

    for eid in eids:
        abstract_data = requests.get(f'{abstract_retrieval_url}{eid}', 
                                     headers=headers).json() \
                                        .get('abstracts-retrieval-response')
        
        file_path = os.path.join(author_folder_path, f'{eid}.json')
        with open(file_path, 'w') as f:
            json.dump(abstract_data, f, ensure_ascii=False, indent=2)

        citedby_count = int(abstract_data.get('coredata').get('citedby-count'))
        if citedby_count == 0:
            continue
        citation_title = abstract_data.get('item').get('bibrecord') \
            .get('head').get('citation-title')

        citing_works = ScopusSearch(f'REFTITLE("{citation_title}")').get_eids()
        assert len(citing_works) >= citedby_count, f'Not all counted citing works were retrieved for "{citation_title}"'
        
        work_folder_path = os.path.join(author_folder_path, eid)
        if not os.path.exists(work_folder_path):
            os.makedirs(work_folder_path)

        for citing_eid in citing_works:
            citing_abstract_data = requests.get(
                f'{abstract_retrieval_url}{citing_eid}', headers=headers) \
                    .json().get('abstracts-retrieval-response')
            
            # if the reported count of citing works isn't equal it means
            # there were probably some false positives in the search results, 
            # so we have to check if each citing work's list of references 
            # contains the wanted work
            write_file = True
            if citedby_count < len(citing_works):
                cited_works = citing_abstract_data.get('item').get('bibrecord') \
                    .get('tail').get('bibliography').get('reference')
                
                for cited_work in cited_works:
                    cited_eid = '2-s2.0-'

                    # this returns either a list of dictionaries or a dictionary,
                    # we want the dictionary with '@idtype': 'SGR' which contains 
                    # the numerical part of an eid
                    itemid = cited_work.get('ref-info').get('refd-itemidlist').get('itemid')
                    if isinstance(itemid, dict):
                        itemid = [itemid]
                    find_sgr = [itid.get('$') for itid in itemid if itid.get('@idtype') == 'SGR']
                    cited_eid += find_sgr[0]
                    if cited_eid == eid:
                        write_file = True
                        break
                else:
                    citedby_count += 1
                    write_file = False
                    continue

            if write_file:
                citing_file_path = os.path.join(work_folder_path, f'{citing_eid}.json')
                with open(citing_file_path, 'w') as f:
                    json.dump(citing_abstract_data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
