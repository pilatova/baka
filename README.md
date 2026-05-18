## Requirements
Install the required libraries from `requirements.txt` into a new environment.

```
# Create and activate conda environment
conda create -n scopus-data python=3.11
conda activate scopus-data

# Install dependencies
pip install -r requirements.txt
```
# Overview

`download_data.py`: A script to download author publication data and citation information from the Scopus API using `pybliometrics`.

`process_data.py`: A script to compute the DRSC from the downloaded data.

Before running the main downloader, we used these utilities to resolve author identifiers from an input TSV file. Both tools read from standard input (stdin) and write out to standard output (stdout).

`get_orcid.py`: A utility using the third-party `orcidfetch` library to attempt matching researcher names and affiliations to an ORCID. Appends orcid, confidence, and method columns to the original dataset. 

- Limitations: Features low success rates and contains safety checks to catch internal library crashes.

- Usage:

```
python get_orcid.py --name_col "authfull" --affil_col "inst_name" < input.tsv > output_orcids.tsv
```

`get_scopus_id.py`: Queries the Scopus Author API via `pybliometrics` to find Scopus IDs for researchers in the Mathematics subject area. Outputs three columns: the original name column, the affiliation column, and a new scopus_id column. If multiple possible matching IDs are found, they are returned separated by a semicolon (;).

- Usage:

```
python get_scopus_id.py --name_col "authfull" --affil_col "inst_name" < input.tsv > scopus_ids_only.tsv
```
## Download

### Prerequisites
It's necessary to obtain an Elsevier Scopus API key by registering at https://dev.elsevier.com/.

The `pybliometrics` library requires an initial setup to store your API key and configuration. The script will automatically trigger `pybliometrics.init()` on its first run to guide you through this setup if it hasn't been done yet. You can read more about it in the pybliometrics configuration documentation.

### Usage
The script requires either an `--orcid` or an `--author-id` to run.

```
python download_data.py --orcid 0000-0002-1825-0097 --work-start 2015 --work-end 2020 --cite-start 2021
```

### Available Arguments
`--orcid`: Author's ORCID (Mutually exclusive with `--author-id`).

`--author-id`: Author's Scopus ID numerical part (Mutually exclusive with `--orcid`).

`--work-start` (Optional): Author publication start year (inclusive).

`--work-end` (Optional): Author publication end year (exclusive).

`--cite-start` (Optional): Citing works start year filter.

`--cite-end` (Optional): Citing works end year filter.

`--cache-dir` (Optional): Storage directory (Default: `./authors_cache`).

--scopus-cache (Optional): Path to your local `pybliometrics` FULL abstract cache.

### Storage & Directory Structure
To save storage space, this script creates directory hierarchies and uses symbolic links pointing directly to your local `pybliometrics` cache files.

Note on Cache Format: This script expects the local `pybliometrics` cache to store abstracts as uncompressed plain-text JSON files named after their EID.

Data is automatically organized by the author's publication year, and citing papers are nested inside a dedicated folder organized by their own respective publication years:

```
authors_cache/                               # Root cache directory (--cache-dir)
└── 0000-0002-1825-0097/                     # Author folder (ORCID or Author ID)
    └── 2018/                                # Author's publication year
        ├── 2-s2.0-85101345678.json          # Symlink to main publication metadata
        └── citing_2-s2.0-85101345678/       # Folder for citing works targeting this paper
            └── 2021/                        # Citation publication year
                └── 2-s2.0-85198765432.json  # Symlink to citing publication
```
### Error Handling & Limitations
- Quota Limits (HTTP 429): If you hit Elsevier's quota limits while fetching data, the script will log a critical error and exit cleanly to prevent spamming the API.

- Authentication (HTTP 401/403): If your API key or institutional VPN connection fails, the script will log a critical error and stop.

- False Positives: The script uses Scopus's `REF()` query to find citations. Because this search can sometimes yield false positives, the script strictly validates each citing paper's reference list before generating a symlink.

## DRSC Calculation

The script processes stored JSON data for authors' citing works to compute their DRSC. It supports calculating both a single parameter metric (with full audit trails) or multi-parameter metric arrays across variable p-values. The program recursively finds .json papers stored within nested author folder paths containing subdirectories that match the pattern citing*. It then calculates the score as described in the thesis.
 
### Available Arguments
`--au-id`: Specifies a single target researcher folder to parse (Mutually exclusive with `--id-file`).

`--id-file`: Path to a text document containing multiple researcher ids separated by newline characters (Mutually exclusive with `--au-id`).

`--directory` (Optional): Folder path containing cached JSON files (Default: ./authors_cache).

`--p-values` (Optional): Space-separated set of custom tunable parameter values to compute (Default: [1.0]).

`--output` (Optional): File path destination to write calculated values (Default: drsc_results.jsonl).

### Usage
```
# Calculate metrics for a single author with default p=1.0 parameter
python3 process_data.py --au-id 0000-0002-9811-9717 --output results.jsonl
```

```
# Process a batch file of researcher IDs tracking a series of p weights
python3 process_data.py --id-file target_researchers.txt --p-values 0 0.5 1 2 --output multidrs.jsonl
```
### Output JSON Lines Format
The script records data points as uniform line-separated JSON files depending on how many custom parameter configurations you supply.

#### Single-Parameter Variant
When providing a single p parameter (e.g. `--p-values 1.0`), the program writes a list of DRSC values computed with each added paper along with dictionary mappings for author and venue names:

```
{
  "au_id": "0000-0002-9811-9717",
  "p": 1.0,
  "total_drs": 14.502,
  "citing_count": 25,
  "lookup": {
    "venues": { "28773": "Journal of Citation Metrics", etc.},
    "authors": { "0000-0001-2345-6789": "Smith, John" , etc.}
  },
  "audit": [
    {
      "eid": "2-s2.0-85203818162",
      "date": "2024-03-12",
      "order": 0,
      "r": 0,
      "score": 1.0,
      "penalty_vars": []
    }, etc.
  ]
}
```

#### Multi-Parameter Variant
When computing DRSC for multiple p values at once, the output structure simplifies to save disk space:

```
{
  "au_id": "0000-0002-9811-9717",
  "p_values": [0.0, 0.5, 1.0, 2.0],
  "drs_vector": [25.0, 18.234, 14.502, 9.112],
  "citing_count": 25
}
```