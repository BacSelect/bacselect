# Prospective monthly sequence-acquisition completion execution

## Status

This document defines the portable filesystem executor for the frozen BacSelect
monthly sequence-acquisition completion contract.

The executor does not perform NCBI retrieval.

The executor does not modify completed Stage 3B batches.

The executor does not construct the cumulative sequence-cache catalogue.

## Purpose

The frozen Stage 2 record defines the exact fresh-acquisition population and
expected number of Stage 3B transport batches.

The frozen Stage 3B executor materializes one final directory for each completed
batch.

The frozen sequence-acquisition completion contract defines the release-level
completion seal.

This executor connects those frozen layers by independently discovering and
re-hashing the persisted Stage 3B evidence before constructing that seal.

## Repository preflight

Execution requires:

- exact expected Git commit;
- `HEAD` equal to that commit;
- local `origin/main` equal to that commit;
- a clean working tree;
- exact SHA256 identities for the frozen source, Stage 2, Stage 3 and completion
  implementations;
- exact SHA256 identity for the frozen NCBI Datasets explicit environment;
- exact wrapper and wrapper-test identities supplied at execution time.

No remote Git query is required.

## Upstream Stage 1 audit

The executor requires an absolute production root and an absolute Stage 1 root.

The Stage 1 root must equal:

`<production-root>/<release-id>/production/<execution-commit>`

The executor re-audits:

- `release-start-checkpoint.json`;
- `assembly_data_report.raw.jsonl`;
- `source-snapshot-record.json`.

The source snapshot must bind:

- the execution commit;
- NCBI Datasets 18.35.0;
- the frozen explicit-environment SHA256.

## Upstream Stage 2 audit

The caller supplies absolute paths to:

- the Stage 2 sequence-plan record;
- the Stage 2 fresh-target manifest.

Both files must reside below the audited Stage 1 production root.

The supplied Stage 2 paths must themselves be regular non-symbolic-link files.
Resolving a symbolic link to an otherwise valid file is not sufficient.

The frozen Stage 2 auditor is called before any sequence-acquisition completion
work.

The audited Stage 2 record determines:

- fresh-acquisition count;
- expected batch count.

## Sequence-acquisition discovery

The canonical Stage 3B root is:

`<stage1-root>/sequence-acquisition/`

Expected final batch names are exactly:

`batch-00001` through `batch-NNNNN`.

The executor independently inventories the Stage 3B root.

It classifies:

- exact final batch directories;
- `.partial` batch entries;
- every other entry as unexpected.

A final batch name represented by a file or symbolic link is not accepted as a
completed batch directory.

The observed final batch set must exactly equal the Stage 2-derived expected
set.

No missing, extra, partial or unexpected sequence-acquisition entry is allowed.

## Zero-fresh release

When Stage 2 contains zero fresh acquisitions:

- expected batch count is zero;
- `sequence-acquisition/` may be lexically absent;
- an existing empty real `sequence-acquisition/` directory is also acceptable;
- a dangling or resolvable symbolic link at `sequence-acquisition/` is not
  treated as absence;
- no synthetic Stage 3B batch is created.

Any entry beneath `sequence-acquisition/` still fails closed.

## Required completed-batch evidence

For every expected final batch, the executor independently requires and
re-hashes:

- `batch-targets.tsv`;
- `accessions.txt`;
- `attempt-origin.json`;
- `dehydrated.zip`;
- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `package-files.tsv`;
- `batch-summary.json`;
- `package/ncbi_dataset/fetch.txt`.

The package directory itself must be a real directory and not a symbolic link.

Critical evidence paths must be regular files and not symbolic links.

## Full package read-back

The executor does not trust `package-files.tsv` to define the current package
inventory.

Instead, it independently walks the complete current `package/` directory.

Every encountered directory must be a real directory.

Every encountered file must be a real regular file.

Symbolic links and non-regular filesystem objects fail closed.

For every package file, the executor records:

- relative POSIX path;
- observed size;
- observed SHA256.

The complete package tree is observed before Stage 3A semantic
revalidation and independently observed again after Stage 3A returns.

The two complete observations must be exactly identical.

The post-validation observed set is supplied to the frozen pure completion
contract.

Therefore:

- a missing package file fails;
- a modified package file fails;
- an additional package file fails;
- a symbolic-link substitution fails;
- a package mutation occurring during Stage 3A revalidation fails.

## `fetch.txt`

The frozen Stage 3B transport contract places the Datasets hydration manifest at:

`package/ncbi_dataset/fetch.txt`

The executor re-hashes that exact file.

The Stage 3B summary already binds its SHA256 and hydration evidence.

Unchanged bytes therefore preserve the previously audited Stage 3B hydration
semantics without rerunning NCBI Datasets or performing network access.

## Stage 3A semantic revalidation

Byte-level re-hashing alone is not sufficient for candidate and component
scientific evidence because a batch summary and its audit TSV could otherwise
be changed together before the release-level completion seal is created.

For every final Stage 3B batch, the executor therefore reruns the frozen Stage
3A `validate_hydrated_package()` function against:

- the current hydrated `package/` directory; and
- the exact batch target slice reconstructed from the already-audited Stage 2
  fresh-target manifest using the frozen Stage 3B target parser.

The executor reuses the exact frozen Stage 3B `_serialize_tsv()` routine to
serialize:

- reconstructed candidate rows;
- reconstructed component rows;
- reconstructed package-file rows.

Those reconstructed bytes must exactly equal the persisted:

- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `package-files.tsv`.

After Stage 3A returns, all three persisted TSV artifacts are read again and
must exactly equal the bytes read before Stage 3A began.

The completion executor therefore does not define a second TSV evidence
representation and does not permit the persisted Stage 3A evidence to change
during semantic revalidation.

A candidate/component audit and `batch-summary.json` cannot be changed together
and still pass completion unless the changed audit bytes are exactly reproduced
by the frozen Stage 3A scientific validator.

## Completion construction

The executor constructs `CompletedTransportBatchEvidence` only after both
filesystem read-back and Stage 3A semantic revalidation succeed.

It then calls the frozen pure sequence-acquisition completion contract.

The executor cannot supply an unverified boolean in place of package evidence.

## Atomic completion publication

The canonical completion artifact is:

`<stage1-root>/sequence-acquisition-completion.json`

The executor refuses to overwrite any lexically existing completion path,
including a dangling or resolvable symbolic link.

It also refuses to proceed when any lexical entry exists at its temporary
completion path, including a dangling or resolvable symbolic link.

The executor:

1. serializes the frozen completion record;
2. writes it to a mode-0644 temporary file;
3. fsyncs the temporary file;
4. reads the temporary file back;
5. audits the exact temporary bytes using the frozen pure contract;
6. atomically hard-links the already-audited temporary inode to the canonical
   completion name using no-clobber filesystem semantics;
7. fails if the canonical path appeared after the earlier preflight;
8. fsyncs the Stage 1 directory;
9. reads and re-audits the canonical artifact;
10. removes the temporary name only after canonical verification succeeds;
11. fsyncs the Stage 1 directory again.

The canonical completion path therefore appears only after the generated bytes
have already passed temporary-file read-back audit.

Publication cannot overwrite a canonical path created concurrently between
preflight and publication.

## Failure state

Existing completed Stage 3B batch directories are never modified.

A failed completion execution does not create a canonical completion seal.

If failure occurs after the temporary completion artifact is created but before
canonical publication, that temporary file remains for inspection and blocks
automatic overwrite.

If no-clobber canonical publication succeeds but canonical read-back or audit
then fails, the canonical link created by that execution is removed and the
audited temporary inode is retained for inspection.

## Cumulative cache boundary

`sequence-acquisition-completion.json` proves only that the current release's
fresh Stage 3B acquisition population is complete and unchanged.

It is not the cumulative BacSelect sequence-cache catalogue.

The cumulative catalogue remains a later production boundary.

## Production wiring

This executor does not modify the monthly GitHub Actions workflow.

It does not enable:

- NCBI source acquisition;
- Stage 3B transport;
- cache reuse;
- cumulative-cache generation;
- Zenodo publication;
- website publication.
