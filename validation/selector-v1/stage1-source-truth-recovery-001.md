# Stage 1 source-truth recovery 001

## Status

Prospective technical recovery clarification.

This clarification was written after the first real Stage 1 source-truth
execution failed closed, and before any recovery implementation or recovery
execution.

It does not change the frozen source-truth scientific semantics, Stage 1
population, eligibility rules, blinding rules, or downstream selector
procedure.

## Failed production attempt

The first real Stage 1 execution used BacSelect commit:

`25e44f29072d951172784364e0b16c291ecb2331`

The execution failed closed with:

`candidate FASTA absent from package manifest`

The failed execution did not produce a completed Stage 1 execution directory.

Its preserved partial directory contains only:

- `stage1-input-evidence-manifest.tsv`;
- `stage1-preclassification-provenance.json`.

The preserved partial artifact identities are:

- input-evidence manifest SHA256:
  `d8b00c3ffcda2ff39832a7b3b8d6a18325d8289452d94f6eb7f3e436b6943a54`;
- preclassification provenance SHA256:
  `70b4590cc664e6a0d79087fb33afab5c2cffecb7b499589b44e4184393ed6ec5`.

The execution log SHA256 is:

`22379e0e43111cb1e874ab1d574ce03a59ca0f11f9ea875eba7d7e7b48268882`

No candidate decision table, relation table, completed execution provenance,
aggregate Stage 1 summary, or final content manifest was generated.

No Stage 2 repeated-BioSample result, chromosome-integrity result, taxonomy
resolution, complete eligible universe, holdout membership, structural
features, or selector outcome was generated.

## Frozen preclassification population

Before source-truth evaluation began, the failed attempt successfully froze the
intended Stage 1 population.

Historical:

- count: `55145`;
- membership SHA256:
  `ed659ac6f9cba972a819ea3fb291d738ddeaf55842feb787a7c8ebbcf467952c`.

Fresh:

- count: `13335`;
- membership SHA256:
  `75a8312f090ffef9b2b0c0a41311c02c059a4f353491208c08d3cd64c8256e22`.

Combined:

- count: `68480`;
- membership SHA256:
  `810c584d578bad678e3a9ef3131e13777444961b906a57f5b2cbdcafd691e324`.

These membership identities are fixed recovery checkpoints.

A recovery execution must reproduce all three counts and all three membership
SHA256 values exactly before source-truth evaluation is allowed to proceed.

## Failure diagnosis

A read-only metadata audit was performed after the failed attempt.

The audit inspected candidate-audit and package-manifest path metadata but did
not calculate source-truth outcomes.

For every Stage 1 candidate, the candidate audit stores the genomic FASTA as a
basename, for example conceptually:

`GCA_<redacted>_ASM<redacted>_genomic.fna`

The corresponding frozen package manifest stores the same file using its
package-relative path, conceptually:

`ncbi_dataset/data/GCA_<redacted>/GCA_<redacted>_ASM<redacted>_genomic.fna`

The frozen Stage 1 implementation attempted a literal package-manifest lookup
using the candidate-audit basename. Therefore the lookup failed before the
existing filesystem resolver could be used.

This representation mismatch was universal across the complete Stage 1
population.

### Historical

- candidates: `55145`;
- candidate value was a basename: `55145`;
- zero basename matches: `0`;
- unique basename matches: `55145`;
- multiple basename matches: `0`;
- zero basename-plus-SHA256 matches: `0`;
- unique basename-plus-SHA256 matches: `55145`;
- multiple basename-plus-SHA256 matches: `0`;
- filesystem resolver passes: `55145`;
- filesystem resolver failures: `0`;
- resolved size matches: `55145`;
- resolved size mismatches: `0`.

### Ordinary fresh

- candidates: `12444`;
- candidate value was a basename: `12444`;
- zero basename matches: `0`;
- unique basename matches: `12444`;
- multiple basename matches: `0`;
- zero basename-plus-SHA256 matches: `0`;
- unique basename-plus-SHA256 matches: `12444`;
- multiple basename-plus-SHA256 matches: `0`;
- filesystem resolver passes: `12444`;
- filesystem resolver failures: `0`;
- resolved size matches: `12444`;
- resolved size mismatches: `0`.

### Recovery fresh

- candidates: `891`;
- candidate value was a basename: `891`;
- zero basename matches: `0`;
- unique basename matches: `891`;
- multiple basename matches: `0`;
- zero basename-plus-SHA256 matches: `0`;
- unique basename-plus-SHA256 matches: `891`;
- multiple basename-plus-SHA256 matches: `0`;
- filesystem resolver passes: `891`;
- filesystem resolver failures: `0`;
- resolved size matches: `891`;
- resolved size mismatches: `0`.

### Combined

Across all `68480` Stage 1 candidates:

- candidate value was a basename: `68480`;
- zero basename matches: `0`;
- unique basename matches: `68480`;
- multiple basename matches: `0`;
- zero basename-plus-SHA256 matches: `0`;
- unique basename-plus-SHA256 matches: `68480`;
- multiple basename-plus-SHA256 matches: `0`;
- filesystem resolver passes: `68480`;
- filesystem resolver failures: `0`;
- resolved size matches: `68480`;
- resolved size mismatches: `0`;
- invalid package-manifest sizes: `0`.

The failure is therefore an implementation-level evidence-join defect. It is
not evidence of missing source sequence, changed package content, altered
eligibility, or a source-truth scientific result.

## Permitted recovery correction

The recovery implementation must not alter candidate membership or
source-truth semantics.

For one sequence-eligible candidate, the package-manifest FASTA row must be
resolved using the jointly frozen candidate evidence:

1. take `candidate.fasta_file`, which is the frozen FASTA basename;
2. take `candidate.fasta_sha256`, which is the frozen candidate FASTA SHA256;
3. identify package-manifest rows for which:
   - `Path(row.relative_path).name == candidate.fasta_file`; and
   - `row.sha256 == candidate.fasta_sha256`;
4. require exactly one matching package-manifest row;
5. fail closed if there are zero or multiple matching rows;
6. pass that matched package row's full `relative_path` to the existing
   fail-closed filesystem resolver;
7. retain the existing manifest-size, manifest-SHA256, candidate-SHA256,
   Primary Assembly component-count, component-identity, component-length,
   topology, and component-sequence-SHA256 verification.

No prefix stripping, prefix insertion, fuzzy matching, accession inference, or
other heuristic path normalization is permitted.

The package-manifest row is selected only by the exact basename plus exact
SHA256 evidence already frozen for the candidate.

## Scientific invariants

Recovery 001 must not change:

- the `68480`-candidate Stage 1 population;
- the historical/fresh partition;
- sequence-eligibility decisions;
- Primary Assembly component membership;
- component topology;
- duplicate-relation semantics;
- containment-relation semantics;
- source-truth terminal statuses or their definitions;
- repeated-BioSample logic;
- chromosome-integrity logic;
- taxonomy logic;
- baseline or holdout logic;
- structural features;
- OPS or SR;
- panel membership;
- selector coverage;
- selector outcome;
- identity-blinding requirements.

The failed production attempt must remain preserved and must not be overwritten
or reinterpreted as a completed Stage 1 execution.

A recovery implementation must be independently tested and frozen in Git before
a real recovery execution is attempted.
