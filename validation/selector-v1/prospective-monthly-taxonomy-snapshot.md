# BacSelect monthly taxonomy-snapshot contract

**PROSPECTIVE PURE MONTHLY STAGE 7 CONTRACT**

This method freezes the identity and provenance contract for the NCBI Taxonomy
snapshot associated with one BacSelect monthly production release.

It does not acquire taxonomy data and does not perform taxonomy resolution.

## Position

The monthly production order is:

1. source snapshot;
2. metadata eligibility;
3. sequence planning and acquisition;
4. sequence evidence validation;
5. source-truth evaluation;
6. repeated-BioSample reconciliation;
7. chromosome-component integrity;
8. taxonomy-snapshot acquisition;
9. taxonomy resolution.

In the production-release overview this taxonomy reference step is called
monthly Stage 7.

Only after a Stage 7 snapshot has been frozen may taxonomy resolution begin.

## Current monthly source binding

Every Stage 7 taxonomy snapshot is bound to the exact current monthly source
snapshot.

The pure contract binds and structurally validates a Stage 1 record supplied
by the production executor:

- monthly release ID;
- monthly source-snapshot ID;
- Stage 7 origin Git commit;
- exact source-snapshot-record SHA256;
- exact raw source-response SHA256 carried by that authenticated record.

The source-snapshot record must retain the frozen Stage 1 schema, status,
selector identity, selector version, architecture schema version, release
identity and deterministic source-snapshot identity.

A taxonomy snapshot cannot be relabelled as belonging to another monthly
source snapshot.

### Executor-side Stage 1 reauthentication

The pure Stage 7 contract is not the authority that establishes which
source-snapshot-record bytes are canonical production evidence.

Before calling the pure Stage 7 contract, the monthly production executor must
reconstruct and authenticate the canonical Stage 1 evidence chain using the
frozen monthly Stage 1 contracts and the authoritative production artefacts.

In particular, the executor must derive the expected source-snapshot-record
SHA256 from the authenticated canonical Stage 1 artefact. It must not treat an
arbitrary caller-supplied SHA256, configuration value, or self-consistent
replacement source-snapshot record as a production trust anchor.

Only after that upstream reauthentication succeeds may the executor pass the
canonical source-snapshot record bytes and their authenticated SHA256 into
`build_monthly_taxonomy_source_context()`.

The pure function then provides deterministic structural validation and
cryptographic binding of that already-authenticated Stage 1 record to the
monthly taxonomy snapshot.

## Historical acquisition is not monthly production

The historical selector-v1 acquisition implementation:

`src/bacselect/source_taxonomy_acquisition.py`

contains frozen source-snapshot constants from the validation execution.

Its top-level `acquire_taxonomy_snapshot()` therefore must not be called by
monthly production.

Those historical bindings are validation evidence and remain untouched.

A future monthly Stage 7 executor may reuse independently audited low-level
primitives from that module only where those primitives are free of historical
source-snapshot bindings.

Examples include:

- HTTPS response streaming;
- archive validation;
- controlled extraction;
- structural taxonomy validation.

The monthly executor must construct its own current-release provenance.

## Taxonomy source

The upstream taxonomy object is the NCBI Taxonomy `new_taxdump` archive:

`https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz`

The frozen resolver consumes:

- `nodes.dmp`;
- `merged.dmp`;
- `delnodes.dmp`.

The resolver implementation is:

`src/bacselect/source_taxonomy.py`

Frozen SHA256:

`9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d`

A Stage 7 record with any other resolver identity fails closed.

## Monthly taxonomy snapshot identity

A monthly taxonomy snapshot ID is derived from three authorities:

1. the BacSelect monthly release ID;
2. the canonical taxonomy-acquisition start UTC timestamp;
3. the complete taxonomy archive SHA256.

The exact form is:

`bacselect-taxonomy-<YYYY.MM>-<YYYYMMDDTHHMMSSZ>-<archive-sha256>`

Consequently:

- a different monthly release produces a different taxonomy snapshot identity;
- a different acquisition start produces a different identity;
- different taxonomy content produces a different identity.

Identical taxonomy archive bytes in two monthly releases do not make the
snapshots interchangeable because the release identity remains part of the
snapshot identity and provenance record.

## Acquisition evidence

The pure contract accepts evidence produced by a future executor.

Required evidence includes:

- acquisition start UTC;
- acquisition completion UTC;
- requested source URL;
- final HTTPS URL;
- archive SHA256 and size;
- `nodes.dmp` SHA256 and size;
- `merged.dmp` SHA256 and size;
- `delnodes.dmp` SHA256 and size;
- acquisition-provenance SHA256;
- content-manifest SHA256;
- production acquisition-implementation SHA256;
- frozen `source_taxonomy.py` SHA256.

All SHA256 values use lowercase hexadecimal.

All taxonomy content sizes are positive integers.

Acquisition completion cannot precede acquisition start.

The requested URL is the exact frozen NCBI `new_taxdump` URL.

The final response URL must remain HTTPS.

## Pure Stage 7 record

Schema:

`bacselect-monthly-taxonomy-snapshot-v1`

Status:

`MONTHLY_TAXONOMY_SNAPSHOT_FROZEN`

The deterministic record binds:

- release ID;
- source snapshot ID;
- origin Git commit;
- source-snapshot-record SHA256;
- raw source-response SHA256;
- taxonomy snapshot ID;
- acquisition start/completion UTC;
- requested and final taxonomy URLs;
- archive identity;
- three extracted taxonomy-member identities;
- acquisition-provenance SHA256;
- content-manifest SHA256;
- production acquisition-implementation SHA256;
- frozen resolver SHA256.

The serializer uses deterministic sorted JSON.

The record auditor reconstructs the current Stage 1 source context and the
entire Stage 7 build before accepting serialized bytes.

## Downstream state

Stage 7 freezes reference evidence only.

The record must state:

- taxonomy resolution performed: false;
- structural features calculated: false;
- selector outcomes calculated: false.

Any Stage 7 record claiming a downstream result fails closed.

## Scientific separation

Stage 7 does not inspect candidate organism TaxIDs.

Stage 7 does not normalize merged TaxIDs.

Stage 7 does not traverse taxonomy lineages.

Stage 7 does not assign species TaxIDs.

Those operations belong exclusively to monthly taxonomy resolution after the
taxonomy snapshot has been frozen.

## Authoritative storage

The eventual executor must persist the taxonomy reference and its provenance
using the existing monthly authoritative-storage contract.

At minimum, authoritative content will include the accepted taxonomy archive,
the three resolver input files, acquisition provenance, content manifest and
the pure Stage 7 record.

Durable object readback and publication semantics belong to the executor
contract, not this pure scientific/provenance contract.

## Historical isolation

This pure monthly module must contain no:

- hard-coded historical source-snapshot ID;
- hard-coded historical source-snapshot commit;
- historical raw-source SHA256;
- historical acquisition SHA256;
- Project Finch runtime dependency;
- institution-specific filesystem path;
- network call;
- archive extraction;
- taxonomy-resolution result.

Historical selector-v1 taxonomy artifacts remain immutable validation evidence.
