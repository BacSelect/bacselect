# Final selector-v1 300/2400 OPS/SR versus random freeze

This record freezes the empirical-rank comparison between the already frozen
final 300/2400 OPS/SR coverage evidence and the already frozen 1,000-replicate
species-balanced random coverage baseline.

## Analysis identity

- comparator commit: `b6ce0212e44e888767bdf1e07c576050f3fe0f40`
- OPS/SR evidence-generation commit:
  `ea547dbe7eeffbd5ce426c7ca5cb4347d8a1bc9d`
- random evidence-generation commit:
  `81d7f62c3aa59b851848be9ce2afeb3b33839980`
- empirical-rank implementation: `lower_is_better_empirical_rank`
- panel sizes: 10, 20, 50, 100, 200, 500
- selectors: OPS, SR
- pre-specified coverage metrics: 10
- random replicates: 1,000

The comparator verified the two independent frozen evidence checkpoints
separately against their exact SHA256 identities before calculating any rank.

## Structural checks

The comparison table contains exactly:

- 1 header row;
- 6 panel sizes;
- 2 selectors;
- 10 metrics;
- 120 unique comparison rows.

All empirical ranks are within the valid range 1..1001.

## Primary weighted-p95 empirical ranks

| N | OPS rank | SR rank |
|---:|---:|---:|
| 10 | 505 | 546 |
| 20 | 167 | 397 |
| 50 | 82 | 101 |
| 100 | 2 | 96 |
| 200 | 1 | 1 |
| 500 | 1 | 1 |

These ranks are frozen descriptive evidence. They do not create a new
OPS-versus-SR decision rule.

## Output identities

- comparison table:
  `0fe15df3166351f06e583e2fadb8bab61eeee7e4cba920f6f59ae6b2ed9fdc3f`
- summary:
  `a1663a676a5d7bde3bb35f64ebcaca7541685affbd66a049086881023968c75a`
- output hash manifest:
  `bd1ebf921f26c18fb04ca9bc0b0c1126b487fbc0acd4a51a9071c62ddc30a593`

## Decision boundary

The comparator records:

- `new_selector_decision_criterion_introduced: false`;
- `selector_decision_evaluated: false`.

The final 300/2400 primary OPS-versus-SR curves remain non-uniformly ordered.
No selector interpretation is made by this freeze record.

Interpretation, if performed, must use only the already pre-specified decision
framework and must not introduce a new aggregate score, significance threshold,
or post-hoc criterion.
