# Results - Explainable Multilingual Legal Meaning Preservation

Data: FrJUDGE + NLLB English/Hindi (projected labels) | model: `xlm-roberta-base` | seeds: [42, 43, 44]

## Experiment 1 - Generic similarity vs. LMP model (test set)

Scores on the 1-10 LMP scale. over_% = predictions that over-estimate preservation by >0.5 levels (dangerous direction). Ours = mean ± std over seeds.

| system                | pearson       | spearman      | rmse          | mae           | over_%         | decision_acc   | decision_macroF1   |   n | pearson_95CI            |
|:----------------------|:--------------|:--------------|:--------------|:--------------|:---------------|:---------------|:-------------------|----:|:------------------------|
| TF-IDF(char)          | 0.281         | 0.307         | 2.391         | 1.907         | 35.556         | 0.585          | 0.406              | 270 | [0.18, 0.39]            |
| chrF                  | 0.41          | 0.401         | 2.507         | 2.064         | 22.963         | 0.504          | 0.3                | 270 | [0.31, 0.51]            |
| BLEU                  | 0.316         | 0.305         | 4.291         | 3.788         | 5.556          | 0.311          | 0.233              | 270 | [0.20, 0.43]            |
| BERTScore(XLM-R)      | 0.413         | 0.428         | 3.834         | 3.125         | 80.741         | 0.456          | 0.209              | 270 | [0.32, 0.52]            |
| SBERT-Multi           | 0.081         | 0.103         | 3.572         | 2.87          | 74.815         | 0.459          | 0.219              | 270 | [-0.03, 0.19]           |
| LaBSE                 | 0.178         | 0.214         | 3.45          | 2.767         | 75.185         | 0.459          | 0.219              | 270 | [0.07, 0.30]            |
| Ours (multi-task LMP) | 0.576 ± 0.018 | 0.553 ± 0.018 | 2.118 ± 0.086 | 1.644 ± 0.082 | 38.148 ± 3.954 | 0.609 ± 0.011  | 0.530 ± 0.026      | 270 | [0.53, 0.69] (ensemble) |

## Experiment 2 - English vs. Hindi (and cross-lingual transfer)



| setting               | test_lang   | system                |   pearson |   spearman |   rmse |   mae |   over_% |   n |
|:----------------------|:------------|:----------------------|----------:|-----------:|-------:|------:|---------:|----:|
| joint (all languages) | en          | TF-IDF(char)          |     0.360 |      0.379 |  2.289 | 1.829 |   31.111 |  90 |
| joint (all languages) | en          | chrF                  |     0.412 |      0.386 |  2.464 | 2.028 |   22.222 |  90 |
| joint (all languages) | en          | BLEU                  |     0.294 |      0.229 |  4.272 | 3.753 |    5.556 |  90 |
| joint (all languages) | en          | BERTScore(XLM-R)      |     0.402 |      0.394 |  3.856 | 3.145 |   81.111 |  90 |
| joint (all languages) | en          | SBERT-Multi           |     0.089 |      0.065 |  3.438 | 2.715 |   73.333 |  90 |
| joint (all languages) | en          | LaBSE                 |     0.166 |      0.133 |  3.256 | 2.589 |   72.222 |  90 |
| joint (all languages) | en          | Ours (multi-task LMP) |     0.584 |      0.574 |  2.065 | 1.607 |   35.556 |  90 |
| joint (all languages) | fr          | TF-IDF(char)          |     0.322 |      0.331 |  2.316 | 1.823 |   37.778 |  90 |
| joint (all languages) | fr          | chrF                  |     0.467 |      0.469 |  2.373 | 1.929 |   24.444 |  90 |
| joint (all languages) | fr          | BLEU                  |     0.329 |      0.398 |  4.284 | 3.804 |    4.444 |  90 |
| joint (all languages) | fr          | BERTScore(XLM-R)      |     0.527 |      0.503 |  3.855 | 3.152 |   82.222 |  90 |
| joint (all languages) | fr          | SBERT-Multi           |     0.074 |      0.170 |  3.719 | 2.995 |   75.556 |  90 |
| joint (all languages) | fr          | LaBSE                 |     0.326 |      0.345 |  3.602 | 2.911 |   77.778 |  90 |
| joint (all languages) | fr          | Ours (multi-task LMP) |     0.698 |      0.663 |  1.752 | 1.351 |   36.667 |  90 |
| joint (all languages) | hi          | TF-IDF(char)          |     0.189 |      0.213 |  2.559 | 2.069 |   37.778 |  90 |
| joint (all languages) | hi          | chrF                  |     0.373 |      0.373 |  2.676 | 2.234 |   22.222 |  90 |
| joint (all languages) | hi          | BLEU                  |     0.330 |      0.304 |  4.318 | 3.808 |    6.667 |  90 |
| joint (all languages) | hi          | BERTScore(XLM-R)      |     0.355 |      0.419 |  3.792 | 3.077 |   78.889 |  90 |
| joint (all languages) | hi          | SBERT-Multi           |     0.085 |      0.143 |  3.552 | 2.899 |   75.556 |  90 |
| joint (all languages) | hi          | LaBSE                 |     0.154 |      0.245 |  3.484 | 2.802 |   75.556 |  90 |
| joint (all languages) | hi          | Ours (multi-task LMP) |     0.556 |      0.544 |  2.108 | 1.698 |   35.556 |  90 |
| zero-shot en->hi      | hi          | Ours (multi-task LMP) |     0.373 |      0.351 |  2.294 | 1.841 |   37.778 |  90 |
| zero-shot fr->en      | en          | Ours (multi-task LMP) |     0.459 |      0.479 |  2.237 | 1.831 |   38.889 |  90 |
| zero-shot fr->hi      | hi          | Ours (multi-task LMP) |     0.396 |      0.359 |  2.745 | 2.151 |   54.444 |  90 |
| zero-shot hi->en      | en          | Ours (multi-task LMP) |     0.425 |      0.377 |  2.261 | 1.805 |   44.444 |  90 |

## Experiment 3a - Legal-domain generalisation



| setting                                         | test_domain   | system                |   pearson |   rmse |   mae |   over_% |   n |
|:------------------------------------------------|:--------------|:----------------------|----------:|-------:|------:|---------:|----:|
| in-domain (joint training)                      | insurance     | Ours (multi-task LMP) |     0.611 |  1.982 | 1.552 |   35.926 | 270 |
| in-domain                                       | insurance     | BERTScore(XLM-R)      |     0.413 |  3.834 | 3.125 |   80.741 | 270 |
| out-of-domain insurance->tenancy (silver probe) | tenancy       | Ours (multi-task LMP) |     0.309 |  3.119 | 2.488 |   68.317 | 202 |

## Experiment 3b - Sentence-only vs. contextual input

Skipped: this dataset has no context column (FrJUDGE pairs are isolated sentences).



## Experiment 4 - Sanity checks (held-out clauses)

identical_>=99%: share of identical pairs scored >= 99% of the scale (higher is better). unrelated_<=1%: share of unrelated same-domain legal pairs scored <= 1% (higher is better).

| system                        |   identical_>=99% |   unrelated_<=1% |   identical_mean |   unrelated_mean |
|:------------------------------|------------------:|-----------------:|-----------------:|-----------------:|
| TF-IDF(char)                  |           100.000 |            0.370 |           10.000 |            2.440 |
| chrF                          |           100.000 |            0.000 |           10.000 |            2.760 |
| BLEU                          |           100.000 |           36.670 |           10.000 |            1.150 |
| BERTScore(XLM-R)              |           100.000 |            0.000 |           10.000 |            8.600 |
| SBERT-Multi                   |           100.000 |            1.480 |           10.000 |            4.340 |
| LaBSE                         |           100.000 |            0.000 |           10.000 |            5.110 |
| Ours (multi-task LMP) + DA    |            95.190 |           93.700 |            9.980 |            1.040 |
| Ours (multi-task LMP) (no DA) |             0.000 |            0.000 |            8.090 |            4.260 |

## Experiment 5a - Score drop caused by one legal edit (higher = more sensitive = better)

Each row: mean(score of faithful simplification) - mean(score after the edit).

| variant         |   TF-IDF(char) |   chrF |   BLEU |   BERTScore(XLM-R) |   SBERT-Multi |   LaBSE |   Ours (multi-task LMP) |
|:----------------|---------------:|-------:|-------:|-------------------:|--------------:|--------:|------------------------:|
| change_number   |          0.070 |  0.020 | -0.240 |             -0.040 |         0.210 |   0.340 |                   0.230 |
| change_scope    |          0.400 |  0.320 |  0.160 |              0.030 |         0.180 |   0.130 |                   0.590 |
| drop_condition  |          1.340 |  1.490 |  1.170 |              0.230 |         1.070 |   1.270 |                   1.700 |
| entity_swap     |          0.270 |  0.170 |  0.050 |              0.010 |        -0.090 |  -0.040 |                   1.410 |
| hallucination   |          0.550 | -0.050 |  0.210 |              0.100 |         0.390 |   0.450 |                   1.460 |
| negation_flip   |          0.070 |  0.090 |  0.110 |              0.020 |         0.360 |   0.200 |                   1.500 |
| obligation_flip |          0.020 |  0.080 |  0.050 |              0.010 |         0.140 |   0.120 |                   0.640 |
| omission        |          1.060 |  1.480 |  0.960 |              0.170 |         0.820 |   1.010 |                   1.440 |
| [average drop]  |          0.470 |  0.450 |  0.310 |              0.070 |         0.390 |   0.440 |                   1.120 |

## Experiment 5c - Qualitative error analysis (20 cases, full text in exp5c_qualitative_cases.md)



| pair_id   | lang   |   gold_errors |   gold_lmp |   model_lmp |   chrF | model_error_types      |
|:----------|:-------|--------------:|-----------:|------------:|-------:|:-----------------------|
| FR229-fr  | fr     |           nan |      1.000 |       6.950 |  6.380 |                        |
| FR089-en  | en     |           nan |      2.800 |       7.200 |  7.190 |                        |
| FR100-hi  | hi     |           nan |      3.000 |       6.870 |  5.090 |                        |
| FR227-fr  | fr     |           nan |      2.000 |       7.390 |  2.880 |                        |
| FR092-en  | en     |           nan |      2.000 |       6.300 |  5.520 |                        |
| FR115-en  | en     |           nan |      4.800 |       8.410 |  7.030 |                        |
| FR131-en  | en     |           nan |      5.000 |       8.290 |  6.900 |                        |
| FR217-hi  | hi     |           nan |      4.600 |       8.700 |  4.580 |                        |
| FR144-en  | en     |           nan |      3.400 |       6.300 |  6.160 |                        |
| FR050-hi  | hi     |           nan |      4.200 |       7.200 |  6.320 |                        |
| FR165-hi  | hi     |           nan |      6.000 |       1.000 |  1.190 | hallucination;omission |
| FR172-en  | en     |           nan |      5.800 |       1.000 |  3.390 | hallucination;omission |
| FR230-hi  | hi     |           nan |      5.400 |       1.280 |  1.860 | hallucination;omission |
| FR150-en  | en     |           nan |      6.600 |       2.780 |  3.080 | hallucination          |
| FR179-hi  | hi     |           nan |      6.600 |       2.080 |  4.650 | contradiction          |
| FR080-hi  | hi     |           nan |     10.000 |       2.710 |  4.650 | contradiction          |
| FR173-hi  | hi     |           nan |      8.000 |       3.140 |  4.150 | hallucination;omission |
| FR268-en  | en     |           nan |      8.000 |       5.190 |  4.130 |                        |
| FR127-hi  | hi     |           nan |      9.600 |       6.480 |  3.310 |                        |
| FR263-fr  | fr     |           nan |     10.000 |       6.910 |  5.760 |                        |

## Experiment 5d - Improvement: legal-edit augmentation (seeds [42], same split)

Test-set agreement with humans (pearson, rmse) and sensitivity to single legal edits (drops, higher = better). Edits are built only from training pairs.

| system                         |   pearson |   rmse |   over_% |   avg_edit_drop |   drop_change_number |   drop_negation_flip |   drop_obligation_flip |   drop_entity_swap |   drop_drop_exception |
|:-------------------------------|----------:|-------:|---------:|----------------:|---------------------:|---------------------:|-----------------------:|-------------------:|----------------------:|
| Ours (main)                    |     0.597 |  2.051 |   43.704 |           1.636 |                1.077 |                1.910 |                  1.096 |              2.440 |                   nan |
| Ours + legal-edit augmentation |     0.496 |  2.398 |   23.704 |           0.879 |               -0.309 |                2.768 |                  0.513 |              1.270 |                   nan |
