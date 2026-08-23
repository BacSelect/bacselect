# Base-12 OPS/SR versus random interpretation

## Status

DESCRIPTIVE VALIDATION RESULT

The OPS-versus-SR selector decision remains **UNRESOLVED**.

Genome and species identities remain blinded.

This interpretation uses only the frozen comparison artifact:

`base12-ops-sr-vs-random.tsv`

SHA256:

`3eb2d49d592da9b9ce7871252e9c8ade1c8bda61fff37eb4ef58dd15517f1c2e`

No new metric, aggregate score, significance threshold, or selector decision
rule is introduced.

## Primary metric

The pre-specified primary metric is species-balanced weighted 95th percentile
nearest-panel Euclidean distance. Lower values indicate better structural
coverage.

| N | OPS rank | SR rank | Lower candidate value |
| ---: | ---: | ---: | :--- |
| 10 | 371 | 487 | OPS |
| 20 | 612 | 262 | SR |
| 50 | 314 | 167 | SR |
| 100 | 34 | 5 | SR |
| 200 | 1 | 1 | SR |
| 500 | 1 | 1 | SR |

The previously frozen OPS-versus-SR ordering is therefore unchanged: OPS has
the lower primary metric at N=10, while SR has the lower primary metric at
N=20, 50, 100, 200, and 500.

Relative to the 1,000 species-balanced random panels, the deterministic
selectors show increasingly strong upper-tail coverage as panel size grows.

At N=100, 33 random replicates had a strictly lower primary metric than OPS
and 4 had a strictly lower primary metric than SR.

At N=200 and N=500, no random replicate had a strictly lower primary metric
than either OPS or SR.

These empirical ranks are descriptive. They are not p-values and are not an
additional selector decision rule.

## Central-distance metrics

The random comparison also identifies a clear trade-off.

At N=20, 50, 100, 200, and 500, both OPS and SR have empirical rank 1001 for:

- species-balanced weighted mean distance;
- species-balanced weighted median distance;
- median species mean distance;
- median species maximum distance.

For these metrics, all 1,000 random panels therefore had strictly lower
values than the corresponding deterministic candidate.

This indicates that the deterministic selectors do not minimize distance for
the centre of the evaluation distribution.

## Tail and extreme-distance metrics

The opposite pattern is observed for upper-tail and extreme-distance
summaries.

As N increases, OPS and SR increasingly occupy the best end of the random
distribution for:

- weighted 95th percentile distance;
- 95th percentile species mean distance;
- 95th percentile species maximum distance;
- maximum species mean distance;
- maximum species maximum distance;
- unweighted maximum distance.

By N=100, several extreme-distance metrics have empirical rank 1 for both
selectors.

At N=200 and N=500, the upper-tail and extreme-distance metrics are almost
uniformly at or very near empirical rank 1.

The observed pattern is poorer central-distance performance alongside
substantially improved upper-tail and worst-case structural coverage.

This behaviour is consistent with the prospectively defined diversity-seeking
objective and is particularly relevant to the pre-specified weighted-p95
primary metric.

## Metric identity note

`unweighted_max` and `max_species_max` are numerically identical by
construction.

The former is the maximum nearest-panel distance over all eligible genomes.
The latter is the maximum, across species, of each species' maximum
nearest-panel distance. Both therefore identify the same global maximum
genome-level distance.

They are retained as separately named pre-specified summaries because they
arise from the genome-level and species-level reporting views respectively.

## Selector decision

The random baseline demonstrates that deterministic diversity-seeking
selection can substantially improve tail and extreme structural coverage
relative to species-balanced random sampling, particularly at larger panel
sizes.

It does not resolve OPS versus SR.

The pre-specified OPS-versus-SR primary curves still cross, and the random
empirical ranks were prospectively defined as descriptive validation evidence
rather than a selector decision criterion.

The selector-v1 decision therefore remains:

**UNRESOLVED**

Identity blinding remains in force.

The remaining pre-specified validation analyses will proceed before any
selector decision or unblinding.
