from __future__ import annotations

import json
import re
from pathlib import Path

from author_metadata import affiliations_block, author_line, credit_status, load_author_metadata, orcid_block

PROJECT = Path(__file__).resolve().parents[1]
MAN = PROJECT / "manuscript"
OUT = MAN / "ijc_submission"
BASE = MAN / "master_manuscript_v2.md"
REFS = PROJECT / "results" / "audit" / "ijc_references.json"


def repository_statement() -> str:
    profile = (PROJECT / "config" / "journal_profile.yml").read_text(encoding="utf-8")
    github_match = re.search(r"^github_url:\s*(\S+)$", profile, re.M)
    zenodo_match = re.search(r"^zenodo_doi:\s*(\S+)$", profile, re.M)
    github = github_match.group(1) if github_match else "null"
    zenodo = zenodo_match.group(1) if zenodo_match else "null"
    if github != "null" and zenodo != "null":
        return f"Code, derived tables, figure source data, hashes, and official-data retrieval instructions are available at {github} and the archived Zenodo release {zenodo}. Bulk GCO files and restricted human-review files are not redistributed."
    return "The public reproducibility release will be deposited in a versioned GitHub repository and archived with Zenodo before submission. It will contain code, derived tables, figure source data, hashes, and official-data retrieval instructions. Bulk GCO files and restricted human-review files will not be redistributed."


def words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def vancouver(record: dict, number: int) -> str:
    authors = record.get("authors", [])
    if len(authors) > 6:
        author_text = ", ".join(authors[:6]) + ", et al."
    else:
        author_text = ", ".join(authors)
    title = record.get("title", "").rstrip(".")
    journal = record.get("journal", "")
    year = record.get("year", "")
    volume = record.get("volume", "")
    issue = record.get("issue", "")
    locator = record.get("pages") or record.get("article_number") or ""
    if volume and issue and locator:
        citation = f"{journal}. {year};{volume}({issue}):{locator}."
    elif volume and locator:
        citation = f"{journal}. {year};{volume}:{locator}."
    elif volume:
        citation = f"{journal}. {year};{volume}."
    else:
        citation = f"{journal}. {year}."
    doi = record.get("doi", "")
    pmid = record.get("pmid", "")
    identifiers = f" doi:{doi}." if doi else (f" PMID:{pmid}." if pmid else "")
    return f"{number}. {author_text}. {title}. {citation}{identifiers}"


def reference_text() -> tuple[str, list[dict]]:
    payload = json.loads(REFS.read_text(encoding="utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"Reference curation is blocked: {payload['errors']}")
    records = payload.get("records", [])
    required = ["title", "journal", "year", "authors"]
    incomplete = [r.get("identifier") for r in records if any(not r.get(k) for k in required)]
    if incomplete:
        raise RuntimeError(f"Incomplete bibliographic records: {incomplete}")
    return "\n".join(vancouver(record, i) for i, record in enumerate(records, start=1)), records


def abstract() -> str:
    return (
        "GLOBOCAN estimates are outputs of different estimation systems, so a difference between releases "
        "cannot automatically be interpreted as a temporal change in cancer burden. We examined whether "
        "revisions between GLOBOCAN 2022 and 2024 were associated with substantive changes in estimation "
        "source or method. We assembled data for 185 countries or areas, 32 common cancers, 55 "
        "applicable cancer-sex combinations, and 20,350 incidence and mortality cells. Source-method metadata "
        "were processed by a sealed automated preclassification, independently classified by 2 blinded human "
        "reviewers, and adjudicated by a third author. The outcome was country median "
        "symmetric absolute percentage difference among cells with a 2022 ASR greater than 0.5 per 100,000. "
        "Incidence and mortality were modelled separately with parsimonious HC3-robust regressions and "
        "2,000 region-stratified country bootstrap samples. The final exposure included 207 administrative or "
        "wording-only changes, 98 substantive changes at the same directness, 37 shifts toward more indirect "
        "sources, 27 shifts toward more direct sources, and 1 unclassifiable pair. Reviewer agreement was "
        "0.868, with six-category Cohen kappa 0.777 and severity-weighted kappa 0.857. The adjusted marginal "
        "difference was +1.468 percentage points for incidence (95% CI -1.464 to 4.360; permutation P=0.486) "
        "and -0.786 percentage points for mortality (95% CI -4.989 to 3.717; permutation P=0.977). External "
        "registry indicators were treated as convergent checks, not truth labels. In this two-release comparison, "
        "substantive source-method transitions were not associated with a separated revision magnitude. "
        "Retaining source-method provenance is therefore important when comparing GLOBOCAN releases."
    )


def title_page(data: dict) -> str:
    authors = author_line(data).replace(",**", "").replace(",***", "")
    return f"""# Title Page

## Title

Estimation-Method Transitions and Cross-Edition Revisions in GLOBOCAN Estimates: A Source-Aware Analysis of 32 Cancers in 185 Countries

## Short title

Source-method transitions in GLOBOCAN

## Authors

{authors}

## Affiliations

{affiliations_block(data)}

## Corresponding author

Hui Zhang, The First Clinical College, Changsha Medical University, Changsha, Hunan 410219, China. E-mail: 515009366@qq.com. ORCID: 0000-0003-4513-5606.

## ORCID iDs

{orcid_block(data)}

## Novelty and Impact

This study links cross-edition GLOBOCAN revisions to independently adjudicated changes in source-method provenance across 185 countries and 32 cancers. It separates wording or coding updates from substantive shifts in directness, quantifies uncertainty from human classification, and tests associations with revision magnitude using parsimonious robust models. The framework helps users interpret release differences without treating them as temporal trends or accuracy rankings.

## Article type

Research Article

## Funding

{data['funding']}

## Conflict of interest

{data['conflict_of_interest']}

## Ethics

This aggregated secondary analysis used publicly available data and did not involve identifiable human participants.

## Data and code availability

{repository_statement()}

## CRediT author contributions

{credit_status(data)}

## AI use disclosure

AI assistance supported deterministic preclassification design, software scaffolding, statistical implementation, figure generation, and language editing. No external LLM produced the sealed row-level classifications. The preclassification was withheld from first-round reviewers and did not determine the final exposure. The authors retain responsibility for all data, analyses, interpretations, references, and submission materials.
"""


def main() -> None:
    data = load_author_metadata()
    source = BASE.read_text(encoding="utf-8")
    start = source.index("## Introduction")
    end = source.index("## Data and code availability")
    body = source[start:end].replace("## Methods", "## Materials and Methods")
    body = body.replace("Python and R implementations were maintained independently for key calculations [27-30].", "Python and R implementations were maintained independently for key calculations. Reporting follows STROBE principles, with RECORD items considered where applicable to secondary data [30,31].")
    body = body.replace("Reporting follows STROBE principles, with RECORD items marked where applicable to secondary data.", "")
    body = body.replace(
        "Recent work quantified the magnitude and distribution of revisions across consecutive GLOBOCAN releases [1].",
        "Recent work quantified the magnitude and distribution of revisions across consecutive GLOBOCAN releases [1]. A related IJC study examined consistency in genitourinary cancer estimates [35]. Our study addresses a different unit of analysis: source-method provenance across 32 cancers and 185 countries."
    )
    legacy_sentence = "The " + "journal" + "-neutral candidate package has passed the computational and author-confirmation gates; journal-specific formatting and submission-system fields remain pending journal selection."
    body = body.replace(legacy_sentence, "The final release will include code, derived tables, figure source data, hashes, and official-data retrieval instructions.")
    body = body.replace(
        "The sealed automated output and the earlier automated rule remained audit artifacts rather than primary exposure definitions.",
        "The sealed automated output and the earlier automated rule remained audit artifacts rather than primary exposure definitions. The final exposure structure is shown in Figure 1 and summarized in Table 1."
    )
    body = body.replace(
        "The permutation comparisons did not provide evidence of a separated transition-associated revision magnitude.",
        "The permutation comparisons did not provide evidence of a separated transition-associated revision magnitude. Country-level revision patterns are shown in Figure 2, cancer-specific distributions in Figure 3, and model estimates and diagnostics in Table 2."
    )
    body = body.replace(
        "Differences in reference year and missingness limit the interpretation of both comparisons.",
        "Differences in reference year and missingness limit the interpretation of both comparisons. These convergent checks are shown in Figure 4."
    )
    body = body.replace(
        "## Conclusion\n\n",
        "## Conclusion\n\n"
    )
    refs, records = reference_text()
    abstract_text = abstract()
    if words(abstract_text) > 250:
        raise RuntimeError(f"Abstract exceeds IJC limit: {words(abstract_text)} words")
    OUT.mkdir(parents=True, exist_ok=True)
    manuscript = (
        "# Estimation-Method Transitions and Cross-Edition Revisions in GLOBOCAN Estimates: A Source-Aware Analysis of 32 Cancers in 185 Countries\n\n"
        "## Abstract\n\n" + abstract_text + "\n\n" + body +
        "## Data and code availability\n\n" + repository_statement() + "\n\n"
        "## Statements\n\n"
        f"Ethics: This aggregated secondary analysis used publicly available data and did not involve identifiable human participants. Funding: {data['funding']} Conflict of interest: {data['conflict_of_interest']} CRediT contributions: {credit_status(data)} AI use disclosure: AI assistance supported deterministic preclassification design, software scaffolding, statistical implementation, figure generation, and language editing. No external LLM produced the sealed row-level classifications; human authors retain responsibility for all final content.\n\n"
        "## References\n\n" + refs + "\n"
    )
    (OUT / "IJC_clean_manuscript.md").write_text(manuscript, encoding="utf-8")
    (OUT / "IJC_title_page.md").write_text(title_page(data), encoding="utf-8")
    (OUT / "IJC_novelty_and_impact.md").write_text(
        "This study links cross-edition GLOBOCAN revisions to independently adjudicated changes in source-method provenance across 185 countries and 32 cancers. It separates wording or coding updates from substantive shifts in directness, quantifies uncertainty from human classification, and tests associations with revision magnitude using parsimonious robust models. The framework helps users interpret release differences without treating them as temporal trends or accuracy rankings.\n",
        encoding="utf-8",
    )
    (OUT / "IJC_reference_manifest.json").write_text(json.dumps({"count": len(records), "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"abstract_words": words(abstract_text), "body_words": words(body), "references": len(records), "output": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
