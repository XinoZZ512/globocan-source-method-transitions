from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "results" / "audit"

# Ordered anchors are deliberately explicit. Search-engine results are never used
# as bibliographic authority for the active manuscript.
IDENTIFIERS = [
    ("doi", "10.1002/ijc.70773"), ("doi", "10.3322/caac.21834"),
    ("doi", "10.3322/caac.70090"), ("doi", "10.1002/ijc.31937"),
    ("pmid", "25220842"), ("doi", "10.2471/blt.15.164384"),
    ("pmid", "33538338"), ("pmid", "30207593"),
    ("doi", "10.3322/caac.21262"), ("doi", "10.1002/ijc.1440"),
    ("doi", "10.1136/jcp.53.2.164-a"), ("doi", "10.3322/canjclin.55.2.74"),
    ("pmid", "21296855"), ("doi", "10.1038/sj.bjc.6602323"),
    ("pmid", "29395269"), ("pmid", "28410997"),
    ("doi", "10.7196/samj.8858"), ("doi", "10.1016/S0959-8049(96)00492-3"),
    ("doi", "10.1186/s40880-017-0234-3"), ("doi", "10.3402/gha.v7.25931"),
    ("doi", "10.1016/S2214-109X(16)30146-2"), ("doi", "10.1371/journal.pone.0197047"),
    ("doi", "10.1186/s12963-016-0074-4"), ("doi", "10.3402/gha.v9.32795"),
    ("doi", "10.1097/00008469-200110000-00005"),
    ("doi", "10.33396/1728-0869-2017-5-54-62"),
    ("doi", "10.1093/bib/bbs078"),
    ("doi", "10.1016/S0140-6736(12)61728-0"), ("pmid", "35039287"),
    ("doi", "10.1136/bmj.39386.490150.94"), ("doi", "10.1371/journal.pmed.1001885"),
    ("doi", "10.2307/1912934"), ("doi", "10.1093/biomet/73.1.13"),
    ("doi", "10.1111/j.2517-6161.1995.tb02031.x"),
    ("doi", "10.1002/ijc.70719"),
]


def get_json(url: str) -> dict:
    response = requests.get(url, timeout=30, headers={"User-Agent": "GLOBOCAN-source-method/1.0"})
    response.raise_for_status()
    return response.json()


def crossref(doi: str) -> dict:
    return get_json(f"https://api.crossref.org/works/{doi}")["message"]


def europe_pmc(pmid: str) -> dict:
    payload = get_json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        f"?query=EXT_ID:{pmid}%20AND%20SRC:MED&resultType=core&format=json"
    )
    results = payload.get("resultList", {}).get("result", [])
    if not results:
        raise RuntimeError(f"PMID not found: {pmid}")
    return results[0]


def normalize_crossref(item: dict, identifier: str) -> dict:
    authors = []
    for author in item.get("author", []):
        family = author.get("family", "").strip()
        initials = "".join(part[:1] for part in re.split(r"[-\s]+", author.get("given", "")) if part)
        if family:
            authors.append(f"{family} {initials}".strip())
    container = (item.get("container-title") or [""])[0]
    date_parts = item.get("published-print", item.get("published-online", item.get("issued", {}))).get("date-parts", [[""]])
    year = date_parts[0][0] if date_parts and date_parts[0] else ""
    # Crossref omits the group authors for the original STROBE record.
    if identifier.lower() == "10.1136/bmj.39386.490150.94" and not authors:
        authors = ["von Elm E", "Altman DG", "Egger M", "Pocock SJ", "Gøtzsche PC", "Vandenbroucke JP"]
    return {
        "identifier": identifier,
        "doi": item.get("DOI", identifier).lower(),
        "pmid": "",
        "title": " ".join((item.get("title") or [""])[0].split()),
        "authors": authors,
        "journal": container,
        "year": year,
        "volume": str(item.get("volume", "")),
        "issue": str(item.get("issue", "")),
        "pages": str(item.get("page", "")),
        "article_number": str(item.get("article-number", "")),
        "source": "Crossref",
    }


def normalize_pmid(item: dict, identifier: str) -> dict:
    doi = str(item.get("doi", "")).lower()
    authors = [
        f"{author.get('lastName', '').strip()} {author.get('initials', '').strip()}".strip()
        for author in (item.get("authorList", {}) or {}).get("author", [])
        if author.get("lastName")
    ]
    journal_info = item.get("journalInfo", {}) or {}
    issue = journal_info.get("issue", "")
    return {
        "identifier": identifier,
        "doi": doi,
        "pmid": str(item.get("pmid", identifier)),
        "title": " ".join(str(item.get("title", "")).split()),
        "authors": authors,
        "journal": str((journal_info.get("journal", {}) or {}).get("title", "")),
        "year": str(item.get("pubYear", "")),
        "volume": str(journal_info.get("volume", "")),
        "issue": str(issue),
        "pages": str(item.get("pageInfo", "")),
        "article_number": "",
        "source": "Europe PMC",
    }


def main() -> None:
    records = []
    errors = []
    for kind, value in IDENTIFIERS:
        try:
            item = crossref(value) if kind == "doi" else europe_pmc(value)
            record = normalize_crossref(item, value) if kind == "doi" else normalize_pmid(item, value)
            if kind == "pmid" and not record["doi"]:
                errors.append({"identifier": value, "error": "PMID has no DOI; author metadata require PubMed XML verification"})
            records.append(record)
        except Exception as exc:
            errors.append({"identifier": value, "error": str(exc)})
        time.sleep(0.15)
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"status": "PASS" if not errors else "BLOCKED", "records": records, "errors": errors}
    (OUT / "ijc_references.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "records": len(records), "errors": errors}, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
