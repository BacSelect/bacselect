# Base-12 grouped feature-ablation interpretation

This interpretation follows the frozen identity-blind grouped feature-ablation
report:

`base12-grouped-ablation.tsv`

SHA256:

`ac753b9c240aa33b11f70a875ef8584814a5cc4185e7c686f5f114483eb66962`

The grouped-ablation result was frozen and independently reproduced before its
coverage and panel-overlap values were inspected.

## Overall result

Grouped feature-family ablation does not provide evidence for removing any of
the four pre-specified feature families from selector v1.

The largest observed grouped-ablation effect is associated with removal of the
five-coordinate `repeat_architecture` family.

Removal of `basic_genome_properties` and `replicon_architecture` also worsens
upper-tail or worst-species structural coverage at larger panel sizes.

Removal of `inter_replicon_sharing` has comparatively little effect on the
primary weighted-p95 metric, but still worsens coverage of the most poorly
represented species.

These results reinforce the leave-one-feature-out conclusion that apparently
modest effects on broad coverage summaries do not demonstrate that a
structural dimension or family is dispensable.

No feature family is removed on the basis of this analysis.

## Repeat architecture

The `repeat_architecture` family contains:

- non-unique canonical 150-mer fraction;
- non-unique canonical 400-mer fraction;
- maximum canonical 150-mer multiplicity;
- maximum canonical 400-mer multiplicity;
- longest exact repeat length.

Removing all five coordinates produces the largest observed grouped-ablation
effect.

For weighted-p95, the grouped-ablation minus full base-12 differences are
positive at all six panel sizes for both selectors.

At N=500:

- OPS weighted-p95 increases by `+0.193809888`;
- SR weighted-p95 increases by `+0.224673899`;
- OPS `max_species_mean` increases by `+0.414115463`;
- SR `max_species_mean` increases by `+0.513520678`;
- OPS `p95_species_max` increases by `+0.205277617`;
- SR `p95_species_max` increases by `+0.244089516`.

The N=500 grouped panels retain only:

- 79/500 genomes from the corresponding full base-12 OPS panel;
- 91/500 genomes from the corresponding full base-12 SR panel.

At N=10 and N=20, neither repeat-ablation selector shares any genomes with the
corresponding full base-12 panel.

The result supports substantial dependence on the pre-specified repeat-
architecture family as a whole.

It does not establish that every repeat coordinate is individually necessary,
nor does it permit a per-feature comparison with the smaller feature families.
The repeat-architecture group contains five coordinates, whereas the other
groups contain two or three.

## Basic genome properties

The `basic_genome_properties` family contains genome length and whole-genome
GC fraction.

At N=500, removing this family increases weighted-p95 by:

- `+0.080616228` for OPS;
- `+0.068866574` for SR.

The corresponding changes in `max_species_mean` are:

- `+0.262658284` for OPS;
- `+0.190421625` for SR.

The effect is most consistent at the larger panel sizes. Some smaller-N
metrics improve after ablation, but these local changes do not establish that
the family is harmful or unnecessary because removing coordinates changes the
entire maximin or residual selection trajectory.

The N=500 panel overlaps are:

- 137/500 for OPS;
- 128/500 for SR.

Genome length and GC therefore continue to contribute materially to the
base-12 selection geometry.

## Replicon architecture

The `replicon_architecture` family contains:

- replicon count;
- non-chromosomal replicon count;
- non-chromosomal sequence fraction.

At N=500, removal produces slightly lower central-distance summaries:

- OPS weighted mean: `-0.007693283`;
- OPS weighted median: `-0.021506552`;
- SR weighted mean: `-0.006506283`;
- SR weighted median: `-0.018758051`.

However, upper-tail and worst-species coverage worsen:

- OPS weighted-p95: `+0.052925992`;
- SR weighted-p95: `+0.047460939`;
- OPS `max_species_mean`: `+0.289852369`;
- SR `max_species_mean`: `+0.316615544`;
- OPS `p95_species_max`: `+0.080075976`;
- SR `p95_species_max`: `+0.073535427`.

The numerical extreme also worsens by:

- `+0.118082887` for OPS;
- `+0.148122530` for SR.

This is a clear example of poorer upper-tail and worst-species coverage being
masked by improved central-distance summaries.

The N=500 overlaps are:

- 125/500 for OPS;
- 117/500 for SR.

The grouped result therefore does not support removal of replicon architecture.

## Inter-replicon sharing

The `inter_replicon_sharing` family contains the shared canonical 150-mer and
400-mer fractions across replicons.

Its effect on the primary weighted-p95 metric is comparatively small at
N=500:

- OPS: `+0.010843792`;
- SR: `+0.005898672`.

Central-distance metrics improve modestly after removal.

However, worst-species coverage still deteriorates:

- OPS `max_species_mean`: `+0.162462669`;
- SR `max_species_mean`: `+0.237566186`;
- OPS `p95_species_max`: `+0.031980070`;
- SR `p95_species_max`: `+0.029756988`.

The N=500 overlaps are:

- 128/500 for OPS;
- 123/500 for SR.

The grouped result therefore does not demonstrate that inter-replicon sharing
is redundant. Its contribution is more apparent in poorly covered species than
in central or weighted-p95 summaries.

## Panel-composition sensitivity

Grouped feature removal changes panel composition substantially for every
feature family.

At N=500, overlap with the corresponding full base-12 panel is:

| Removed family | OPS overlap | SR overlap |
| --- | ---: | ---: |
| basic genome properties | 137/500 | 128/500 |
| replicon architecture | 125/500 | 117/500 |
| repeat architecture | 79/500 | 91/500 |
| inter-replicon sharing | 128/500 | 123/500 |

Thus, aggregate coverage similarity does not imply panel-membership stability.

This is consistent with the leave-one-feature-out result, in which N=500 panel
overlap was also low despite several individual ablations having small effects
on weighted-p95.

## Relationship to leave-one-feature-out analysis

The grouped-ablation results strengthen the main conclusions from the
leave-one-feature-out analysis.

In particular:

1. repeat-related dimensions collectively carry substantial structural
   information;
2. basic genome length and GC remain important to upper-tail coverage;
3. replicon architecture can appear comparatively favourable under central
   summaries while still protecting against poorly covered species;
4. inter-replicon sharing has a relatively small effect on broad summaries but
   retains detectable value for worst-species coverage;
5. panel composition is highly sensitive to the feature schema.

No single-feature or grouped-ablation result justifies removal of a frozen
base-12 coordinate at this stage.

## Interpretation limits

The magnitudes of grouped-ablation effects must not be interpreted as
per-feature importance scores.

The groups contain different numbers of coordinates:

- basic genome properties: 2;
- replicon architecture: 3;
- repeat architecture: 5;
- inter-replicon sharing: 2.

Grouped removal also changes the sequential selection trajectory, so negative
metric deltas at individual panel sizes do not demonstrate that the removed
family is detrimental.

The analysis evaluates sensitivity to the pre-specified feature families. It
does not estimate causal importance, statistical independence, or an optimal
number of coordinates.

`unweighted_max` and `max_species_max` are numerically identical by
construction and are not treated as independent supporting observations.

## Consequence for selector v1

The base-12 structural-feature schema remains unchanged after grouped
feature-ablation analysis.

No feature family is removed.

The strongest grouped dependence is observed for the pre-specified repeat-
architecture family, but repeat-scale validation remains necessary because
the current 150-mer and 400-mer scales were inherited from the Project Finch
short-read experimental design rather than established prospectively for
BacSelect.

The grouped-ablation analysis does not resolve the OPS versus SR selector
decision. That decision remains open under the pre-specified comparison rule.

Genome and species identities remain blinded.

Repeat-scale validation is the next feature-schema analysis. Input-order
invariance, broader deterministic rebuild validation, and update-stability
analysis also remain separately pre-specified before selector v1 and the
BacSelect structural-feature schema are frozen.
