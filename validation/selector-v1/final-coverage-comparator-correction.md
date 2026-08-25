# Prospective final-coverage comparator correction

## Scope

This correction is frozen before any final 300/2400 OPS/SR-versus-random
empirical rank is calculated.

The originally committed final comparator incorrectly required the independently
generated OPS/SR evidence and random evidence to have the same
`analysis_commit`.

That requirement is a provenance error, not a scientific-method change.

## Why the original gate is invalid

The two evidence sets were intentionally generated and frozen sequentially:

- final OPS/SR coverage analysis commit:
  `ea547dbe7eeffbd5ce426c7ca5cb4347d8a1bc9d`;
- final random coverage analysis commit:
  `81d7f62c3aa59b851848be9ce2afeb3b33839980`.

The later random run necessarily occurred after the OPS/SR evidence had been
frozen. Requiring both evidence files to report the comparator's current commit,
or to report one common evidence-generation commit, would reject valid frozen
inputs.

## Correction

The comparator now:

1. reads the committed frozen evidence from
   `validation/selector-v1/results`;
2. verifies every scientific input against its exact frozen SHA256;
3. verifies the OPS/SR summary against its own frozen analysis commit;
4. verifies the random provenance against its own frozen analysis commit;
5. verifies the source hash manifests for both evidence sets;
6. retains the existing `lower_is_better_empirical_rank` implementation;
7. retains all six panel sizes, both selectors, and all ten pre-specified
   coverage metrics;
8. records that empirical ranks are descriptive support and do not introduce
   a new selector decision criterion.

A `--verify-inputs-only` mode verifies all frozen input/provenance gates without
calculating any empirical rank.

## Decision boundary

This correction does not change:

- any OPS or SR panel;
- any coverage metric;
- any random membership;
- any random coverage value;
- the empirical-rank algorithm;
- the pre-specified OPS-versus-SR automatic-winner rule;
- the rule that crossing primary curves do not produce an automatic winner.

No empirical rank is calculated until this correction has been reviewed,
committed, and pushed.
