# Observational benchmark results

Data: actual APHIS surveillance reports and public environmental products; synthetic examples are separate.

Panel: 2,494 county-months, 58 counties, 2022-01–2025-07; 280 positive H5N1 county-months.

## Primary outcome: explicit H5N1 reports

| Validation | Model | ROC-AUC | Average precision | Brier | Outcome prevalence |
| --- | --- | --- | --- | --- | --- |
| county_holdout | logistic_baseline | 0.625 | 0.153 | 0.099 | 0.112 |
| county_holdout | logistic_full | 0.616 | 0.154 | 0.099 | 0.112 |
| county_holdout | forest_baseline | 0.743 | 0.283 | 0.116 | 0.112 |
| county_holdout | forest_full | 0.725 | 0.264 | 0.113 | 0.112 |
| temporal_2025 | logistic_baseline | 0.278 | 0.076 | 0.110 | 0.111 |
| temporal_2025 | logistic_full | 0.289 | 0.084 | 0.111 | 0.111 |
| temporal_2025 | forest_baseline | 0.506 | 0.110 | 0.133 | 0.111 |
| temporal_2025 | forest_full | 0.462 | 0.099 | 0.137 | 0.111 |

## Added environmental predictors

Full-minus-baseline average precision, with paired county-bootstrap 95% intervals:

- county_holdout, logistic: +0.001 (95% interval -0.009 to +0.017).
- county_holdout, forest: -0.019 (95% interval -0.053 to +0.015).
- temporal_2025, logistic: +0.008 (95% interval -0.001 to +0.044).
- temporal_2025, forest: -0.010 (95% interval -0.032 to +0.005).

Intervals are conditional on fitted predictions and resample whole counties; model-selection uncertainty is not included.
A positive point estimate alone does not establish added predictive value; intervals and temporal performance must also be considered.

The inclusive-H5 sensitivity results, complete interval estimates, split audit, out-of-fold predictions, and missingness reports accompany this summary.

## Limits

This is an exploratory retrospective ecological prediction study, not a validated early-warning system or a causal analysis. Absence of a reported detection is not a tested-negative outcome. Surveillance effort and subtype ascertainment are incomplete. Climate and satellite predictors use the prior month; final revised source products do not reproduce real-time data availability. County holdouts do not separate neighboring counties with a buffer. Small satellite archive gaps and QA masking are documented in the data quality audit; imputation occurs within each training fold.
