# BacSelect monthly taxonomy-snapshot execution

**PROSPECTIVE MONTHLY STAGE 7 EXECUTION CONTRACT**

This document freezes the production execution architecture for acquiring,
validating, storing and publishing the NCBI Taxonomy snapshot associated with
one BacSelect monthly release.

It adds no taxonomy scientific decision rule.

The frozen pure Stage 7 contract remains:

`src/bacselect/monthly_taxonomy_snapshot.py`

Taxonomy resolution remains a later stage.

## Implementation split

Production Stage 7 is implemented through:

`src/bacselect/monthly_taxonomy_snapshot_execution.py`

and:

`validation/selector-v1/run_monthly_taxonomy_snapshot.py`

The execution-support module owns reusable operational logic, taxonomy
acquisition/provenance construction and authoritative-storage handling. It
receives an already-authenticated immutable upstream context and must not import
or dynamically load modules from `validation/`.

The validation wrapper owns repository binding, CLI parsing, explicit
real-execution authorization, frozen validation-wrapper loading, Stage 1 through
Stage 6 reconstruction/authentication and release-directory orchestration.

This preserves the repository dependency direction: validation executors may
import production modules from `src/bacselect`, while production modules do not
depend on validation wrappers.

Focused tests are:

`tests/test_monthly_taxonomy_snapshot_execution.py`

and:

`tests/test_run_monthly_taxonomy_snapshot.py`

No historical taxonomy execution wrapper is modified.

## Stage identity

The canonical local stage name is:

`taxonomy-snapshot`

The acquisition workspace is:

`taxonomy-snapshot.partial`

The canonical Stage 7 record is:

`monthly-taxonomy-snapshot-record.json`

The completion receipt is:

`taxonomy-snapshot-completion.json`

Its temporary publication path is:

`.taxonomy-snapshot-completion.json.tmp`

The completion schema is:

`bacselect-monthly-taxonomy-snapshot-completion-v1`

The terminal completion status is:

`TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE`

The completion receipt is the terminal local authority that Stage 7 execution
finished successfully.

A canonical `taxonomy-snapshot` directory without a valid completion receipt is
incomplete evidence and must not authorize Stage 8.

## Explicit real-execution authorization

The production CLI requires:

`--authorize-real-execution`

Without that flag, no network request, partial stage, authoritative object,
canonical stage or completion artefact may be created.

Tests inject synthetic network responses and local temporary storage.

## No caller-supplied production identities

The real CLI must not accept caller-supplied values for:

- release ID;
- source-snapshot ID;
- source-snapshot-record SHA256;
- raw source-response SHA256;
- Stage 6 completion SHA256;
- taxonomy snapshot ID;
- taxonomy archive SHA256.

Those identities are derived from authenticated production evidence.

The execution commit is bound to the repository state used for execution.

## Stage 6 prerequisite

Stage 7 starts only after the current monthly Stage 6 chromosome-integrity
execution has completed.

The Stage 7 validation wrapper must load the frozen Stage 6 executor by its
frozen implementation identity and use the frozen Stage 6 reconstruction path.

It must not trust the existence of:

`chromosome-integrity-completion.json`

by itself.

The validation wrapper must reconstruct and authenticate the upstream chain
used by Stage 6, including the Stage 5 context and the frozen upstream
contracts, then authenticate the canonical Stage 6 decisions, record and
completion receipt.

After successful reconstruction, the wrapper constructs an immutable Stage 7
upstream context for the execution-support module. That context binds the
authenticated:

- release ID;
- source-snapshot ID;
- canonical source-snapshot-record bytes and SHA256;
- canonical raw source-response bytes and SHA256;
- chromosome-integrity decisions SHA256;
- chromosome-integrity record SHA256;
- chromosome-integrity completion SHA256;
- execution Git commit.

The execution-support module must not accept a replacement upstream identity
from configuration or independently load a validation wrapper.

For long-running acquisition and publication, the wrapper also supplies an
upstream-stability callback. The execution-support module invokes that callback
at the frozen stability checkpoints without importing validation code.

The Stage 6 completion must have schema:

`bacselect-monthly-chromosome-integrity-completion-v1`

and status:

`CHROMOSOME_INTEGRITY_EXECUTION_COMPLETE`

The Stage 6 decision, record and completion SHA256 identities are frozen into
the Stage 7 completion receipt.

Stage 7 does not require every Stage 6 candidate to have PASS status. An
authentic completed Stage 6 execution is the prerequisite. Candidate-specific
withholding remains governed by the frozen downstream scientific contracts.

## Canonical Stage 1 reauthentication

The reconstructed upstream context supplies the authoritative current monthly:

- release ID;
- source-snapshot ID;
- source-snapshot-record SHA256.

The validation wrapper reads the canonical Stage 1:

`source-snapshot-record.json`

and:

`assembly_data_report.raw.jsonl`

from the current release root as part of constructing the authenticated
upstream context.

The source-snapshot-record bytes must hash exactly to the SHA256 obtained from
the reconstructed upstream production chain.

The raw response bytes must hash exactly to the `raw_response_sha256` bound by
that authenticated source-snapshot record.

Only those authenticated bytes may be passed to:

`build_monthly_taxonomy_source_context()`

The executor must never manufacture an expected source-snapshot-record SHA256
from whatever bytes happen to be present locally.

## Upstream stability

Because taxonomy acquisition and durable storage can take substantially longer
than pure record construction, upstream evidence is checked more than once.

At minimum, Stage 7 must reauthenticate the current Stage 1 and Stage 6
authorities:

1. before the real taxonomy request;
2. after acquisition and authoritative-storage read-back, before canonical
   stage publication;
3. immediately before completion publication.

Any change in the authenticated upstream signatures fails closed.

## Taxonomy source

The exact requested URL is the frozen Stage 7 source:

`https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz`

The request must use HTTPS.

The final response URL must remain HTTPS.

A positive finite network timeout is required.

The production implementation may use Python `urllib.request`.

The response is always closed after use.

## Reusable historical low-level primitives

The historical top-level function:

`acquire_taxonomy_snapshot()`

must never be called by monthly production.

The following independently audited low-level functions from
`src/bacselect/source_taxonomy_acquisition.py` may be reused:

- `validate_resolver_identity()`;
- `validate_archive()`;
- `extract_required_members()`;
- `structural_validate()`;
- `stream_http_response()`;
- `write_content_manifest()`.

Those primitives contain no historical monthly source-snapshot binding.

Their scientific/structural behaviour is reused unchanged.

## Frozen taxonomy resolver

Before network acquisition, the executor validates the exact frozen resolver:

`src/bacselect/source_taxonomy.py`

SHA256:

`9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d`

The resolver is used only for structural validation during Stage 7.

No candidate TaxID is supplied to it.

No taxonomy resolution result is produced.

## Partial acquisition

The executor creates exactly one fresh:

`taxonomy-snapshot.partial`

directory.

It refuses to begin if any of the following already exists:

- `taxonomy-snapshot`;
- `taxonomy-snapshot.partial`;
- `taxonomy-snapshot-completion.json`;
- `.taxonomy-snapshot-completion.json.tmp`.

Inside the partial stage, the HTTP response is streamed first to:

`new_taxdump.tar.gz.partial`

The partial archive is created no-clobber.

An empty body, unsuccessful HTTP status, non-HTTPS final URL, malformed gzip,
malformed tar, unsafe archive member, missing required member, duplicate
required member or non-regular required member fails closed.

After download, the exact streamed SHA256 and size must equal a fresh
filesystem read-back identity.

The accepted archive is:

`new_taxdump.tar.gz`

Promotion from the `.partial` archive must not overwrite an existing path.

The accepted archive identity is checked again after promotion and after
extraction.

## Controlled extraction

Only these required resolver inputs are extracted:

- `nodes.dmp`;
- `merged.dmp`;
- `delnodes.dmp`.

Extraction uses the frozen controlled-extraction rules and refuses overwrite.

Unexpected archive members may remain unextracted when otherwise safe under the
frozen archive-validation contract.

The accepted resolver inputs undergo frozen structural validation before the
snapshot can be frozen.

## Monthly acquisition provenance

The monthly production executor writes:

`taxonomy-acquisition.json`

This is new monthly provenance and must not reuse the historical selector-v1
acquisition provenance object.

Its schema is:

`bacselect-monthly-taxonomy-acquisition-v1`

Its terminal status is:

`TAXONOMY_ACQUISITION_COMPLETE`

The record binds exactly these semantic fields:

- schema version;
- terminal status;
- release ID;
- source-snapshot ID;
- source-snapshot-record SHA256;
- raw source-response SHA256;
- Stage 6 completion SHA256;
- execution Git commit;
- production execution-support module SHA256;
- production validation-wrapper SHA256;
- execution-method SHA256;
- frozen `source_taxonomy.py` SHA256;
- requested URL;
- final URL;
- HTTP status;
- ETag when supplied;
- Last-Modified when supplied;
- acquisition start UTC;
- acquisition completion UTC;
- downloader identity;
- Python version;
- OpenSSL version;
- archive member count;
- archive SHA256 and size;
- `nodes.dmp` SHA256 and size;
- `merged.dmp` SHA256 and size;
- `delnodes.dmp` SHA256 and size;
- structural-validation result.

It explicitly records:

- taxonomy resolution performed: false;
- structural features calculated: false;
- selector outcomes calculated: false.

The acquisition-provenance JSON uses a closed schema. No additional field is
permitted without changing its schema version and the corresponding frozen
auditor.

The pure Stage 7 field
`taxonomy_acquisition_implementation_sha256` is the SHA256 of the production
execution-support module. The validation-wrapper SHA256 and execution-method
SHA256 are additionally bound through `taxonomy-acquisition.json`, whose SHA256
is itself bound by the pure Stage 7 record.

No Project Finch identity or historical source-snapshot identity may occur.

## Content manifest

After acquisition provenance is frozen, the executor reuses the audited
deterministic content-manifest writer.

The file is:

`taxonomy-content-sha256.tsv`

It covers exactly:

- `new_taxdump.tar.gz`;
- `nodes.dmp`;
- `merged.dmp`;
- `delnodes.dmp`;
- `taxonomy-acquisition.json`.

The manifest itself is not included recursively in that content manifest.

## Pure Stage 7 record

After acquisition, structural validation and content-manifest construction, the
executor builds the frozen pure Stage 7 record.

The file is:

`monthly-taxonomy-snapshot-record.json`

Its schema is:

`bacselect-monthly-taxonomy-snapshot-v1`

Its status is:

`MONTHLY_TAXONOMY_SNAPSHOT_FROZEN`

The taxonomy snapshot ID is derived by the frozen pure contract from:

- monthly release ID;
- acquisition start UTC;
- archive SHA256.

The executor audits the serialized record against the authenticated Stage 1
source-snapshot record before it can continue.

## Authoritative Stage 7 artefact set

Exactly seven logical Stage 7 artefacts enter the authoritative-storage
manifest:

1. `taxonomy-snapshot/new_taxdump.tar.gz`
2. `taxonomy-snapshot/nodes.dmp`
3. `taxonomy-snapshot/merged.dmp`
4. `taxonomy-snapshot/delnodes.dmp`
5. `taxonomy-snapshot/taxonomy-acquisition.json`
6. `taxonomy-snapshot/taxonomy-content-sha256.tsv`
7. `taxonomy-snapshot/monthly-taxonomy-snapshot-record.json`

The authoritative-storage stage ID is:

`taxonomy-snapshot`

The manifest uses the frozen:

`bacselect-authoritative-storage-manifest-v1`

contract.

Every artefact object is addressed through:

`objects/sha256/<first-two>/<next-two>/<complete-sha256>`

The manifest is stored using the key returned by
`authoritative_manifest_key()`.

## Durable object publication

Authoritative storage publication is no-clobber.

For a missing content-addressed object, Stage 7 writes through an
executor-owned temporary file in the authoritative store, durably flushes it,
verifies its byte identity and publishes it without overwriting an existing
object.

If the content-addressed destination already exists, Stage 7 does not replace
it. It accepts the existing object only after exact regular-file, SHA256 and
size verification.

Unknown, symlinked, non-regular or identity-mismatching objects fail closed.

The same no-clobber principle applies to the authoritative manifest.

## Durable read-back receipt

After all seven artefact objects and the authoritative manifest have been
published, Stage 7 calls:

`expected_stored_objects()`

and performs fresh read-back from the authoritative root for every expected
object.

The observed object-key, SHA256 and size tuple must match the frozen storage
contract exactly.

Only then may Stage 7 serialize:

`bacselect-authoritative-storage-receipt-v1`

The authoritative receipt is stored using the key returned by
`authoritative_receipt_key()`.

The stored receipt itself is then read back and its exact bytes, SHA256 and size
are verified.

For Stage 7, seven logical artefacts plus the authoritative manifest produce
exactly eight objects in the authoritative receipt's `verified_objects` set.
The `verified_object_count` must therefore equal exactly `8`.

The receipt is not recursively inserted into the seven-artefact manifest.

## Local canonical stage inventory

After authoritative read-back succeeds, the partial stage receives local
copies of:

`taxonomy-authoritative-storage-manifest.json`

and:

`taxonomy-authoritative-storage-receipt.json`

The canonical `taxonomy-snapshot` stage therefore contains exactly nine files:

- `new_taxdump.tar.gz`;
- `nodes.dmp`;
- `merged.dmp`;
- `delnodes.dmp`;
- `taxonomy-acquisition.json`;
- `taxonomy-content-sha256.tsv`;
- `monthly-taxonomy-snapshot-record.json`;
- `taxonomy-authoritative-storage-manifest.json`;
- `taxonomy-authoritative-storage-receipt.json`.

No other file is allowed in the canonical Stage 7 directory.

## Canonical local publication

Canonical local publication follows the hardened no-clobber publication model
used by later monthly executors.

The canonical stage directory must not pre-exist.

Files are published from the partial stage without overwriting any canonical
path.

Every published file is read back and compared with the validated partial
source.

If publication fails after creating any canonical path, cleanup removes only
paths demonstrably created by the current executor.

For hard-linked files this requires matching device and inode identity.

Unknown or changed paths are never deleted.

Incomplete cleanup is itself a fail-closed execution error.

Only after all nine files are verified may the executor remove its partial
source links/files and the empty partial directory.

## Failure and interruption semantics

Failure before canonical publication never creates:

`taxonomy-snapshot-completion.json`

A retained:

`taxonomy-snapshot.partial`

directory is explicitly incomplete evidence and may be retained for inspection.

It must never be interpreted as a frozen monthly taxonomy snapshot.

A canonical `taxonomy-snapshot` directory without a valid completion receipt is
also incomplete and cannot authorize Stage 8.

Correctly published content-addressed authoritative objects, authoritative
manifests and authoritative receipts are immutable durable evidence. Once they
have been successfully published and verified, a later Stage 7 failure or local
rollback must not delete them.

If local canonical-stage publication or completion publication subsequently
fails, those durable authoritative objects may remain unreferenced by a
terminal local completion receipt. Their presence does not make Stage 7
complete and cannot authorize Stage 8.

Rollback cleanup is therefore restricted to executor-owned local partial,
canonical-publication and temporary-completion paths whose identity can be
demonstrated safely. It never removes already accepted authoritative objects,
manifests or receipts.

The executor never silently resumes or reuses an existing partial or canonical
stage.

## Completion receipt

The deterministic Stage 7 completion receipt binds exactly these semantic
fields:

- schema version;
- terminal status;
- release ID;
- source-snapshot ID;
- execution Git commit;
- production execution-support module SHA256;
- production validation-wrapper SHA256;
- execution-method SHA256;
- source-snapshot-record SHA256;
- raw source-response SHA256;
- chromosome-integrity decisions SHA256;
- chromosome-integrity record SHA256;
- chromosome-integrity completion SHA256;
- taxonomy snapshot ID;
- monthly taxonomy-snapshot record SHA256;
- taxonomy archive SHA256;
- `nodes.dmp` SHA256;
- `merged.dmp` SHA256;
- `delnodes.dmp` SHA256;
- taxonomy acquisition-provenance SHA256;
- taxonomy content-manifest SHA256;
- authoritative-storage manifest SHA256;
- authoritative-storage manifest key;
- authoritative-storage receipt SHA256;
- authoritative-storage receipt key;
- authoritative verified-object count, which must equal exactly `8`.

The completion JSON uses a closed schema. No additional field is permitted
without changing `bacselect-monthly-taxonomy-snapshot-completion-v1` and the
corresponding frozen auditor.

The receipt is deterministic canonical JSON.

It is reconstructed and audited before publication.

## Completion publication

Completion is published last.

The executor writes:

`.taxonomy-snapshot-completion.json.tmp`

using no-clobber creation.

It reads back and audits the temporary bytes.

It reauthenticates the current Stage 1 and Stage 6 authorities.

Only then is the canonical:

`taxonomy-snapshot-completion.json`

published without overwrite.

The canonical completion bytes are read back and audited again.

Stage 1 and Stage 6 stability are checked again.

On failure, cleanup removes only a completion path demonstrably created from
the executor-owned temporary file.

Unknown or changed completion paths are preserved and the execution fails
closed.

## Stage 8 boundary

Stage 7 does not:

- inspect candidate organism TaxIDs for decision-making;
- normalize merged TaxIDs for candidates;
- traverse candidate lineages;
- choose species ancestors;
- assign canonical species TaxIDs;
- calculate structural features;
- calculate selector outcomes.

Stage 8 may begin only from an authenticated Stage 7 canonical stage and
completion receipt.

Stage 8 must independently verify the Stage 7 record, authoritative-storage
receipt and required resolver-input identities before taxonomy resolution.

## Portability

Production Stage 7 must contain no:

- PHF-specific filesystem path;
- `/NGS/` path;
- Slurm requirement;
- Project Finch runtime dependency;
- historical validation snapshot identity;
- historical source-snapshot commit;
- historical source-snapshot SHA256.

All production roots are supplied through portable execution interfaces.

## Freeze discipline

The historical taxonomy acquisition implementation and historical taxonomy
resolution execution remain immutable validation evidence.

The monthly pure Stage 7 contract remains the provenance/scientific authority.

The monthly execution-support module adds operational mechanics only.

The monthly wrapper adds orchestration only.

Neither may introduce a new taxonomy scientific rule.
