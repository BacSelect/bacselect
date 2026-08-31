# Prospective monthly sequence-cache catalogue execution

## Status

This document defines the portable execution boundary for the frozen BacSelect
monthly sequence-cache catalogue contract.

It does not alter the frozen pure catalogue contract.

It does not implement:

- monthly cache verification;
- Stage 2 production writing;
- cloud-provider object transport;
- Zenodo publication;
- website publication;
- workflow orchestration.

## Purpose

The executor converts already completed and independently sealed Stage 3B
sequence acquisition into the canonical cumulative monthly sequence-cache
catalogue.

Its inputs are:

- the exact current Stage 1 production root;
- the exact Stage 2 sequence-plan record;
- the exact Stage 2 fresh-target manifest;
- the canonical release-level sequence-acquisition completion;
- the exact completed Stage 3B batch evidence;
- the complete previously authoritative catalogue history materialized beneath
  the supplied production root.

Its output is:

`<stage1 root>/sequence-cache-catalogue.json`

## Frozen dependencies

Execution is permitted only when repository preflight proves the expected
identities of:

- the frozen sequence-acquisition completion executor and its tests;
- the frozen sequence-cache catalogue contract, tests and method;
- the frozen authoritative-storage contract and tests;
- this execution method;
- this execution wrapper and its tests.

The frozen completion executor remains responsible for pinning and auditing the
earlier Stage 1, Stage 2, Stage 3A and Stage 3B dependencies.

## Explicit authorization

The command-line entry point requires:

`--authorize-real-execution`

Absence of explicit authorization fails closed before production execution.

## Repository preflight

Before execution the wrapper requires:

- `HEAD` equals the explicitly supplied execution commit;
- local `origin/main` equals that commit;
- the working tree is clean;
- every frozen dependency has its expected SHA256;
- the wrapper itself has its explicitly supplied SHA256;
- the wrapper test has its explicitly supplied SHA256.

No remote Git query is required.

## Current completion re-audit

The catalogue executor does not trust the mere presence of:

`sequence-acquisition-completion.json`

It reuses the frozen completion executor's already tested read-only primitives
to reconstruct the completion authority.

This includes:

- exact Stage 1 source-snapshot audit;
- exact Stage 2 sequence-plan audit;
- exact fresh-target reconstruction;
- exact expected Stage 3B batch set;
- rejection of partial or unexpected Stage 3B entries;
- independent batch evidence collection;
- Stage 3A hydrated-package semantic revalidation;
- package filesystem read-back;
- exact frozen Stage 3B TSV reconstruction;
- release-level completion contract audit.

The completion artifact is read before and after this reconstruction and must
remain byte-identical.

## Catalogue batch evidence

After the completion has passed the full frozen audit, the executor loads the
exact bytes required by the catalogue contract from each completed batch:

- `batch-summary.json`;
- `candidate-sequence-audit.tsv`;
- `component-sequence-audit.tsv`;
- `package-files.tsv`.

Each path must be a real regular non-symlink file.

Each payload SHA256 must match the corresponding value in the independently
audited sequence-acquisition completion.

The executor therefore does not manufacture new Stage 3B evidence for the
catalogue.

## Catalogue history namespace

Previous catalogue discovery is restricted to the supplied production root.

The canonical history location is:

`<production root>/<YYYY.MM>/production/<40-character Git commit>/sequence-cache-catalogue.json`

Only canonical catalogue paths under valid release and commit directories are
eligible history entries.

A catalogue file, release directory, production directory or commit directory
that occupies a canonical history position through a symbolic link fails
closed.

## Complete history requirement

The production root supplied to this executor must contain the complete
materialized canonical catalogue history required to prove the chain.

A runner may restore those small catalogue files from durable storage before
execution.

The catalogue executor itself does not perform network retrieval.

A partially materialized history is not accepted merely because a recent
catalogue is available.

## Genesis proof

Genesis is permitted only when discovery finds no earlier canonical catalogue
anywhere in the materialized production-root history.

The first discovered catalogue in any non-empty history must itself have:

`catalogue_mode = GENESIS`

A first discovered `CHAINED` catalogue means predecessor evidence is missing and
fails closed.

Thus `None` is passed to the frozen pure catalogue builder only after an actual
history scan proves the materialized canonical history is empty.

## Chain proof

Every discovered prior catalogue must pass the frozen standalone catalogue
audit.

Its embedded:

- release ID must equal its release-directory name;
- origin Git commit must equal its production commit-directory name.

There may be at most one canonical catalogue for a release.

After sorting successful catalogue releases chronologically, every catalogue
after genesis must have:

- `catalogue_mode = CHAINED`;
- `previous_catalogue_release_id` equal to the immediately preceding successful
  catalogue release;
- `previous_catalogue_sha256` equal to SHA256 of the exact preceding catalogue
  bytes.

A failed or absent monthly production release need not exist in the chain.

A missing successful predecessor, fork, conflicting same-release catalogue or
broken SHA link fails closed.

## Chronological append-only rule

Before current publication there must be no canonical catalogue for:

- the current release;
- any later release.

This prevents retrospective insertion into an already advanced authoritative
catalogue chain.

## Current predecessor

For a non-empty valid history, the latest successfully chained catalogue is the
only predecessor supplied to the frozen pure catalogue builder.

The executor never selects a predecessor solely by filename or modification
time.

## Current catalogue construction

The executor invokes the frozen pure catalogue serializer with:

- current release ID;
- current source-snapshot ID;
- current origin Git commit;
- exact audited sequence-acquisition completion bytes;
- exact completion-bound current batch evidence;
- either no predecessor after proven genesis absence or the exact latest
  predecessor catalogue bytes.

The resulting canonical bytes must pass the frozen standalone catalogue audit
before any publication attempt.

## Publication path

The canonical output is:

`sequence-cache-catalogue.json`

The temporary path is:

`.sequence-cache-catalogue.json.tmp`

Both are directly under the audited current Stage 1 production root.

Lexical existence checks use `os.path.lexists()` so dangling symbolic links also
block execution.

## No-clobber publication

The temporary artifact is created using exclusive creation.

The executor:

1. creates the temporary inode with mode `0644`;
2. writes all catalogue bytes;
3. fsyncs the file;
4. reads back the temporary bytes;
5. confirms exact equality;
6. re-audits the frozen catalogue contract;
7. fsyncs the containing directory;
8. re-discovers the prior catalogue chain and confirms it has not changed;
9. creates the canonical path using a hard link with no overwrite;
10. fsyncs the directory;
11. reads back and re-audits the canonical bytes;
12. re-discovers catalogue history and proves the newly published current
    catalogue is exactly the next chain member;
13. removes the temporary link;
14. fsyncs the directory.

`os.replace()` is not used.

## Concurrent history change

History is checked immediately before publication and again after canonical
publication.

If history changed before publication, publication is refused.

If post-publication history verification fails, the executor removes only the
canonical hard link that it created and retains the already audited temporary
inode.

This mirrors the fail-closed publication pattern already frozen for the
sequence-acquisition completion executor.

## Current-release conflict

If another canonical catalogue for the same release exists under another
production commit, execution fails.

If such a competing catalogue appears during publication, post-publication
chain verification fails and the executor removes its own canonical link.

Single-writer workflow orchestration remains desirable, but correctness does
not depend solely on that assumption.

## Authoritative-storage boundary

The executor pins the frozen authoritative-storage contract because the
catalogue's provider-neutral logical artifact identities must remain compatible
with its SHA-addressed object namespace.

This executor does not claim to have uploaded or durably read back those
objects.

Durable object transport and authoritative storage receipts are a separate
execution boundary.

This avoids treating transient runner storage as authoritative cloud storage.

## Zero-fresh release

A valid zero-fresh sequence-acquisition completion requires no Stage 3B batch
directories.

The catalogue executor still:

- fully re-audits Stage 1 and Stage 2;
- audits the zero-batch completion;
- proves catalogue history;
- carries the previous catalogue forward through the frozen pure contract or
  produces an empty genesis catalogue;
- publishes the current canonical catalogue using the same no-clobber gate.

## Portability

The executor contains no:

- institutional filesystem path;
- PHF infrastructure dependency;
- Slurm command or environment dependency;
- Project Finch dependency;
- historical validation-root dependency;
- direct NCBI request;
- cloud-provider SDK dependency;
- Zenodo publication call.

The only subprocess dependency is local Git repository identity checking.

## Result

Successful execution reports:

- release ID;
- source-snapshot ID;
- catalogue path;
- catalogue SHA256;
- catalogue mode;
- predecessor release ID when present;
- predecessor catalogue SHA256 when present;
- final catalogue entry count;
- current acquisition count.

## Next boundary

Completion of this executor does not yet close the monthly cache loop.

The next implementation after this executor is the portable monthly
cache-verification executor, followed by the Stage 2 production writer.
