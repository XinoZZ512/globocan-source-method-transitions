from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from author_metadata import load_author_metadata

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
SUB = PROJECT / "manuscript" / "ijc_submission"
FIG = PROJECT / "results" / "figures"
TABLES = PROJECT / "results" / "tables_v2"
AUDIT = PROJECT / "results" / "audit"


def wc(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check(name: str, condition: bool, blockers: list[str], detail: str = "") -> dict:
    if not condition:
        blockers.append(name)
    return {"pass": bool(condition), "detail": detail}


def valid_orcid(value: str) -> bool:
    compact = value.replace("-", "").upper()
    if len(compact) != 16 or not re.fullmatch(r"[0-9]{15}[0-9X]", compact):
        return False
    total = 0
    for digit in compact[:15]:
        total = (total + int(digit)) * 2
    remainder = (12 - total % 11) % 11
    check_digit = "X" if remainder == 10 else str(remainder)
    return compact[-1] == check_digit


def main() -> None:
    blockers: list[str] = []
    slash_user_path = "C:" + "/Users/"
    backslash_user_path = "C:" + "\\Users"
    clean = SUB / "IJC_clean_manuscript.md"
    title = SUB / "IJC_title_page.md"
    abstract = ""
    body = ""
    text = clean.read_text(encoding="utf-8") if clean.exists() else ""
    if "## Abstract" in text and "## Introduction" in text:
        abstract = text.split("## Abstract", 1)[1].split("## Introduction", 1)[0]
    if "## Introduction" in text and "## Data and code availability" in text:
        body = text.split("## Introduction", 1)[1].split("## Data and code availability", 1)[0]
    results = {
        "abstract_unstructured_under_250": check("abstract_unstructured_under_250", wc(abstract) <= 250 and not re.search(r"^### ", abstract, re.M), blockers, str(wc(abstract))),
        "body_under_5000": check("body_under_5000", wc(body) <= 5000, blockers, str(wc(body))),
        "main_display_items_six": check("main_display_items_six", all(any(FIG.glob(f"Figure_{i}_*.pdf")) for i in range(1, 5)) and (TABLES / "Table_1_final_exposure_summary.csv").exists() and (TABLES / "Table_2_adjusted_effects_and_diagnostics.csv").exists(), blockers),
        "references_under_50": check("references_under_50", len(re.findall(r"(?m)^\d+\. ", text.split("## References", 1)[-1])) <= 50, blockers),
        "novelty_under_75": check("novelty_under_75", wc((SUB / "IJC_novelty_and_impact.md").read_text(encoding="utf-8")) <= 75, blockers),
        "complete_reference_manifest": check("complete_reference_manifest", bool((AUDIT / "ijc_references.json").exists()) and not json.loads((AUDIT / "ijc_references.json").read_text(encoding="utf-8")).get("errors"), blockers),
        "claim_ledger_resolved": check("claim_ledger_resolved", (SUB / "IJC_claim_to_reference_ledger.csv").exists() and not any(term in (SUB / "IJC_claim_to_reference_ledger.csv").read_text(encoding="utf-8") for term in ["To be checked", "Primary official source required"]), blockers),
        "required_comparators": check("required_comparators", "10.1002/ijc.70773" in text and "10.1002/ijc.70719" in text, blockers),
        "locked_effects": check("locked_effects", "+1.468" in text and "-0.786" in text and "-1.464" in text and "-4.989" in text, blockers),
        "no_superseded_effects": check("no_superseded_effects", ("0." + "34 pp") not in text and ("11." + "22 pp") not in text and ("0." + "34 percentage") not in text and ("11." + "22 percentage") not in text, blockers),
        "no_journal_neutral_language": check("no_journal_neutral_language", not any(term in text.lower() for term in ["journal" + "-neutral", "pending journal selection", "submission_candidate=true"]), blockers),
        "no_absolute_paths": check("no_absolute_paths", not re.search(r"[A-Za-z]:\\|" + re.escape(slash_user_path) + "|" + re.escape(backslash_user_path), text), blockers),
    }
    data = load_author_metadata()
    xianzhi = next((a for a in data["authors"] if a["name"] == "Xianzhi Zhou"), {})
    results["author_metadata"] = check("author_metadata", len(data["authors"]) == 12 and xianzhi.get("orcid") == "0009-0003-4092-3133" and sum(bool(a.get("corresponding")) for a in data["authors"]) == 1, blockers)
    results["orcid_checksums"] = check("orcid_checksums", all(valid_orcid(a.get("orcid", "")) for a in data["authors"]), blockers)
    required_figures = [f"Figure_{i}_" for i in range(1, 5)]
    results["figure_files"] = check("figure_files", all(any(FIG.glob(f"{prefix}*")) for prefix in required_figures) and any(FIG.glob("Supplementary_Figure_S1*")), blockers)
    f3 = TABLES / "figure3_cancer_heatmap_data.csv"
    f3_ok = False
    if f3.exists():
        d = pd.read_csv(f3)
        f3_ok = len(d) == 128 and int(d["median_aspd"].notna().sum()) == 127
    results["figure3_structure"] = check("figure3_structure", f3_ok, blockers)
    lowess_manifest = TABLES / "lowess_source_manifest.txt"
    results["lowess_manifest"] = check("lowess_manifest", lowess_manifest.exists() and "0.6" in lowess_manifest.read_text(encoding="utf-8"), blockers)
    profile = (PROJECT / "config" / "journal_profile.yml").read_text(encoding="utf-8")
    results["repository_release"] = check("repository_release", "github_url: null" not in profile and "zenodo_doi: null" not in profile, blockers, "Requires authenticated public release")
    results["public_package"] = check("public_package", (ROOT / "outputs" / "PUBLIC_REPRODUCIBILITY_RELEASE.zip").exists(), blockers)
    results["upload_package"] = check("upload_package", (ROOT / "outputs" / "IJC_SUBMISSION_UPLOAD.zip").exists(), blockers)
    status = {
        "status": "PASS" if not blockers else "BLOCKED",
        "analysis_candidate": True,
        "ijc_submission_candidate": not blockers,
        "blockers": blockers,
        "checks": results,
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "ijc_integrity.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if blockers:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
