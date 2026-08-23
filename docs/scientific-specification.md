# BacSelect scientific specification

## Status

Draft specification for BacSelect v1.

This document defines the intended scientific behaviour of BacSelect before
implementation of the production selector or release of any BacSelect panel.

Nothing in this document is a released BacSelect result.

The following scientific decisions remain explicitly open until prospective
validation is complete:

- the final BacSelect architecture feature schema;
- the final repeat scales;
- whether selector v1 enforces one genome per species or permits
  species-balanced within-species representation;
- the final NCBI genome-note exclusion and review policy.

## Purpose

BacSelect generates compact, reproducible panels of complete bacterial genomes
for benchmarking, method development, workflow testing, and related
computational genomics applications.

A user chooses the number of genomes, N.

BacSelect returns the first N genomes from a deterministic diversity ranking of
the current eligible bacterial genome universe.

BacSelect is designed to span bacterial genome architecture.

It does not claim to represent:

- bacterial prevalence;
- ecological abundance;
- clinical importance;
- pathogen importance;
- phylogenetic diversity in every sense;
- all forms of biological diversity.

Species names, clinical relevance, pathogen status, publication status, and
downstream benchmark performance are not selection variables.

## Scope and limitations

BacSelect represents structural diversity among eligible public complete
bacterial genome assemblies in its defined source universe.

BacSelect does not represent all bacterial life.

The source universe necessarily reflects biases in:

- which bacteria have been sampled;
- where and from whom or what they were sampled;
- which organisms can be cultured or otherwise recovered;
- which genomes have been sequenced;
- which sequencing technologies and assembly methods were used;
- which genomes have been assembled to completion;
- which assemblies have been deposited in public archives; and
- how deposited genomes are taxonomically classified.

BacSelect is intended to reduce arbitrary or abundance-driven genome selection
within this explicitly defined universe.

It cannot remove biases already present in the underlying public data.

A BacSelect panel must therefore be described as structurally diverse within
its stated release universe, not as an absolute or unbiased representation of
all bacteria.

BacSelect v1 does not federate independent genome collections outside the
INSDC/GenBank assembly archive. Expansion to additional genuinely independent
source collections would require explicit duplicate reconciliation,
eligibility harmonisation, provenance, licensing, and validation before those
sources could enter the selection universe.

## Release model

BacSelect is refreshed monthly.

A new source snapshot is initiated on the first day of each calendar month.

The release identifier is:

`YYYY.MM`

Publication occurs only after all validation requirements for that snapshot
pass.

A failed or unresolved validation blocks publication rather than silently
changing eligibility rules.

Every published release is immutable.

`latest` may point to the newest validated release but must never replace or
modify a historical release.

## Source universe

The prospective BacSelect v1 source universe comprises eligible public complete
bacterial genome assemblies in the International Nucleotide Sequence Database
Collaboration (INSDC) / GenBank assembly archive, accessed reproducibly through
NCBI Datasets.

NCBI Datasets is therefore the BacSelect v1 retrieval interface. BacSelect does
not claim that NCBI is the only genomic database or that this source universe
contains all bacterial genomes.

Candidate discovery targets:

- taxon Bacteria;
- GenBank assemblies (`GCA_`);
- assembly level `Complete Genome`;
- current assembly versions;
- non-MAG assemblies;
- non-multi-isolate assemblies.

The raw NCBI assembly metadata response is retained unchanged as release
provenance.

The discovery query uses the NCBI Datasets `--assembly-version current`
setting. In the returned assembly metadata, the assembly status must be
`latest`; `replaced` and `suppressed` assemblies are not eligible.

The distinction between query terminology (`current`) and returned assembly
status (`latest`) must be covered by validation tests.

The exact NCBI Datasets version, command, retrieval timestamp, source hashes,
and relevant environment information are recorded for every release.

## Why GenBank assemblies

BacSelect uses the canonical GenBank (`GCA_`) assembly as its source assembly
identifier.

Paired RefSeq (`GCF_`) records are not treated as independent genomes.

This prevents GenBank/RefSeq pairs from contributing duplicate opportunities
for selection.

## Atypical assembly metadata

BacSelect does not automatically exclude every assembly labelled `atypical` by
NCBI.

Atypical warnings are frozen as metadata and evaluated under explicit BacSelect
rules.

Environmental origin, unusual genome size, or other biological unusualness is
not itself grounds for exclusion.

Warnings that establish that the assembly does not represent a single,
structurally interpretable bacterial genome may exclude a candidate.

The initial automatic exclusion set is intended to include:

- chimeric;
- contaminated;
- mixed culture.

The exact accepted warning strings must be frozen from the NCBI schema before
production implementation.

## BioSample requirement and repeated BioSamples

Every candidate must have a valid accession-like BioSample identifier.

A BioSample represented by more than one current eligible GenBank complete
assembly triggers reconciliation.

For a repeated BioSample:

1. if candidate source-genome component fingerprints are exactly identical,
   retain one deterministic canonical assembly and mark the others as duplicate
   representations;

2. if current candidate assemblies are not sequence-identical, fail closed for
   automated selection unless a separately frozen reconciliation procedure
   resolves the group.

Repeated BioSample membership is a reconciliation trigger, not proof that
assemblies are biologically interchangeable.

## Source-genome boundary

The BacSelect source genome is the set of component nucleotide sequences
assigned to the NCBI `Primary Assembly` unit of the canonical GenBank assembly.

Additional package assembly units do not contribute to:

- structural features;
- sequence fingerprints;
- BacSelect selection geometry.

## Sequence eligibility

Every retained Primary Assembly component must:

- be retrievable from the frozen source package;
- reconcile to the expected assembly component;
- have a stable accession.version and sequence checksum;
- contain only A, C, G, and T for primary structural calculations;
- have sufficient topology and molecule-location information for the frozen
  structural feature definitions.

Sequence validation is performed before panel selection.

## Source structural integrity

Source-genome integrity is evaluated independently of panel membership.

Exact duplicate Primary Assembly components are not eligible.

A fully contained linear Primary Assembly component is not eligible when it
does not contribute a unique structural sequence truth.

Circular contained components may remain eligible because circular closure
provides a distinct topology-specific adjacency.

Potentially ambiguous chromosome-component architecture triggers source
replicon-integrity review.

Review outcomes are:

- retain;
- exclude;
- unresolved.

Unresolved candidates fail closed.

Cached adjudications may be reused only when the exact assembly accession
version and relevant source evidence are unchanged.

## Species resolution

Species grouping uses a frozen NCBI Taxonomy snapshot associated with each
monthly BacSelect release.

For each eligible genome, lineage traversal begins from its structured NCBI
Taxonomy identifier.

The first ancestral taxon whose rank is exactly `species` defines the canonical
species group.

Merged TaxIDs are normalized through the frozen taxonomy snapshot.

Deleted, missing, cyclic, or otherwise unresolved TaxIDs fail closed for
species-based selection.

Species names are descriptive output only.

Canonical species TaxIDs are grouping identifiers and are never interpreted
numerically as selection scores.

## Candidate structural feature schema

The first BacSelect candidate architecture schema inherits the 12
sequence-derived structural features developed and validated for Project
Finch:

1. total genome length;
2. whole-genome GC fraction;
3. replicon count;
4. non-chromosomal replicon count;
5. non-chromosomal sequence fraction;
6. non-unique canonical 150-mer fraction;
7. non-unique canonical 400-mer fraction;
8. maximum canonical 150-mer multiplicity;
9. maximum canonical 400-mer multiplicity;
10. longest exact repeat length;
11. inter-replicon shared canonical 150-mer fraction;
12. inter-replicon shared canonical 400-mer fraction.

Canonical k-mers treat a sequence and its reverse complement as equivalent.

Circular replicons are processed topology-aware across the recorded FASTA
origin.

The 150-bp and 400-bp repeat scales were originally chosen for Project Finch
because they correspond to the frozen PE150 read length and approximate
paired-fragment scale used in that benchmark.

They are therefore not automatically assumed to be the final general-purpose
BacSelect repeat scales.

Before architecture schema v1 is frozen, prospective validation must test:

- alternative repeat scales;
- feature-scale sensitivity;
- feature ablation;
- correlation and redundancy among structural dimensions; and
- whether the selected panel remains structurally stable under reasonable
  alternative feature definitions.

No BacSelect architecture schema version is released until this validation is
complete.

## Feature caching

Raw structural features are properties of a frozen assembly sequence and do not
need to be recomputed every month when the source sequence is unchanged.

Feature results are cached against immutable sequence and assembly provenance.

A new or sequence-revised assembly requires feature computation.

Taxonomy, eligibility, percentile coordinates, species representatives, and
the final ranking are rebuilt for every monthly release.

## Species-balanced percentile geometry

BacSelect does not allow a heavily sequenced species to dominate feature
scaling merely because more genomes have been deposited for that species.

For species s containing n_s eligible genomes, each genome i in species s is
assigned weight:

    w_i = 1 / n_s

Every species therefore contributes total weight 1 to each feature's empirical
distribution.

If the release contains S eligible species groups, total feature weight is S.

For a raw feature value x, define:

    W_less(x) = sum of genome weights for values < x
    W_equal(x) = sum of genome weights for values = x

The species-balanced percentile coordinate is:

    p(x) = [W_less(x) + 0.5 * W_equal(x)] / S

All tied raw values receive the same coordinate.

A constant feature maps to 0.5.

Percentile calculations must use exact deterministic arithmetic before
fixed-precision output.

All 12 percentile dimensions have equal weight in selector v1 unless the
prospective validation programme demonstrates that this must be revised before
release.

## Provisional one-representative-per-species design

The initial BacSelect selector design exposes one candidate genome per eligible
species group.

This is a prospective design hypothesis rather than a frozen BacSelect v1
requirement.

Before selector v1 is frozen, this design must be compared with at least one
species-abundance-controlled alternative that permits more than one genome
from a species when doing so materially expands structural coverage.

The comparison must use pre-specified quantitative metrics rather than
inspection of organism identities.

Under the provisional one-representative-per-species design, for each
species:

1. calculate the centroid of all eligible member genomes in the
   12-dimensional species-balanced percentile space;

2. calculate squared Euclidean distance from every genome in that species to
   the species centroid;

3. choose the genome with the smallest distance as that species'
   representative.

An exact tie is resolved by frozen canonical genome order.

The number of deposited genomes in a species is not a direct ranking variable.

## Provisional global diversity ladder

Under the provisional one-representative-per-species design, the global
BacSelect ladder is generated only from the one representative genome selected
for each eligible species group.

Let R contain one representative genome per species.

All distances use squared Euclidean distance in the 12-dimensional
species-balanced percentile space.

### First genome

Calculate the centroid of all genomes in R.

Rank 1 is the representative genome nearest that global centroid.

### Subsequent genomes

For each unselected representative, calculate its minimum distance to any
representative already selected.

Select the genome maximizing that minimum distance.

Repeat until every species representative has been ranked.

Exact ties use frozen canonical species order only as the final tie-breaker.

Species names, TaxID numeric magnitude, accession identity, biological
importance, and downstream benchmark behaviour are not ranking variables.

## Nested panel property

The complete diversity ladder is generated once per monthly release.

A BacSelect panel of size N is exactly the first N rows of that ladder.

Therefore:

- the N=10 panel is a prefix of N=20;
- the N=20 panel is a prefix of N=50;
- the N=50 panel is a prefix of N=100;
- and so forth.

Changing N never replaces an already selected genome with an unrelated
selection from the same release.

## Public panel-size range

The initial BacSelect website exposes:

- 10;
- 20;
- 50;
- 100;
- 200;
- 500;

plus custom integer N from 10 through 500.

The production ranking itself is not limited to 500 and should rank every
eligible species representative.

The public maximum may be increased in a later interface release without
changing the selector.

## Structural coverage reporting

BacSelect does not assign an arbitrary percentage called `coverage`.

For a panel of size N, calculate the distance from every eligible species
representative to its nearest selected panel genome.

Report at minimum:

- median nearest-panel distance;
- 95th-percentile nearest-panel distance;
- maximum nearest-panel distance.

Comparisons between panel sizes may report the relative reduction in these
distances.

Monthly release comparisons must evaluate old and new panels against the same
comparison universe before attributing a change to improved structural
coverage.

## Required release artefacts

Each monthly release must preserve sufficient information to reproduce and
audit the panel.

Required release artefacts include:

- source snapshot metadata;
- eligibility table;
- exclusion/review table;
- taxonomy snapshot identity;
- species-resolution table;
- raw structural-feature table;
- species-balanced percentile matrix;
- species-representative table;
- complete diversity ladder;
- selector trace;
- release summary;
- checksums;
- machine-readable provenance.

Human-facing downloads will include at least:

- Excel metadata;
- TSV metadata;
- accession list.

FASTA delivery must not compromise release reproducibility or require large
sequence archives to be stored directly in the website repository.

## Version identity

A user-visible BacSelect result is identified by at least:

- BacSelect release `YYYY.MM`;
- selector version;
- structural-feature schema version;
- N.

For example:

`BacSelect 2027.04 / selector 1.0.0 / architecture 1 / N=100`

Historical releases are immutable.

A change to scientific selection semantics requires an explicit selector or
architecture-schema version change.

## Validation before BacSelect v1.0

The selector must not be released as BacSelect v1.0 until prospective validation
has tested at least:

- deterministic byte-identical rebuilds;
- invariance to input row permutation apart from defined exact ties;
- exact nestedness for all exposed N;
- exactly one selected genome per species;
- exclusion of species names and biological-priority fields from selection;
- species-abundance balancing;
- repeat-scale, feature-scale, and feature-ablation sensitivity;
- correlation and redundancy among candidate architecture features;
- comparison with species-balanced random panels;
- comparison of the provisional one-representative-per-species design with at
  least one species-abundance-controlled design that permits multiple genomes
  from the same species;
- structural-distance behaviour as N increases;
- stability under historical or simulated monthly source updates;
- behaviour when accessions are added, replaced, or suppressed;
- comparison with the frozen Project Finch 40-genome panel at N=40.

The validation design must be frozen before BacSelect panel identities are
examined.

## Relationship to Project Finch

Project Finch motivated BacSelect but remains scientifically separate.

The frozen Project Finch Experiment 0 panel is not regenerated or replaced.

Its 40-genome / 25-species design answered a benchmark-specific question that
included deliberate within-species structural sampling.

BacSelect v1 instead constructs a general species-balanced diversity ladder
with one representative genome per species.

Project Finch may use or compare with future BacSelect releases, but BacSelect
does not depend on Project Finch benchmark outcomes.
