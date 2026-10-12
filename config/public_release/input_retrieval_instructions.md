# Public input retrieval

The public release intentionally excludes GCO bulk estimate files and reviewer-level source-method ratings. Recreate the analysis inputs from the official GCO sources and retain the listed SHA-256 values locally before running the pipeline.

## Official method dictionaries

- GLOBOCAN 2022: `https://gco-api.iarc.fr/api/globocan/v3/2022/meta/method/all/`
- GLOBOCAN 2024: `https://gco-api.iarc.fr/api/globocan/v3/2024/meta/method/all/`

The downloaded method dictionaries used for this release had SHA-256 values `00aeaaca2657a1c7ae001eece5a0772bdd5695ba0015511a52ddd7590981c441` (2022) and `273819c74e5bc25f2dba4605d64de59772bc47650c6d84fca298972803bedac4` (2024).

## GCO estimate and source-method inputs

Obtain the corresponding 2022 and 2024 estimate, country, cancer, and source-method CSV exports from the official GCO release/API under the applicable access and redistribution terms. Do not commit those files to this repository. The private analysis manifest records their byte counts and SHA-256 values for local verification.

## External indicators

The WHO PBCR and cause-of-death completeness inputs are retrieved from the official WHO data endpoints identified in the private project configuration. Re-download them on the analysis date and record the retrieval date and SHA-256 in the local provenance manifest.

## Reproduction boundary

This repository contains only code, aggregate derived tables, figure source data, bibliographic metadata, and configuration needed to audit the released results. Country identifiers are retained only where required by aggregate figure source data; blind keys, row-level reviewer ratings, adjudication rationales, and restricted source files are excluded.
