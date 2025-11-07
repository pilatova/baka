`download_py`: a script to download author publication data and citation information from Scopus API.

### Prerequisites

It's necessary to obtain an Elsevier Scopus API key by registering at https://dev.elsevier.com/.
Then put it in a file named `API_KEY.py` in variable `KEY` in the same folder as the script.
The pybliometrics library will also require this value be present in its configuration file (https://pybliometrics.readthedocs.io/en/stable/configuration.html).

Install the required libraries from `requirements.txt` into a new environment.
```
# Create and activate conda environment
conda create -n scopus-data python=3.11
conda activate scopus-data

# Install dependencies
pip install -r requirements.txt
```

### Usage

`python download_data.py --orcid 0000-0002-1825-0097 --start-year 2015 --end-year 2020`

Downloads all available publications of author with ORCID 0000-0002-1825-0097 published in year range [2015, 2020).

The data in the form of json files (as provided by Scopus) is stored in the following directory structure (created in the current working directory if not configured otherwise):

```
authors_cache/                         # Root cache directory (configurable)
└── 0000-0001-2345-6789/               # Author folder named by ORCID
    ├── 2-s2.0-85101345678.json        # Main publication metadata
    ├── 2-s2.0-85102345678.json
    └── 2-s2.0-85101345678/            # Folder for citing works
        ├── 2-s2.0-85198765432.json    # Citing publication 1
        └── 2-s2.0-85195543210.json    # Citing publication 2
```

Each json file should contain (among other information):

- Title, authors, publication venue

- Abstract, keywords, references count

- Citation count, publication date

- DOI and other identifiers

### Limitations

If you request the data of a particularly profilic and/or popular author, it's possible to hit the quota limit set by Elsevier. The program sadly doesn't contain a mechanism to circumvent this.
