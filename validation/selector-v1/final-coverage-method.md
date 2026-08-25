# Final selector-v1 300/2400 coverage validation method

This method is frozen before calculating coverage outcomes in the final
300/2400 feature geometry.

## Inputs

The analysis uses the frozen final selector-v1 feature space and the frozen
baseline identities:

- 55,306 genomes;
- 13,765 species groups;
- panel sizes N = 10, 20, 50, 100, 200, and 500;
- OPS N=500 ladder SHA256
  `ab5d75b2d35b9577bcf84acceb8e10d847e983e04a8e4aa5859fd0bde1ae2834`;
- SR N=500 ladder SHA256
  `080cbaf23d9259610d59fc1ef5a3164329e0bbbe9016b21590c0b34ad2da1b97`;
- species-balanced random ladder-set SHA256
  `9394a26ded92fb2baafea0101b837335e9d434f4cd3d8c6484ef61bbf0741719`.

The OPS and SR ladders are reconstructed and required to match their frozen
identity-blind fingerprints before coverage is evaluated.

## Coverage evaluation

For every panel size, the nearest-panel distance is calculated for every
eligible genome in the final 12-dimensional species-balanced percentile
geometry.

The same pre-specified `CoverageSummary` fields used by the historical
selector-v1 validation are retained. No metric is added or removed.

## Primary OPS-versus-SR comparison

The primary metric is `weighted_p95`, the species-balanced weighted 95th
percentile nearest-panel distance. Lower is better.

The primary comparison is evaluated at all six frozen panel sizes.

The automatic-winner rule is unchanged:

- if OPS has the lower primary metric at all six N values, OPS is the automatic
  primary winner;
- if SR has the lower primary metric at all six N values, SR is the automatic
  primary winner;
- if the curves cross, there is no automatic primary winner;
- if all six primary values tie, there is no automatic primary winner.

The primary comparison script records only that rule. It does not construct a
new aggregate score, significance threshold, or post-hoc selector criterion.

If the primary curves are not uniformly ordered, interpretation of the already
pre-specified secondary metrics remains a later decision-record step. This
calculation does not automate or redefine that interpretation.

## Random baseline

The random baseline retains the historical prospective protocol:

- 1,000 species-balanced random ladders;
- maximum N = 500;
- master seed = 20260824;
- `numpy.random.Generator(PCG64)`;
- one generator, sequential replicates;
- the same six panel sizes;
- the same coverage metrics.

The random membership ladder set is required to match the already frozen
identity because the genome universe, species mapping, seed, and sampling
protocol are unchanged. Coverage distances are recalculated because the
feature geometry changed from 150/400 to 300/2400.

Random coverage summaries use empirical inverse-CDF quantiles without
interpolation at 1/40, 1/2, and 39/40.

The first five replicate coverage results are evaluated twice within the same
prospective run and required to produce the same deterministic fingerprint.
That fingerprint is an output of the final geometry, not a historical expected
value.

## Candidate versus random comparison

For every N, selector, and pre-specified coverage metric, the candidate value
is compared against all 1,000 random replicate values using the existing
`lower_is_better_empirical_rank` implementation.

The comparison is descriptive support. It does not introduce a new
OPS-versus-SR selector decision criterion and does not itself choose a
selector.

## Identity blindness

No organism name, taxonomic label, pathogen status, clinical relevance,
publication status, or assembler performance is used to choose between OPS and
SR. Panel identities remain uninspected during this validation stage.

## Freeze sequence

1. Commit and push this prospective method and implementation before running
   the final coverage calculations.
2. Calculate OPS-versus-SR coverage and the random coverage distribution under
   that exact commit.
3. Freeze those outputs and hashes.
4. Calculate and freeze OPS/SR empirical ranks against the frozen random
   distribution using the already committed comparison implementation.
5. Apply the pre-specified selector decision rule in a separate decision
   record. If the evidence remains mixed, record the selector decision as
   unresolved rather than inventing a new post-hoc score or threshold.
