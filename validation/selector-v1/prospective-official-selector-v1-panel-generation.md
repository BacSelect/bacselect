# BacSelect selector-v1 prospective official panel-generation method

## Status

This document prospectively freezes the method for generating the first
official BacSelect selector-v1 nested panel artefacts from the frozen
selector-validation baseline.

It is written after the selector decision has been finalized, audited,
committed, pushed, and unblinded, but before any official selector-v1 panel
artefact has been generated.

The frozen selector decision is OPS.

This method does not define or publish a monthly BacSelect release.

In particular, execution of this method must not assign a `YYYY.MM` release
identifier to the frozen validation baseline.

A dated BacSelect release requires a source snapshot initiated under the
separate frozen monthly release model.

## Scientific authority

The authoritative selector-decision record is:

`validation/selector-v1/stage7-selector-decision-record.json`

Its SHA256 is:

`d0cf63ad4d933194e3e782912a2a2a3c617353758d2c87c1b1198681a75869e2`

The selector-decision record is committed in:

`d4ba45468baf34b094e7f4bbda8b21a6d8a9de3a`

The frozen winning selector is:

`OPS`

The authoritative frozen winning N=500 ordered-ladder fingerprint is:

`c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`

The N=500 ladder must be reconstructed from the frozen final baseline geometry
and accepted by the same frozen Stage 7 ladder-verification implementation
before any panel artefact is serialized.

No accession may be sourced from console output, pasted membership, a manually
edited list, or an independently reconstructed list that has not passed that
verification.

## Purpose

The purpose of this stage is to convert the scientifically frozen winning
selector ladder into deterministic, auditable selector-v1 reference panel
artefacts.

This stage establishes:

- the canonical ordered N=500 selector-v1 reference ladder;
- the six initial preset public panels;
- the exact prefix rule for custom N;
- deterministic serialization;
- machine-readable provenance;
- checksums;
- a completion record suitable for a later monthly release workflow.

This stage does not:

- refresh the source universe;
- modify eligibility;
- modify taxonomy;
- recalculate structural features;
- alter selector semantics;
- compare OPS and SR again;
- use the external selector-resolution holdout;
- calculate a new selector score;
- assign a monthly release identifier;
- publish a BacSelect release;
- generate FASTA;
- generate human-facing Excel release metadata.

## Selector and architecture versions

For selector-v1 release serialization, the version identifiers are frozen as:

- selector version: `1.0.0`;
- structural architecture schema version: `1`;
- official panel-artifact schema version:
  `bacselect-selector-v1-official-panels-v1`.

These identifiers describe the now-frozen selector-v1 semantics and the
serialization contract defined by this document.

Any future scientific change to selector semantics requires a new selector
version.

Any future change to the structural-feature architecture requires an explicit
architecture-schema version change.

A serialization-only change that changes the machine-readable panel artefact
schema requires a new panel-artifact schema version.

## Public panel sizes

The frozen preset public panel sizes are:

- 10;
- 20;
- 50;
- 100;
- 200;
- 500.

The panels are nested prefixes of one deterministic ordered ladder.

For preset N:

`panel(N) = winning_ladder[0:N]`

The public interface may also request any integer N satisfying:

`10 <= N <= 500`

A custom N is generated from the same verified ordered ladder and must never
rerun the selector.

No rounding, interpolation, nearest preset, replacement rule, or secondary
selection is permitted.

## Source ladder reconstruction

The implementation must reproduce the exact frozen Stage 7 reconstruction
path.

It must:

1. verify the pushed selector-decision record;
2. require the decision to be exactly `OPS`;
3. load the frozen final geometry helper;
4. load the final baseline with
   `load_final_foundation(recompute_coordinates=True)`;
5. reconstruct OPS and SR using the frozen Stage 7 ladder builder;
6. pass both reconstructed ladders through the frozen Stage 7
   `_verify_ladders` implementation;
7. require the OPS N=500 fingerprint to equal
   `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
8. only then resolve the verified OPS indices to canonical baseline GenBank
   accessions.

The implementation must not accept a caller-supplied accession sequence as the
scientific source of panel membership.

## Canonical accession requirements

Every serialized panel member must be a canonical GenBank assembly accession
matching:

`^GCA_[0-9]+\.[0-9]+$`

The N=500 ladder must contain exactly 500 accessions.

Those 500 accessions must be unique.

Rank is one-based and must run exactly from 1 through 500.

The order is scientifically meaningful and must be retained exactly.

## Execution boundary

The implementation and its tests must be committed and pushed before real
official-panel generation.

Production generation must require:

- an explicit expected Git execution commit;
- `HEAD` exactly equal to that commit;
- local `origin/main` exactly equal to that commit;
- a clean working tree;
- exact implementation SHA256;
- exact implementation-test SHA256;
- the authoritative selector-decision record SHA256;
- the frozen Stage 7 wrapper identity;
- the frozen Stage 7 execution-adapter identity;
- all baseline and final-geometry identities already enforced by the frozen
  Stage 7 reconstruction path.

No network lookup is required for this stage.

No `git ls-remote` requirement is introduced.

## Production output location

Real generation must occur in fresh scratch storage outside the Git repository.

The production root is:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/official-panel-generation/<execution-commit>`

The output directory must not already exist.

The implementation must fail closed if the target directory or any required
target artefact already exists.

The repository must not be modified by production execution.

Only after deterministic generation and audit may selected official artefacts
be copied into Git by a separate explicit freeze step.

## Text serialization rules

Unless otherwise specified:

- encoding is UTF-8;
- line endings are LF;
- every non-empty text file ends with exactly one final newline;
- TSV uses literal tab separators;
- TSV fields in this schema require no quoting;
- accession order is never sorted after ladder reconstruction;
- JSON uses:
  - `sort_keys=True`;
  - `indent=2`;
  - one final newline;
- files use mode `0644`.

Floating-point values are not part of these official membership artefacts.

## Required artefact 1: verified winning ladder

Filename:

`selector-v1-winning-ladder-n500.tsv`

Exact header:

`rankaccessionfirst_public_panel_n`

There are exactly 500 data rows.

`rank` is the one-based OPS ladder position.

`accession` is the canonical GCA accession at that position.

`first_public_panel_n` is the smallest value in:

`10,20,50,100,200,500`

that is greater than or equal to `rank`.

Therefore:

- ranks 1-10 have `first_public_panel_n=10`;
- ranks 11-20 have `first_public_panel_n=20`;
- ranks 21-50 have `first_public_panel_n=50`;
- ranks 51-100 have `first_public_panel_n=100`;
- ranks 101-200 have `first_public_panel_n=200`;
- ranks 201-500 have `first_public_panel_n=500`.

This file contains panel membership only.

Species names, species TaxIDs, raw features, coordinates, distances, holdout
identities and selector-resolution products are not included.

## Required artefacts 2-7: preset accession lists

The six exact filenames are:

- `panel-n10.txt`;
- `panel-n20.txt`;
- `panel-n50.txt`;
- `panel-n100.txt`;
- `panel-n200.txt`;
- `panel-n500.txt`.

Each file contains exactly one canonical GCA accession per line and no header.

The final newline is mandatory.

For each N, file membership is exactly the first N accessions of
`selector-v1-winning-ladder-n500.tsv`.

The order must match the ladder exactly.

No file may contain duplicate accessions.

## Custom-N serialization

The generator must expose a pure serialization function for custom integer N
from 10 through 500.

For custom N, the byte representation is:

`accession_1 + "\n" + ... + accession_N + "\n"`

where the accessions are the first N entries in the verified OPS ladder.

Custom-N generation must not modify or regenerate the canonical preset
artefacts.

Custom-N output does not become a separately frozen release artefact merely
because a user requests it.

## Required artefact 8: panel membership manifest

Filename:

`panel-membership-manifest.tsv`

Exact header:

`panel_sizemember_countaccession_list_sha256`

There are exactly six data rows, in ascending N order:

`10,20,50,100,200,500`

For every row:

- `panel_size` is N;
- `member_count` is exactly N;
- `accession_list_sha256` is the lowercase SHA256 of the exact bytes of the
  corresponding `panel-nN.txt` file.

The manifest does not duplicate accession identities.

## Required artefact 9: generation summary

Filename:

`panel-generation-summary.json`

Exact top-level keys are:

- `schema_version`;
- `status`;
- `selector`;
- `selector_version`;
- `architecture_schema_version`;
- `winning_ladder_n`;
- `winning_ladder_sha256`;
- `preset_panel_sizes`;
- `custom_n_min`;
- `custom_n_max`;
- `nested_prefix_property`;
- `winning_ladder_accession_count`;
- `selector_decision_record_sha256`;
- `selector_decision_commit`;
- `monthly_release_assigned`.

Required values are:

- `schema_version` =
  `bacselect-selector-v1-official-panels-v1`;
- `status` =
  `OFFICIAL_SELECTOR_V1_REFERENCE_PANELS_GENERATED`;
- `selector` = `OPS`;
- `selector_version` = `1.0.0`;
- `architecture_schema_version` = `1`;
- `winning_ladder_n` = `500`;
- `winning_ladder_sha256` =
  `c81d9fd30cda2d49f0f6c81d4bf99dace9fff811c7612036d9265ef90707fa13`;
- `preset_panel_sizes` = `[10,20,50,100,200,500]`;
- `custom_n_min` = `10`;
- `custom_n_max` = `500`;
- `nested_prefix_property` = `true`;
- `winning_ladder_accession_count` = `500`;
- `selector_decision_record_sha256` =
  `d0cf63ad4d933194e3e782912a2a2a3c617353758d2c87c1b1198681a75869e2`;
- `selector_decision_commit` =
  `d4ba45468baf34b094e7f4bbda8b21a6d8a9de3a`;
- `monthly_release_assigned` = `false`.

No `YYYY.MM` release identifier may appear in this summary.

## Required artefact 10: machine-readable provenance

Filename:

`panel-generation-provenance.json`

Exact top-level keys are:

- `schema_version`;
- `execution_commit`;
- `implementation_sha256`;
- `implementation_test_sha256`;
- `selector_decision_record_sha256`;
- `selector_decision_commit`;
- `winning_selector`;
- `winning_ladder_sha256`;
- `stage7_wrapper_sha256`;
- `stage7_execution_adapter_sha256`;
- `final_geometry_helper_sha256`;
- `baseline_bindings`;
- `environment_lock_sha256`.

`schema_version` is:

`bacselect-selector-v1-official-panel-provenance-v1`

`winning_selector` must be:

`OPS`

`baseline_bindings` must be copied from the already frozen Stage 7 binding
surface, not reconstructed from filenames heuristically.

The provenance record must bind the exact implementation and test identities
used for the production execution.

## Required artefact 11: content manifest

Filename:

`panel-content-manifest.tsv`

Exact header:

`artifactsha256bytesdata_rows`

Rows are lexicographically ordered by `artifact`.

It contains exactly these ten artefacts:

- `panel-generation-provenance.json`;
- `panel-generation-summary.json`;
- `panel-membership-manifest.tsv`;
- `panel-n10.txt`;
- `panel-n20.txt`;
- `panel-n50.txt`;
- `panel-n100.txt`;
- `panel-n200.txt`;
- `panel-n500.txt`;
- `selector-v1-winning-ladder-n500.tsv`.

The content manifest does not include itself.

`sha256` is the lowercase SHA256 of exact file bytes.

`bytes` is the exact file size in bytes.

`data_rows` excludes a TSV header where one exists.

Therefore:

- ladder `data_rows` = 500;
- panel membership manifest `data_rows` = 6;
- each accession list `data_rows` = N;
- each JSON record `data_rows` = 1.

## Deterministic audit requirements

A production execution is complete only if all of the following pass:

1. the pushed selector decision remains OPS;
2. the winning N=500 ladder is reconstructed from the frozen baseline;
3. the same frozen Stage 7 verifier accepts the reconstructed OPS and SR
   ladders;
4. the OPS fingerprint is exactly the frozen winning fingerprint;
5. exactly 500 unique canonical GCA accessions are resolved;
6. rank is exactly 1 through 500;
7. all six preset panels are exact prefixes;
8. all accession-list counts equal N;
9. all accession-list SHA256 values match the membership manifest;
10. every content-manifest SHA256 and byte count is exact;
11. canonical JSON reserialization is byte-identical;
12. a complete rebuild in a second fresh scratch directory produces
    byte-identical copies of all eleven output artefacts.

The rebuild must use the same pushed implementation commit and frozen inputs.

No tolerance-based comparison is permitted.

## Console disclosure

Panel membership is no longer scientifically blinded after the pushed
selector-decision boundary.

Nevertheless, the production generator should default to aggregate console
output.

It should print:

- pass/fail status;
- winning selector;
- N=500 ladder fingerprint;
- artefact paths;
- artefact SHA256 values;
- counts;
- whether production/rebuild bytes are identical.

It should not dump all 500 accessions to scheduler logs unless an explicit
display mode is requested.

## Completion evidence

After production/rebuild byte identity succeeds, create a Git-eligible
aggregate completion record:

`validation/selector-v1/official-selector-v1-panel-completion-evidence.json`

The completion record must not duplicate all 500 accessions.

It must include at least:

- status;
- panel-artifact schema version;
- selector;
- selector version;
- architecture schema version;
- winning ladder fingerprint;
- preset panel sizes;
- production execution commit;
- implementation SHA256;
- implementation-test SHA256;
- production content-manifest SHA256;
- rebuild content-manifest SHA256;
- all-output-byte-identity boolean;
- selector-decision record SHA256;
- selector-decision commit;
- monthly release assigned boolean.

The required status is:

`OFFICIAL_SELECTOR_V1_REFERENCE_PANELS_COMPLETE`

`monthly_release_assigned` must be `false`.

The completion record may be committed only after the deterministic
production/rebuild audit succeeds.

## Relationship to a monthly BacSelect release

Completion of this method freezes the selector-v1 reference panels.

It does not itself create a public monthly release.

A public BacSelect `YYYY.MM` release must separately bind:

- a source snapshot initiated for that calendar month;
- source snapshot metadata and raw provenance;
- complete eligibility and exclusion/review outputs;
- that month's taxonomy snapshot;
- that month's species-resolution outputs;
- that month's structural-feature outputs;
- that month's percentile geometry;
- that month's selector trace;
- that month's complete diversity ladder;
- structural coverage reporting;
- release checksums;
- machine-readable release provenance;
- human-facing TSV metadata;
- human-facing Excel metadata;
- accession downloads.

The release workflow may reuse the selector and deterministic serialization
principles frozen here, but it must not relabel this validation baseline as a
monthly source snapshot.

## Human-facing Excel and TSV metadata

Excel and enriched TSV metadata are intentionally outside this panel-generation
stage.

The repository currently has no frozen workbook dependency or deterministic
Excel serialization implementation.

Those formats must therefore be specified and implemented prospectively as
part of the monthly release-packaging stage.

No workbook is generated by this method.

## FASTA

This stage does not download, bundle, or publish FASTA.

Future FASTA delivery must remain reproducibly tied to canonical GCA
accessions and must not require large immutable sequence archives to be stored
directly in the website repository.

## Fail-closed conditions

Generation must fail without modifying existing outputs if any required
condition changes, including:

- selector decision not OPS;
- selector-decision record hash mismatch;
- Git execution commit mismatch;
- dirty working tree;
- local `origin/main` mismatch;
- frozen Stage 7 implementation identity mismatch;
- final geometry verification failure;
- OPS or SR ladder fingerprint mismatch;
- OPS ladder length other than 500;
- duplicate ladder indices;
- duplicate accessions;
- non-canonical GCA accession;
- non-nested panel prefix;
- invalid N;
- pre-existing output path;
- serializer mismatch;
- checksum mismatch;
- rebuild byte mismatch.

There is no fallback selector or manual repair path inside production
generation.

## Prospective implementation requirements

Before real output generation, the implementation must have synthetic tests
covering at least:

1. exact OPS decision accepted;
2. SR decision refused;
3. `UNRESOLVED` refused;
4. malformed decision refused;
5. decision-record SHA mismatch refused;
6. ladder fingerprint mismatch refused;
7. incorrect OPS ladder length refused;
8. duplicate ladder index refused;
9. out-of-range ladder index refused;
10. duplicate accession refused;
11. malformed GCA accession refused;
12. N below 10 refused;
13. N above 500 refused;
14. non-integer N refused;
15. boolean N refused;
16. exact preset panel prefixes;
17. exact custom-N prefix;
18. exact accession-list final newline;
19. exact ladder TSV header;
20. exact membership-manifest header;
21. exact content-manifest header;
22. canonical JSON summary bytes;
23. canonical JSON provenance bytes;
24. exact preset row order;
25. exact first-public-panel-N boundaries;
26. exact file set;
27. fresh-output requirement;
28. no overwrite;
29. repository dirty-state refusal;
30. wrong HEAD refusal;
31. wrong local `origin/main` refusal;
32. implementation SHA mismatch refusal;
33. implementation-test SHA mismatch refusal;
34. content-manifest SHA mismatch detection;
35. production/rebuild byte mismatch detection;
36. no monthly release identifier in generated reference-panel artefacts;
37. no species, holdout, raw feature, coordinate, distance, or selector-product
    columns in membership artefacts;
38. no production input may be used by implementation unit tests.

Synthetic fixtures must be used during implementation testing.

The real frozen baseline must not be opened by unit tests.

## Prospectivity statement

At the time this method is frozen:

- OPS has already won the prospectively frozen selector-resolution rule;
- the winning OPS N=500 ladder has already been reconstructed and its frozen
  fingerprint verified;
- membership has been legitimately unblinded;
- no official selector-v1 panel artefact has yet been generated;
- no official selector-v1 panel generator exists;
- no monthly public release has been assigned;
- no release workbook has been generated.

This document freezes output semantics before implementation and before real
official-panel artefact generation.
