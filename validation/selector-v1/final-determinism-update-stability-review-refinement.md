# Prospective determinism/update-stability review refinement

## Status

PRE-COMMIT, PRE-EXECUTION IMPLEMENTATION REFINEMENT

The first prospective package was installed for review but was not staged,
committed, or executed.

Focused review identified two issues to correct before freezing the method.

## Blinded deterministic-rebuild serialization

The first draft proposed writing one deterministic `tie_key` per genome in the
canonical matrix and ladder artifacts.

Although no accession string was present, an individual accession hash can be
mapped against the known finite public accession universe. That is weaker
blinding than necessary.

The refined design therefore:

- sorts canonical matrix rows by `tie_key` but does not write the key;
- reports only one complete ordered ladder SHA256 per selector rather than
  one per-genome hash.

This preserves byte-comparison determinism while avoiding individually
mappable pseudonyms.

## SR first-divergence explanation

The first draft compared SR genome-level secondary scores whenever two species
had equal primary scores.

That is not the SR decision hierarchy when the baseline genome and selected
genome belong to different species. Equal species-level primary scores are
resolved first by the frozen `species_tie_key`; genome-level scores are only
used within the chosen species.

The refined trace now distinguishes:

- species-level tie resolution between different species;
- genome-level score/tie resolution within the same species.

The traced ladder is still required to equal the committed SR implementation
exactly.

## Scientific boundary

No deterministic-rebuild or update-stability scientific outcome had been
calculated when these refinements were made.

The seven update scenarios, perturbation sizes, feature policy, panel sizes,
selectors, coverage geometry, stability outputs, and no-threshold
interpretation boundary are unchanged.
