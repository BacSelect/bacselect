# Final selector-v1 update-stability interpretation

## Status

**UPDATE-STABILITY INTERPRETATION COMPLETE**

This checkpoint interprets the already frozen, blinded update-stability
evidence for the final 300/2400 selector-v1 geometry.

It does not introduce a new selector-decision rule.

The evidence interpreted here was frozen at Git commit:

`50c526ea48b6dee481551dc0bbdb47c3fc03fcf2`

The frozen update-stability evidence record SHA256 is:

`a9297b490aa788ed6aef8b81c24000acad9f3923d67229128278b7cb9f449baf`

Genome and species identities remain blinded.

## Overall result

There is **no uniform update-stability winner between OPS and SR**.

The two selectors respond differently to different changes in the source
universe:

- SR is markedly more stable than OPS when additional genomes are added to
  already represented species, especially heavily sampled species;
- SR is also more stable than OPS under the tested taxonomy-split scenario;
- both selectors are highly sensitive to addition of previously absent
  species;
- SR is more sensitive than OPS to the tested merger of singleton species;
- both selectors are highly stable to structurally identical record
  replacement, with only small membership changes;
- deterministic removal of existing genomes perturbs both selectors, but OPS
  changes more strongly in this scenario.

These are descriptive stability results. No prospective stability threshold or
aggregate stability score exists, so they do not select OPS or SR.

## N=500 panel membership

At N=500, unordered overlap with the frozen baseline panel was:

| Scenario | OPS overlap | OPS changed | SR overlap | SR changed |
| --- | ---: | ---: | ---: | ---: |
| add 500 general existing-species genomes | 173/500 | 327 | 499/500 | 1 |
| remove 500 genomes | 177/500 | 323 | 381/500 | 119 |
| replace 500 genomes with structural copies | 493/500 | 7 | 494/500 | 6 |
| add 500 genomes to heavily sampled species | 139/500 | 361 | 500/500 | 0 |
| add 100 previously absent species | 166/500 | 334 | 163/500 | 337 |
| split 500 genomes from the largest species | 157/500 | 343 | 500/500 | 0 |
| merge 100 singleton species | 237/500 | 263 | 145/500 | 355 |

The complete six-N results remain frozen in
`final300-2400-update-stability-prefixes.tsv`.

## Addition within the existing species universe

### General addition

Adding 500 structural-profile copies while retaining each template's existing
species assignment caused only a very small change in the species-balanced
percentile geometry:

- mean absolute coordinate shift:
  `1.3309266649057275e-05`;
- maximum absolute coordinate shift:
  `8.3087170390960807e-05`.

Despite that small geometry shift, OPS overlap fell progressively from 10/10
at N=10 to 173/500 at N=500.

The first OPS positional divergence occurred at rank 15 because the baseline
choice was no longer the selected representative of its species.

SR first diverged at rank 5 through an exact-score genome tie break and retained
499/500 baseline members at N=500.

This scenario therefore exposes a strong difference in sensitivity to
additional within-species sampling.

### Addition to heavily sampled species

This was the most striking within-species contrast.

Adding 50 genomes to each of the ten most heavily sampled species produced an
extremely small coordinate shift:

- mean absolute coordinate shift:
  `3.1574410009305148e-07`;
- maximum absolute coordinate shift:
  `1.731153964623644e-06`.

OPS nevertheless changed at rank 2 and retained only 139/500 baseline members
at N=500. The first divergence again occurred because the baseline choice was
no longer the selected one-per-species representative.

SR was unchanged through N=500: overlap was 500/500 at every evaluated panel
size.

This is direct evidence that, under the tested perturbation, OPS membership is
highly sensitive to changes in within-species sampling even when the global
percentile geometry changes only minimally.

It does not establish a general stability threshold and does not by itself
select SR.

## Removal of existing genomes

Deterministic removal of 500 genomes reduced the universe from 55,306 to
54,806 genomes and reduced the species count from 13,765 to 13,653.

At N=500:

- OPS overlap was 177/500;
- SR overlap was 381/500.

OPS first diverged at rank 3 because another candidate had a higher current
maximin score.

SR first diverged at rank 19 because another species had a higher residual
score.

Some baseline members were physically unavailable after removal, but the
membership changes were much larger than the number of unavailable baseline
members alone:

- OPS: 3 unavailable baseline N=500 members, 323 total changes;
- SR: 8 unavailable baseline N=500 members, 119 total changes.

The perturbation therefore propagates through each selector trajectory rather
than being limited to direct replacement of removed panel members.

## Structurally identical record replacement

Replacing 500 genomes with synthetic accessions carrying identical raw
features and the same species assignments caused:

- zero mean percentile-coordinate shift;
- zero maximum percentile-coordinate shift.

At N=500:

- OPS overlap was 493/500;
- SR overlap was 494/500.

The first divergence for each selector occurred when the corresponding
baseline accession was no longer available.

Because geometry and species assignments were unchanged, the small residual
membership differences are attributable to record identity and the frozen
deterministic tie-breaking pathway rather than structural-geometry change.

This provides a useful control: neither selector is broadly destabilized by
record replacement alone.

## Addition of previously absent species

Adding 100 new singleton species changed the species-balanced percentile
geometry more strongly than within-species addition:

- mean absolute coordinate shift:
  `0.0004273340139773582`;
- maximum absolute coordinate shift:
  `0.0013162732003728639`.

At N=500:

- OPS overlap was 166/500;
- SR overlap was 163/500.

The first divergence occurred at:

- OPS rank 7, through a higher maximin score;
- SR rank 10, through a higher species residual score.

Only three synthetic new-species genomes appeared in the SR N=500 panel and
none appeared in the OPS N=500 panel, yet both baseline panels changed by more
than 330 members.

The large response is therefore not simply direct insertion of newly added
genomes. Adding new species changes the species-balanced geometry and
subsequent selector trajectory across the existing universe.

Both selectors are sensitive to this tested form of genuine universe
expansion.

## Taxonomy split

Reassigning 500 genomes from the largest baseline species into one new species
changed no raw feature rows.

At N=500:

- OPS overlap was 157/500;
- SR overlap was 500/500.

OPS first diverged at rank 2 because the baseline choice was no longer the
selected species representative.

SR first diverged positionally at rank 134 through a higher species residual
score, but its unordered membership at all evaluated N values remained
identical to baseline.

The positional divergence and 500/500 N=500 membership are not contradictory:
the SR ordering changed internally and later reconverged to the same evaluated
prefix membership.

This scenario again shows strong OPS sensitivity to changed species-group
composition under the one-representative-per-species construction.

## Taxonomy merge

Merging 100 singleton species into one species changed no raw feature rows but
reduced the species count from 13,765 to 13,666.

At N=500:

- OPS overlap was 237/500;
- SR overlap was 145/500.

SR was especially sensitive in this scenario. Its first selected genome
changed immediately at rank 1 because the perturbed species-centroid geometry
changed the minimum species-centroid distance to the global centroid.

OPS first diverged at rank 3 because the baseline choice was no longer the
selected species representative.

This result is important because it prevents a one-sided interpretation of
the stability analysis: SR is not uniformly more stable than OPS to taxonomy
changes.

## What the stability results establish

The update-stability analysis establishes several mechanistic properties of
the two candidate selectors under the pre-specified perturbations.

1. OPS can be highly sensitive to relatively small within-species changes
   because the one-per-species representative itself may change, which then
   changes the subsequent maximin trajectory.

2. SR can be extremely stable to additional sampling within already
   represented species, including the tested heavily sampled-species
   perturbation.

3. Both selectors can change substantially when previously absent species are
   introduced, even when relatively few of those new genomes are themselves
   selected.

4. Taxonomy reassignment affects the selectors differently depending on the
   type of reassignment. The tested split strongly perturbed OPS membership
   but not SR membership, whereas the tested singleton merge strongly
   perturbed SR.

5. Structurally identical record replacement causes only small panel changes
   for both selectors, supporting the intended deterministic behaviour in the
   absence of meaningful geometry or species-assignment change.

These statements are specific to the pre-specified perturbations. They are not
claims about all possible future archive updates.

## Selector-decision boundary

The update-stability protocol prospectively defined:

- no minimum acceptable overlap;
- no maximum acceptable changed count;
- no aggregate stability score;
- no statistical significance threshold;
- no equivalence margin;
- no rule preferring one selector because it is more stable in a subset of
  scenarios.

Accordingly, the stability results **must not be converted into a new
post-hoc OPS-versus-SR decision rule**.

The existing selector decision therefore remains:

**UNRESOLVED**

Update stability does not select OPS and does not select SR.

The earlier one-per-species hypothesis remains not rejected by the frozen
coverage comparison, but that is not equivalent to selecting OPS.

## Validation status after this checkpoint

The final 300/2400 selector-v1 validation has now completed:

- final geometry reconstruction and input-order invariance;
- OPS-versus-SR structural coverage;
- random-baseline comparison;
- final selector-decision checkpoint;
- leave-one-feature-out sensitivity;
- grouped feature-family sensitivity;
- broader deterministic rebuild;
- update-stability validation.

The 12-coordinate final 300/2400 structural feature schema remains intact.

The remaining step is not another post-hoc selector metric. It is a
release-final decision/audit checkpoint that reconciles the already frozen
evidence with the already frozen selector-decision rules and records whether
selector v1 can be finalized or must remain unresolved.

Genome and species identities remain blinded.
