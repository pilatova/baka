#!/usr/bin/env python3

from process_data import calculate_DRS

def print_DRS_table(sorted_works, drs, scores, rs, determining_variables, author_names, venue_names):
    print(f"{'#'}\t{'Authors'}\t{'Venue'}\t{'Max prior r'}\t{'Contribution 1/(r+1)'}")
        
    for i, work in enumerate(sorted_works):
        author_ids = work['authors']
        author_last_names = []
        for author_id in author_ids:
            _, last_name = author_names[author_id]
            author_last_names.append(last_name)
        authors_str = ", ".join(author_last_names)
        
        venue_str = work['venue_name']
        max_r = rs[i]
        
        explanations = []
        for var_type, var_id in determining_variables[i]:
            if var_type == 'author':
                _, last_name = author_names[var_id]
                explanations.append(last_name)
            else:  # venue
                explanations.append(venue_names[var_id])
        
        explanation_str = f"({', '.join(explanations)})"
        max_r_str = f"{max_r} {explanation_str if len(explanations) > 0 else ''}"
        
        score = scores[i]
        score_str = f"{score:.6f}"
        
        print(f"{i + 1}\t{authors_str}\t{venue_str}\t{max_r_str}\t{score_str}")
    
    print(f"{'DRS total:'}\t{drs:.6f}")

def example_test():
    citing_works = [
        {
            'eid': 123, 'title': '1',
            'authors': {1: ('', 'Smith')},
            'venue_id': 1, 'venue_name': 'J1'
        },
        {
            'eid': 124, 'title': '2',
            'authors': {2: ('', 'Jones')},
            'venue_id': 1, 'venue_name': 'J1'
        },
        {
            'eid': 125, 'title': '3',
            'authors': {1: ('', 'Smith'), 3: ('', 'Lee')},
            'venue_id': 2, 'venue_name': 'J2'
        },
        {
            'eid': 126, 'title': '4',
            'authors': {3: ('', 'Lee')},
            'venue_id': 1, 'venue_name': 'J1'
        },
        {
            'eid': 127, 'title': '5',
            'authors': {4: ('', 'Kim')},
            'venue_id': 3, 'venue_name': 'J3'
        },
        {
            'eid': 128, 'title': '6',
            'authors': {1: ('', 'Smith')},
            'venue_id': 1, 'venue_name': 'J1'
        }
    ]
    x = calculate_DRS(citing_works)
    print_DRS_table(citing_works, *x)

def edge_case_tests():
    # Paper 1 & 2 share a venue. Paper 2 & 3 share an author.
    test_works = [
        {'eid': 2, 'publication_date': '2024-01-01', 'venue_id': 'V1', 'venue_name': 'X', 'authors': {'A1': 'Smith'}},
        {'eid': 1, 'publication_date': '2024-01-01', 'venue_id': 'V1', 'venue_name': 'X', 'authors': {'A2': 'Jones'}},
        {'eid': 3, 'publication_date': '2024-01-02', 'venue_id': 'V2', 'venue_name': 'Z', 'authors': {'A2': 'Jones'}},
    ]

    sorted_works = sorted(test_works, key=lambda x: (x['publication_date'], x['eid']))
    assert sorted_works[0]['eid'] == 1
    
    score_p0, _, _, _, _, _ = calculate_DRS(sorted_works, p=0)
    assert score_p0 == 3.0, f"Expected 3.0, got {score_p0}"

    # 3. Test p=1
    # Paper 1 (A): r=0 -> 1/1 = 1.0
    # Paper 2 (B): r=1 (Venue V1) -> 1/2 = 0.5
    # Paper 3 (C): r=1 (Author A2) -> 1/2 = 0.5
    # Total = 2.0
    score_p1, _, rs, _, _, _ = calculate_DRS(sorted_works, p=1)
    assert score_p1 == 2.0
    assert rs == [0, 1, 1]

    # 4. Test p=large (Unique Count)
    # Only Paper 1 is new across all variables. Papers 2 and 3 repeat something.
    score_p100, _, _, _, _, _ = calculate_DRS(sorted_works, p=100)
    assert round(score_p100, 1) == 1.0

    print("Edge cases passed")

if __name__ == '__main__':
    example_test()
    edge_case_tests()