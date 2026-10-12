from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor

PROJECT = Path(__file__).resolve().parents[1]
TABLES = PROJECT / "results" / "tables_v2"
MODELS = PROJECT / "results" / "models_v2"
ADJ = PROJECT / "data" / "adjudication"
STATUS = PROJECT / "results" / "adjudication" / "adjudication_status.json"
ROUND3_FINAL_STATUS = PROJECT / "results" / "adjudication" / "round3" / "round3_final_status.json"
ROUND3_FINAL_TABLE = ADJ / "adjudication_template_round3_FINAL_RESTRICTED.csv"
SEED = 20261009
N_BOOT = 2000
SUBSTANTIVE = {"SUBSTANTIVE_SAME_DIRECTNESS", "TOWARD_MORE_DIRECT", "TOWARD_MORE_INDIRECT"}


def exposure_map() -> tuple[pd.DataFrame, str]:
    status = json.loads(ROUND3_FINAL_STATUS.read_text()) if ROUND3_FINAL_STATUS.exists() else json.loads(STATUS.read_text())
    final_ready = status.get("status") == "ADJUDICATION_COMPLETE" and status.get("formal_analysis_allowed", False) and ROUND3_FINAL_TABLE.exists()
    if final_ready:
        x = pd.read_csv(ROUND3_FINAL_TABLE, dtype=str, keep_default_na=False)
        key = pd.read_csv(ADJ / "blind_key_RESTRICTED.csv")[["blind_id", "iso3"]]
        x = x.merge(key, on="blind_id", how="left", validate="one_to_one")
        if x[["iso3", "indicator"]].isna().any().any():
            raise ValueError("Adjudicated exposure could not be fully mapped through the restricted blind key")
        col, label = "adjudicated_classification", "ADJUDICATED"
    elif status.get("gate_passed", False):
        x = pd.read_csv(ADJ / "adjudication_template_RESTRICTED.csv")
        key = pd.read_csv(ADJ / "blind_key_RESTRICTED.csv")[["blind_id", "iso3"]]
        x = x.merge(key, on="blind_id", how="left", validate="one_to_one")
        if x[["iso3", "indicator"]].isna().any().any():
            raise ValueError("Adjudicated exposure could not be fully mapped through the restricted blind key")
        col, label = "adjudicated_classification", "ADJUDICATED"
    else:
        x = pd.read_csv(ADJ / "provisional_classification_DEVELOPMENT_ONLY.csv")
        col, label = "provisional_classification", "PROVISIONAL_DEVELOPMENT_ONLY"
    x["substantive_transition"] = x[col].isin(SUBSTANTIVE).astype(float)
    x.loc[x[col].eq("UNCLASSIFIABLE"), "substantive_transition"] = np.nan
    x["wording_only"] = x[col].eq("ADMINISTRATIVE_OR_WORDING_ONLY").astype(int)
    return x[["iso3", "indicator", col, "substantive_transition", "wording_only"]], label


def country_data() -> tuple[pd.DataFrame, str]:
    cells = pd.read_csv(PROJECT / "data" / "normalized" / "paired_cells.csv")
    ext = pd.read_csv(PROJECT / "data" / "normalized" / "external_validation.csv")
    exp, label = exposure_map()
    cells = cells.merge(exp, on=["iso3", "indicator"], how="left", validate="many_to_one")
    eligible = cells[cells.asr_2022 > 0.5].copy()
    country = eligible.groupby(["iso3", "indicator"], as_index=False).agg(
        median_aspd=("aspd", "median"), median_abs_log_ratio=("absolute_log_ratio", "median"),
        proportion_gt20=("revision_gt_20", "mean"), median_asr_2022=("asr_2022", "median"),
        hdi_value=("hdi_value", "first"), who_region=("who_region_2022", "first"),
        baseline_directness_score=("source_directness_score_2022", "first"),
        substantive_transition=("substantive_transition", "first"), wording_only=("wording_only", "first"))
    country = country.merge(ext, on="iso3", how="left", suffixes=("", "_external"))
    country["hdi_z"] = (country.hdi_value - country.hdi_value.mean()) / country.hdi_value.std(ddof=0)
    country["log_outcome"] = np.log1p(country.median_aspd)
    country.to_csv(TABLES / "country_level_v2.csv", index=False)
    return country, label


def marginal(fit, frame: pd.DataFrame) -> float:
    a, b = frame.copy(), frame.copy()
    a["substantive_transition"], b["substantive_transition"] = 0, 1
    return float(np.median(np.expm1(fit.predict(b)) - np.expm1(fit.predict(a))))


def diagnostics(fit, frame: pd.DataFrame, indicator: str) -> dict:
    infl = fit.get_influence()
    x = pd.DataFrame(fit.model.exog, columns=fit.model.exog_names)
    vif = {c: float(variance_inflation_factor(x.values, i)) for i, c in enumerate(x.columns) if c != "Intercept"}
    return {"indicator": indicator, "n": int(fit.nobs), "r_squared": float(fit.rsquared),
            "max_vif": max(vif.values()) if vif else None, "max_leverage": float(infl.hat_matrix_diag.max()),
            "max_cooks_d": float(infl.cooks_distance[0].max()), "shapiro_p": float(stats.shapiro(fit.resid).pvalue),
            "transition_n": int(frame.substantive_transition.sum()), "wording_only_n": int(frame.wording_only.sum())}


def stratified_bootstrap(frame: pd.DataFrame, formula: str, rng: np.random.Generator) -> tuple[np.ndarray, int]:
    vals, failures = [], 0
    strata = list(frame.groupby("who_region", dropna=False))
    for _ in range(N_BOOT):
        sample = pd.concat([g.sample(len(g), replace=True, random_state=int(rng.integers(2**31-1))) for _, g in strata])
        try:
            if sample.substantive_transition.nunique() < 2:
                raise ValueError("single exposure")
            vals.append(marginal(smf.ols(formula, sample).fit(), sample))
        except Exception:
            failures += 1
    return np.asarray(vals), failures


def permutation_p(frame: pd.DataFrame, formula: str, observed: float, rng: np.random.Generator) -> float:
    vals = []
    strata_cols = ["who_region", "baseline_directness_score"]
    for _ in range(2000):
        p = frame.copy()
        p["substantive_transition"] = p.groupby(strata_cols, dropna=False).substantive_transition.transform(
            lambda s: rng.permutation(s.to_numpy()))
        if p.substantive_transition.nunique() < 2:
            continue
        vals.append(abs(marginal(smf.ols(formula, p).fit(), p)))
    return float((1 + np.sum(np.asarray(vals) >= abs(observed))) / (1 + len(vals)))


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True); MODELS.mkdir(parents=True, exist_ok=True)
    country, label = country_data()
    formula = "log_outcome ~ substantive_transition + baseline_directness_score + np.log1p(median_asr_2022) + hdi_z"
    rng = np.random.default_rng(SEED)
    rows, diags, loo, coefficients = [], [], [], []
    for indicator in ["Incidence", "Mortality"]:
        f = country[(country.indicator == indicator) & country.hdi_z.notna() & country.substantive_transition.notna()].copy()
        fit = smf.ols(formula, f).fit(cov_type="HC3")
        model_formulas = {
            "M0": "log_outcome ~ substantive_transition",
            "M1": "log_outcome ~ substantive_transition + baseline_directness_score + np.log1p(median_asr_2022)",
            "M2": formula,
        }
        for model_name, model_formula in model_formulas.items():
            model_fit = smf.ols(model_formula, f).fit(cov_type="HC3")
            for term, estimate in model_fit.params.items():
                coefficients.append({
                    "indicator": indicator,
                    "model": model_name,
                    "term": term,
                    "estimate": float(estimate),
                    "hc3_se": float(model_fit.bse[term]),
                    "p_value": float(model_fit.pvalues[term]),
                    "n": int(model_fit.nobs),
                })
        effect = marginal(fit, f)
        boot, failures = stratified_bootstrap(f, formula, rng)
        rows.append({"indicator": indicator, "exposure_status": label, "n": len(f), "transition_n": int(f.substantive_transition.sum()),
                     "adjusted_marginal_difference_pp": effect, "bootstrap_ci_low": float(np.quantile(boot, .025)),
                     "bootstrap_ci_high": float(np.quantile(boot, .975)), "bootstrap_success": len(boot),
                     "bootstrap_failure_rate": failures/N_BOOT, "permutation_p": permutation_p(f, formula, effect, rng)})
        diags.append(diagnostics(fit, f, indicator))
        for region in sorted(f.who_region.dropna().unique()):
            q = f[f.who_region != region]
            loo.append({"indicator": indicator, "excluded_region": region, "n": len(q),
                        "marginal_difference_pp": marginal(smf.ols(formula, q).fit(), q)})
    pd.DataFrame(rows).to_csv(MODELS / "primary_model_v2.csv", index=False)
    pd.DataFrame(coefficients).to_csv(MODELS / "model_coefficients_v2.csv", index=False)
    pd.DataFrame(diags).to_csv(MODELS / "model_diagnostics_v2.csv", index=False)
    pd.DataFrame(loo).to_csv(MODELS / "leave_one_region_out.csv", index=False)
    negative = country.groupby(["indicator", "wording_only"], as_index=False).median_aspd.agg(["count", "median", "mean"]).reset_index()
    negative.to_csv(TABLES / "wording_only_falsification.csv", index=False)
    if label == "ADJUDICATED" and country.substantive_transition.isna().any():
        bounds = []
        for bound in [0, 1]:
            bounded = country.copy()
            bounded["substantive_transition"] = bounded.substantive_transition.fillna(bound)
            for indicator in ["Incidence", "Mortality"]:
                f = bounded[(bounded.indicator == indicator) & bounded.hdi_z.notna()].copy()
                fit = smf.ols(formula, f).fit(cov_type="HC3")
                bounds.append({"indicator": indicator, "unclassifiable_as": bound, "n": len(f),
                               "unclassifiable_country_indicator_n": int(country.loc[country.indicator.eq(indicator), "substantive_transition"].isna().sum()),
                               "adjusted_marginal_difference_pp": marginal(fit, f)})
        pd.DataFrame(bounds).to_csv(MODELS / "unclassifiable_boundary_sensitivity.csv", index=False)
    summary = {"status": label, "formula": formula, "bootstrap_replicates": N_BOOT, "submission_candidate": False,
               "warning": "Provisional exposure is for pipeline development only." if label.startswith("PROVISIONAL") else None}
    (MODELS / "v2_analysis_status.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
