# BacSelect selector-v1 prospective monthly production and release method

## Status

This document prospectively freezes the production architecture for recurring
BacSelect selector-v1 monthly releases.

It is written after:

- selector-v1 validation has completed;
- OPS has been prospectively selected and frozen as selector v1;
- the winning OPS reference ladder has been unblinded and audited;
- official selector-v1 reference panels have been generated independently
  twice and shown to be byte-identical;
- aggregate reference-panel completion evidence has been committed and pushed.

It is written before:

- any monthly source snapshot is initiated under this production architecture;
- any dated `YYYY.MM` BacSelect release is assigned;
- any monthly production implementation is executed;
- any public monthly release is packaged or published.

This document defines production architecture before the first dated release
outcome exists.

## Scientific authority

The frozen scientific specification is:

`docs/scientific-specification.md`

SHA256:

`93114676f8510e9df57459153316266f7d57b7cfe380e09849bddf8e62d2cddf`

The authoritative selector-decision record is:

`validation/selector-v1/stage7-selector-decision-record.json`

SHA256:

`d0cf63ad4d933194e3e782912a2a2a3c617353758d2c87c1b1198681a75869e2`

The winning selector is:

`OPS`

The frozen selector version is:

`1.0.0`

The frozen structural architecture schema version is:

`1`

The completed selector-v1 reference-panel evidence is:

`validation/selector-v1/official-selector-v1-panel-completion-evidence.json`

SHA256:

`c767483ca238e76f5448decc5d7810608cbf3da7642c060e1566ec630141ff53`

The reference-panel completion evidence is scientific validation evidence.
It is not a monthly release and must never be relabelled as one.

## Release calendar

BacSelect monthly release boundaries are evaluated in UTC.

This operational rule removes dependence on the timezone configured on an
execution host.

A release identifier has the exact form:

`YYYY.MM`

A source snapshot for release `YYYY.MM` may be initiated only when the UTC
calendar date is within that same year and month and the UTC day-of-month is
exactly `01`.

A snapshot initiated on any later UTC day may be retained as operational or
development evidence, but it cannot be retrospectively labelled as that
month's canonical BacSelect source snapshot.

The release identifier is derived from the authorized snapshot-start UTC
timestamp.

It must not be supplied independently in a way that can disagree with that
timestamp.

## Monthly release identity

Every published monthly result is identified by at least:

- BacSelect release `YYYY.MM`;
- selector version `1.0.0`;
- architecture schema version `1`;
- requested panel size N.

Historical releases are immutable.

`latest` is a pointer to the newest successfully published immutable release.

Updating `latest` must never modify a historical release.

## Source-snapshot initiation boundary

A monthly production run begins with a release-start checkpoint written before
the first external source query.

The release-start checkpoint must contain at least:

- schema version;
- snapshot-start UTC timestamp;
- derived release identifier;
- expected Git execution commit;
- source-universe query specification;
- NCBI Datasets environment identity;
- selector version;
- architecture schema version;
- status indicating that source acquisition has not yet completed.

The checkpoint must be written atomically to fresh scratch storage.

After the checkpoint exists, its release identifier and start timestamp are
immutable.

The first NCBI source query must occur only after this checkpoint has been
successfully written and read back.

## Source universe

Monthly discovery follows the frozen BacSelect v1 source-universe rules.

Candidate discovery targets:

- taxon Bacteria;
- GenBank assembly accessions only;
- canonical `GCA_` accessions;
- assembly level exactly `Complete Genome`;
- current assembly versions;
- non-MAG assemblies;
- non-multi-isolate assemblies.

The NCBI Datasets query must explicitly request current assembly versions.

Returned assembly status must be exactly `current`.

Previous, suppressed, retired, unknown, missing or unrecognized assembly
statuses fail closed.

The complete raw NCBI assembly metadata response is retained unchanged as
release provenance.

The production record must bind:

- exact NCBI Datasets version;
- exact command and arguments;
- source-query start and completion UTC timestamps;
- raw-response SHA256;
- relevant environment identity;
- production Git commit.

## Production code architecture

Monthly production must use dedicated parameterized production wrappers.

Historical selector-validation executors must not be invoked directly when
they embed:

- historical snapshot identifiers;
- historical commit identifiers;
- fixed source manifests;
- fixed scratch paths;
- validation-only holdout logic;
- validation-only blinded selector comparison logic.

Scientific primitives from the validated implementation may be reused when
their exact identities and applicable scientific semantics are frozen.

Any reused component must receive current monthly inputs explicitly rather than
implicitly through a historical constant.

Production wrappers must fail closed when a historical fixed input would
otherwise be inherited.

## Monthly stage model

Monthly production is an ordered fail-closed chain.

Successful completion of an upstream stage is required before the next stage
may execute.

The monthly production stages are:

1. release-start and source-snapshot acquisition;
2. cache-reuse and fresh-sequence acquisition planning;
3. sequence acquisition and immutable source-evidence verification;
4. source-truth and sequence eligibility;
5. repeated-BioSample handling;
6. source structural-integrity handling;
7. monthly taxonomy-snapshot acquisition;
8. taxonomy resolution;
9. complete eligible monthly universe construction;
10. raw structural-feature cache reuse and computation;
11. monthly species-balanced percentile geometry;
12. monthly species-representative construction;
13. complete OPS diversity-ladder construction;
14. public panel and structural-coverage generation;
15. release packaging and deterministic rebuild;
16. publication gate.

No later stage may silently repair, reinterpret, or bypass a failed earlier
stage.

## Stage 1: source snapshot

The full monthly public-assembly metadata snapshot is acquired through NCBI
Datasets.

The snapshot must be new for the monthly release.

The raw metadata response is immutable evidence.

Source discovery and source eligibility are separate operations.

No scientific filtering may occur before the raw source response has been
retained and fingerprinted.

## Stage 2: cache reuse and fresh acquisition planning

The production workflow deterministically partitions monthly candidates into:

- exact reusable cached source evidence;
- fresh or sequence-revised source evidence requiring acquisition.

Cache reuse is permitted only when immutable source identity is sufficient to
prove that the sequence evidence relevant to downstream decisions is unchanged.

At minimum, reuse must bind:

- canonical assembly accession.version;
- relevant assembly/component identity;
- sequence checksum;
- source-evidence checksum;
- applicable frozen adjudication identity where reused.

Accession identity alone is insufficient for sequence-derived cache reuse.

A changed or unverifiable source must be reacquired or fail closed.

## Stage 3: sequence acquisition and verification

Fresh source sequence evidence is acquired reproducibly through the frozen
NCBI Datasets environment or its prospectively versioned successor.

Every retained Primary Assembly component must:

- be present;
- reconcile to the expected assembly component;
- carry stable accession.version identity;
- match its recorded sequence checksum;
- satisfy frozen sequence-composition requirements;
- provide the topology and molecule-location evidence required by selector-v1.

Partial, ambiguous or inconsistent acquisition states fail closed.

Failed acquisition evidence is retained and never silently converted into an
eligible source.

## Stage 4: source truth and eligibility

The frozen selector-v1 source-truth and post-sequence eligibility semantics
remain authoritative.

Monthly production must not weaken those rules to preserve a desired panel
size or accession.

Eligibility is evaluated before panel selection.

Publication status, organism popularity, clinical importance and previous
panel membership are not eligibility overrides.

## Stage 5: repeated BioSamples

Repeated-BioSample handling follows the frozen selector-v1 scientific rules.

Cached prior adjudication may be reused only when all source evidence on which
that adjudication depended is unchanged.

A monthly wrapper must explicitly bind the evidence supporting each reused
adjudication.

Unresolved repeated-BioSample cases fail closed.

## Stage 6: source structural integrity

Source structural-integrity rules remain independent of panel membership.

Exact duplicate Primary Assembly components are not eligible.

Fully contained linear Primary Assembly components are handled according to the
frozen selector-v1 rule.

Circular topology-specific components remain subject to the frozen distinction.

Potentially ambiguous chromosome/component architecture must undergo the
frozen review logic.

Unresolved cases fail closed.

## Stage 7: monthly taxonomy snapshot

Each monthly BacSelect release has its own frozen NCBI Taxonomy snapshot.

The taxonomy acquisition implementation must be parameterized by the current
monthly source snapshot.

It must not inherit a historical hard-coded source snapshot identifier or
historical source snapshot commit.

The taxonomy snapshot has a deterministic identity derived from its acquisition
start UTC timestamp and content.

It must bind:

- monthly release identifier;
- monthly source-snapshot identity;
- source-snapshot SHA256;
- taxonomy acquisition start/completion UTC timestamps;
- taxonomy source identities;
- content manifest;
- production implementation identity.

A taxonomy snapshot from another monthly release cannot be substituted merely
because its content appears similar.

## Stage 8: taxonomy resolution

Species grouping follows the frozen selector-v1 rule.

For every eligible candidate, lineage traversal begins at the structured NCBI
Taxonomy identifier.

The first ancestral taxon whose rank is exactly `species` is the canonical
species group.

Merged TaxIDs are normalized through the current monthly frozen taxonomy
snapshot.

Deleted, missing, cyclic or unresolved taxonomy fails closed.

Species names are descriptive output only.

Canonical species TaxIDs are grouping identifiers and are not numerical
selection scores.

## Stage 9: complete monthly universe

The monthly complete universe contains all candidates that pass the current
monthly source, sequence, structural-integrity and taxonomy gates.

Monthly production does not reconstruct the historical selector-validation
baseline.

Monthly production does not construct an external holdout.

Monthly production does not perform the Stage 5 baseline-intersection logic
used for selector resolution.

The monthly complete universe itself is the source population for current
selector-v1 production.

Its ordered membership and species-group membership must be deterministically
fingerprinted.

## Stage 10: structural-feature cache and computation

Raw structural features are immutable properties of frozen sequence evidence
under a frozen architecture implementation.

Exact reusable feature results may be reused when:

- assembly accession.version is unchanged;
- relevant component sequence checksums are unchanged;
- topology/component evidence relevant to the feature is unchanged;
- architecture schema version is unchanged;
- feature implementation identity is compatible with the cached result.

New or sequence-revised eligible assemblies require feature computation.

Feature-cache provenance must distinguish reused and newly calculated rows.

Taxonomy, species balance, percentile coordinates, representative selection and
final ranking are never reused merely because raw feature values are cached.

## Stage 11: monthly percentile geometry

The complete monthly eligible universe is used to rebuild the selector-v1
species-balanced percentile geometry every month.

The frozen selector-v1 percentile definition remains authoritative.

For each species containing n eligible genomes, every genome receives species
weight:

`1 / n`

Every species contributes total weight one.

Tied values use the frozen midpoint rule.

A constant feature maps to `0.5`.

Exact deterministic arithmetic is required before fixed-precision output.

All twelve selector-v1 structural dimensions have equal weight.

Monthly coordinates must never be copied from a previous release.

## Stage 12: monthly species representatives

Species-representative construction is rerun for the current monthly universe.

The implementation must use the exact frozen selector-v1 representative
semantics.

No previous-release representative receives incumbency preference.

Previous panel membership is not a tie-breaker.

The release preserves a machine-readable species-representative table.

## Stage 13: OPS ladder

OPS is the sole production selector for selector version `1.0.0`.

Monthly production must not:

- run SR as an alternative selector;
- run AG as an alternative selector;
- rerun the OPS-versus-SR selector-resolution decision;
- consult the selector-resolution external holdout;
- calculate the frozen OPS/SR decision product;
- introduce another selector tie-break.

The complete OPS diversity ladder is generated once from the current monthly
eligible representative population.

Production ranking is not limited to 500.

The ladder must rank every eligible species representative supported by
selector-v1.

The public N=10 through N=500 panels are prefixes of this complete ladder.

## Stage 14: public panels

Preset public panel sizes remain:

`10,20,50,100,200,500`

Custom integer N is permitted when:

`10 <= N <= 500`

For any N:

`panel(N) = complete_OPS_ladder[0:N]`

Custom N never reruns OPS.

Changing N never substitutes unrelated members from the same release.

If the current eligible representative population has fewer members than a
requested N, that request fails explicitly rather than silently changing the
selector.

## Structural coverage reporting

For each published preset panel size, calculate nearest-panel distances across
the current eligible species-representative population.

At minimum report:

- median nearest-panel distance;
- 95th-percentile nearest-panel distance;
- maximum nearest-panel distance.

The implementation may preserve the larger frozen deterministic coverage
metric set where useful.

The word `coverage` must not be converted into an arbitrary percentage.

Cross-release claims about improvement require evaluation of both panels
against the same comparison universe.

A simple comparison of each release against its own changing universe is not
sufficient evidence of improvement over time.

## Stage 15: release packaging

Every successfully generated monthly release must preserve sufficient
machine-readable evidence to reproduce and audit the result.

Required scientific/reproducibility artefacts remain:

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

Human-facing downloads must include at least:

- Excel metadata;
- TSV metadata;
- accession list.

The exact monthly release serialization schema, workbook schema and release
directory layout must be prospectively frozen before first production
packaging.

This architecture document does not itself freeze those final presentation
schemas.

## FASTA delivery

FASTA is not required to be stored directly in the website repository.

Any future FASTA delivery mechanism must remain reproducibly bound to the exact
canonical GCA accession.version membership of the immutable release.

FASTA retrieval must not modify the scientific identity of a release.

## Production and rebuild

Every monthly production package must be independently rebuilt from the same
frozen release inputs and pushed implementation commit.

All deterministic scientific and release artefacts required by the final
monthly serialization contract must be byte-identical between production and
rebuild.

Any byte mismatch blocks publication.

Production and rebuild must use separate fresh scratch roots.

## Scratch layout

The monthly production implementation must use a release-scoped and
commit-scoped scratch hierarchy.

The production architecture is:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/monthly/<release-id>/production/<execution-commit>`

The independent rebuild architecture is:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/monthly/<release-id>/rebuild/<execution-commit>`

Source-snapshot acquisition may use a subordinate immutable directory beneath
the same release namespace.

No production run may overwrite an existing release/commit execution root.

## Repository boundary

Scientific production outputs are generated outside Git first.

Identity-bearing release artefacts may enter a public release repository only
through a later explicit packaging/publication gate.

Aggregate completion evidence may be committed to the scientific repository
after deterministic production/rebuild audit.

Production execution must never modify the scientific source repository.

## Publication gate

Publication is allowed only after all frozen monthly gates succeed.

At minimum the publication gate must require:

- source snapshot initiated on UTC day 01;
- release identifier derived correctly from that timestamp;
- source acquisition complete;
- all eligibility stages complete;
- no unresolved fail-closed cases;
- taxonomy snapshot frozen;
- complete monthly universe frozen;
- structural features complete;
- monthly geometry complete;
- species representatives complete;
- complete OPS ladder generated;
- required panels generated;
- structural coverage generated;
- required release package complete;
- production/rebuild deterministic audit passed;
- checksums and provenance complete;
- repository and implementation identities exact.

A failed condition blocks publication.

There is no best-effort publication mode.

## Immutable publication

After successful publication:

- the `YYYY.MM` release is immutable;
- its scientific artefacts and checksums are immutable;
- its user-visible metadata is immutable except for clearly versioned
  non-scientific corrections governed by a separate policy;
- `latest` may move to a later valid release but may not alter a historical
  release.

A scientific change requires a new monthly release and, when selection
semantics change, an explicit selector or architecture-schema version change.

## Failure handling

Operational failure and scientific ineligibility remain distinct.

Failed network acquisition does not make a genome scientifically ineligible.

Failed retrieval is recorded as failed acquisition evidence and blocks any
stage requiring unresolved source evidence.

Failed artefacts are retained where safe for audit.

Production software must not delete or reinterpret failed evidence to make a
release pass.

## No historical hard-coded production inputs

The monthly implementation must reject historical fixed production bindings.

In particular, monthly execution must not rely on:

- `snapshot-20260825T132821Z` as the current source snapshot;
- the historical fixed fresh-download target manifest used during selector-v1
  validation;
- the historical selector-resolution external holdout;
- fixed selector-validation scratch directories;
- a historical validation execution commit masquerading as the monthly
  production commit.

Reusable scientific implementations must be parameterized or wrapped so that
the current monthly evidence is supplied explicitly.

## Monthly production implementation

The implementation should be divided into independently testable layers:

1. release-start and source-snapshot orchestration;
2. monthly source/cache/acquisition orchestration;
3. monthly source eligibility and integrity orchestration;
4. monthly taxonomy orchestration;
5. monthly structural-feature orchestration;
6. monthly geometry and OPS selection;
7. deterministic monthly release packaging;
8. publication gate.

The implementation may reuse frozen pure scientific primitives.

It should not duplicate scientific logic merely to create a monthly wrapper.

## Environment locking

Every production stage that depends on an external executable or Python
environment must bind its exact environment identity.

At minimum the monthly provenance must identify:

- NCBI Datasets environment/version;
- BacSelect Python environment lock;
- production Git commit;
- relevant implementation SHA256 values.

Environment changes must be prospective and testable.

## Implementation tests

Before any real monthly source snapshot is initiated, synthetic tests must
cover at least:

1. valid UTC day-01 release start;
2. UTC day-02 or later release start refusal;
3. release identifier derived from UTC start timestamp;
4. malformed release-start timestamp refusal;
5. attempted caller-supplied mismatching release identifier refusal;
6. dirty Git repository refusal;
7. HEAD mismatch refusal;
8. local `origin/main` mismatch refusal;
9. historical hard-coded source snapshot refusal;
10. historical fixed target-manifest refusal;
11. source-query failure retained as operational failure;
12. current-versus-noncurrent assembly-status handling;
13. cache reuse only for exact immutable source identity;
14. changed sequence forces reacquisition/recomputation;
15. unresolved source truth blocks downstream production;
16. unresolved repeated BioSample blocks downstream production;
17. unresolved structural integrity blocks downstream production;
18. taxonomy snapshot bound to the current monthly source snapshot;
19. unresolved taxonomy blocks production;
20. monthly universe excludes validation holdout logic;
21. raw-feature cache reuse with exact compatible provenance;
22. monthly percentile geometry always rebuilt;
23. monthly representative construction always rebuilt;
24. OPS is the only production selector;
25. SR cannot be selected by monthly production;
26. AG cannot be selected by monthly production;
27. selector-resolution holdout cannot be opened by monthly production;
28. complete OPS ladder is not artificially limited to 500;
29. preset panel prefixes exact;
30. custom N prefix exact;
31. N below 10 refused;
32. N above 500 refused;
33. insufficient ladder length for requested N refused;
34. structural coverage metrics generated without arbitrary percentage;
35. production output root must be fresh;
36. rebuild output root must be fresh;
37. production/rebuild mismatch blocks publication;
38. incomplete release package blocks publication;
39. successful historical release cannot be overwritten;
40. `latest` cannot mutate a historical release.

Unit tests must use synthetic source metadata, synthetic sequences or
lightweight fixtures as appropriate.

Implementation unit tests must not access a real monthly source snapshot.

## First real monthly execution boundary

No real monthly source snapshot may be initiated until:

- this method is committed and pushed;
- monthly release-start/source-snapshot implementation is committed and pushed;
- its synthetic tests pass;
- its execution wrapper is committed and pushed;
- repository HEAD equals local `origin/main`;
- the working tree is clean.

The monthly source-snapshot start itself is a scientific production boundary.

It must not be performed experimentally and then retroactively accepted.

## Prospectivity statement

At the time this method is frozen:

- selector v1 is finalized as OPS;
- selector-v1 reference panels are complete and reproducible;
- those reference panels are explicitly non-monthly;
- no monthly source snapshot has been initiated under this architecture;
- no monthly release identifier has been assigned;
- no monthly production method previously existed;
- no dedicated monthly release-packaging implementation exists;
- historical validation executors contain inputs that are unsuitable for direct
  recurring production without parameterization.

This method freezes recurring production semantics before the first monthly
production snapshot is initiated.
