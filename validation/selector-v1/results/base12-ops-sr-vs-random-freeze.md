# Base-12 OPS/SR versus random freeze

This record freezes the first identity-blind comparison of the previously
frozen OPS and SR coverage metrics against the previously frozen
species-balanced random baseline.

## Prospective boundary

The comparison implementation was committed and pushed before empirical ranks
for the real candidate metrics were calculated.

Comparator implementation commit:

`e143114ff8f0041a0dd4f3fd511b767602e38769`

No genome or species identities were inspected during this comparison.

The empirical rank is descriptive validation evidence only. It does not modify
the pre-specified OPS-versus-SR decision rule and does not create a new selector
decision criterion.

## Frozen inputs

| Input | SHA256 |
| --- | --- |
| `base12-ops-vs-sr.txt` | `94ba2725fa646a803837d999ca609513d5000766398587e4a8f13dc5eb2655a1` |
| `random-coverage-replicates.tsv` | `86104d1ff9a3c619cdfa10e9839bf486b0ee1e77eccc758d93ea3ad9cc42a4a9` |
| `random-coverage-summary.tsv` | `247e7c248803226a378168f1f944b788bd056851bb475367ed08ae119a1657dc` |
| `random-coverage-provenance.tsv` | `450bf925999734f7a69dd4e5fda262f565fd4dc0feb224e34bc139fa674f1021` |

## Frozen comparison artifact

`base12-ops-sr-vs-random.tsv`

SHA256:

`3eb2d49d592da9b9ce7871252e9c8ade1c8bda61fff37eb4ef58dd15517f1c2e`

The artifact contains:

- 6 pre-specified panel sizes;
- 2 candidate selectors;
- 10 pre-specified coverage metrics;
- candidate metric value;
- random 2.5th percentile;
- random median;
- random 97.5th percentile;
- empirical rank relative to 1,000 random replicates.

This gives 120 identity-blind candidate/metric comparisons.

## Primary metric checkpoint

For the pre-specified weighted-p95 primary metric, empirical ranks were:

| N | OPS rank | SR rank |
| ---: | ---: | ---: |
| 10 | 371 | 487 |
| 20 | 612 | 262 |
| 50 | 314 | 167 |
| 100 | 34 | 5 |
| 200 | 1 | 1 |
| 500 | 1 | 1 |

The previously frozen OPS-versus-SR primary ordering is unchanged: OPS is
lower at N=10 and SR is lower at N=20, 50, 100, 200, and 500.

No selector decision is made or changed by this freeze record.
