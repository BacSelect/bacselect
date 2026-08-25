# Prospective determinism/update-stability runtime refinement

## Status

PRE-COMMIT, PRE-EXECUTION IMPLEMENTATION REFINEMENT

The prospective determinism/update-stability files remain untracked and no
scientific validation outcome has been calculated.

A second focused code review identified two runtime/provenance issues before
the method was frozen.

## Exact text writing

The draft runners passed a `newline` keyword to `Path.write_text()`. Python
3.11 `Path.write_text()` does not accept that keyword, so the outcome-producing
path would have failed only after scientific calculations had completed.

The refined runners now use an explicit text writer based on
`Path.open(..., newline="")`. Canonical strings already contain explicit `\n`
line endings.

No scientific calculation or serialization content is changed by this fix.

## Scenario fingerprint completeness

The update-stability scenario fingerprint previously bound accession-derived
tie identity, species assignment, and synthetic/baseline status, but not the
12 raw structural feature values.

That was insufficient to make the fingerprint a complete identity for a
perturbed source universe.

The refined aggregate fingerprint now also binds all 12 raw structural feature
values for every canonical-sorted row using `.17g` serialization.

Only the aggregate scenario SHA256 is reported. No per-genome hash or identity
is written.

## Scientific boundary

The seven pre-specified perturbation scenarios, their sizes, selector
algorithms, full recomputation of species-balanced geometry, stability outputs,
and no-threshold interpretation boundary are unchanged.

No deterministic-rebuild or update-stability outcome had been calculated when
this refinement was made.
