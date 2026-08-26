# BacSelect selector-v1 taxonomy snapshot acquisition method

**PROSPECTIVE ACQUISITION METHOD - NO BACSELECT TAXONOMY SNAPSHOT ACQUIRED**

This method fixes the acquisition, validation, provenance and freeze procedure
for the NCBI Taxonomy snapshot used by the BacSelect selector-v1 blinded
post-sequence eligibility workflow.

It is frozen before any BacSelect taxonomy archive is downloaded and before
any candidate TaxID is resolved against that archive.

## Parent checkpoint

Parent BacSelect commit:

`0015b5f25eb5d17488881e38a9022fa8b55433bd`

Frozen BacSelect taxonomy resolver SHA256:

`9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d`

No BacSelect taxonomy snapshot or taxonomy-resolution result has been
generated at this checkpoint.

## Bound BacSelect source snapshot

This taxonomy snapshot is acquired for, and cryptographically bound to, the
already frozen BacSelect fresh source snapshot:

- snapshot ID:
  `snapshot-20260825T132821Z`
- source-snapshot BacSelect commit:
  `c19094a053482b8c2ecfbe0977d22f834e8dd159`
- source-acquisition method SHA256:
  `ea444212eecf9f6f86c478a1d4e71f86bb216ed166aa2449bcc13daddff6351a`
- raw source report SHA256:
  `b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`
- source acquisition record SHA256:
  `6a1a9b35ee2590b7cd6eac1b087e83254c1acbe9af912475bd9c9c1494ef8741`

The phrase "for the same fresh source snapshot" means that this taxonomy
snapshot is the single frozen taxonomy reference used to resolve structured
organism TaxIDs originating from the source snapshot above.

It does not require the taxonomy and genome-source downloads to have identical
wall-clock acquisition times.

No later source snapshot may silently reuse this taxonomy freeze as though it
were part of that later snapshot.

## Upstream taxonomy object

The prospective upstream object is the NCBI Taxonomy `new_taxdump` archive:

`https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/new_taxdump/new_taxdump.tar.gz`

The exact downloaded response body is retained byte-for-byte as:

`new_taxdump.tar.gz`

The BacSelect SHA256 of those downloaded bytes is the authoritative
cryptographic identity of the taxonomy archive.

An upstream checksum, including an MD5 value if supplied by NCBI, may be
retained as auxiliary transport provenance but does not replace the BacSelect
SHA256 identity and is not the scientific freeze key.

## Downloader implementation

A dedicated BacSelect taxonomy acquisition implementation must be written,
tested on synthetic/local fixtures and frozen in Git before the first network
acquisition.

The implementation must:

1. use HTTPS;
2. use the exact prospective URL above as the requested URL;
3. record the final response URL after redirects;
4. require a successful HTTP response;
5. stream response bytes to a temporary `.partial` file;
6. never expose a partial download under the final archive name;
7. calculate SHA256 and byte count over the exact downloaded response body;
8. validate the completed archive before accepting it;
9. rename the temporary archive to `new_taxdump.tar.gz` only after all
   acquisition-level acceptance checks pass;
10. fail closed on any network, HTTP, filesystem, archive or validation error.

The runtime provenance must record at least:

- BacSelect Git commit;
- taxonomy acquisition implementation SHA256;
- prospective acquisition-method SHA256;
- requested URL;
- final URL;
- acquisition start UTC;
- acquisition completion UTC;
- HTTP status;
- downloader/runtime identity;
- Python version;
- SSL/OpenSSL runtime identity where available;
- archive byte count;
- archive SHA256.

HTTP response metadata such as `ETag` or `Last-Modified`, when supplied, may be
recorded as descriptive upstream provenance but is not used as the snapshot
identity.

## Archive validation

The archive is not trusted solely because the network request completed.

Before acceptance, the implementation must verify that:

1. the gzip/tar archive can be read completely without decompression or tar
   parsing failure;
2. archive member names are safe relative paths;
3. no member path is absolute;
4. no member path contains parent traversal;
5. required members occur exactly once;
6. required members are regular files rather than symbolic links, hard links,
   devices, FIFOs or directories.

The required resolver members are exactly:

- `nodes.dmp`
- `merged.dmp`
- `delnodes.dmp`

Unexpected additional files in the official `new_taxdump` archive are
preserved within the original archive and do not by themselves invalidate the
snapshot.

No unrestricted `extractall` operation is permitted.

## Resolver-input extraction

Only the three files consumed by the frozen BacSelect taxonomy resolver are
materialized as resolver inputs:

- `nodes.dmp`
- `merged.dmp`
- `delnodes.dmp`

They are extracted directly from the accepted archive into the taxonomy
snapshot directory using controlled file creation.

For each extracted resolver input, provenance records:

- exact archive member name;
- extracted byte count;
- SHA256.

The three extracted file SHA256 values, together with the archive SHA256, form
the content identity of the accepted BacSelect taxonomy snapshot.

The complete original `new_taxdump.tar.gz` archive is retained even though
only those three extracted files are consumed by `source_taxonomy.py`.

## Structural validation

After controlled extraction, the frozen BacSelect `source_taxonomy.py`
implementation is instantiated against the three extracted files as a
structural validation step.

This validation may verify parser invariants and taxonomy structure, including
the required taxonomy root.

It must not:

- read a BacSelect candidate manifest;
- resolve a BacSelect candidate TaxID;
- calculate species-group counts;
- calculate holdout adequacy;
- calculate structural features;
- inspect selector outcomes.

A malformed or internally inconsistent taxonomy archive fails the acquisition
and is not eligible for freezing.

## Snapshot directory

The accepted taxonomy snapshot is stored outside Git.

The snapshot directory must contain at least:

- `new_taxdump.tar.gz`
- `nodes.dmp`
- `merged.dmp`
- `delnodes.dmp`
- acquisition provenance;
- content SHA256 manifest;
- snapshot freeze record.

Temporary `.partial` files are not accepted snapshot artifacts.

Identity-bearing taxonomy data remain outside the Git repository.

## Content SHA256 manifest

The acquisition implementation writes a deterministic SHA256 manifest covering
at least:

- `new_taxdump.tar.gz`
- `nodes.dmp`
- `merged.dmp`
- `delnodes.dmp`
- acquisition provenance.

The manifest itself is SHA256 hashed.

## Freeze record

After successful acquisition, archive validation, controlled extraction and
structural validation, a taxonomy snapshot freeze record is generated.

The freeze record must contain at least:

- schema version;
- taxonomy snapshot ID;
- snapshot status;
- BacSelect Git commit;
- bound source snapshot ID;
- bound source raw-report SHA256;
- bound source acquisition SHA256;
- taxonomy acquisition-method SHA256;
- taxonomy acquisition implementation SHA256;
- `source_taxonomy.py` SHA256;
- requested URL;
- final URL;
- archive byte count;
- archive SHA256;
- `nodes.dmp` SHA256;
- `merged.dmp` SHA256;
- `delnodes.dmp` SHA256;
- acquisition-provenance SHA256;
- content-manifest SHA256;
- structural-validation status;
- taxonomy resolution performed: `no`;
- structural features calculated: `no`;
- selector outcomes calculated: `no`.

The taxonomy snapshot becomes eligible for downstream resolution only after
this freeze record and its cryptographic identities have been audited.

## Git freeze boundary

The taxonomy archive and extracted `.dmp` files remain outside Git.

Before any real candidate TaxID resolution, Git must freeze blinded,
non-identity-bearing evidence sufficient to bind:

- taxonomy snapshot ID;
- source snapshot binding;
- taxonomy acquisition method;
- acquisition implementation;
- archive SHA256;
- resolver-input SHA256 values;
- acquisition provenance SHA256;
- snapshot freeze record SHA256.

## Failure behavior

Any of the following makes the acquisition unusable:

- non-successful HTTP response;
- interrupted or incomplete transfer;
- archive parse failure;
- unsafe archive member;
- duplicated required member;
- missing required member;
- required member that is not a regular file;
- controlled extraction failure;
- SHA256 calculation failure;
- structural taxonomy validation failure;
- provenance inconsistency;
- failure to bind the snapshot to the frozen BacSelect source snapshot.

A failed attempt may be retained separately as operational evidence but must
not be labelled as the frozen BacSelect taxonomy snapshot.

## Blinding and scientific boundary

Taxonomy acquisition and freezing must not read or use:

- candidate accession identities;
- candidate BioSample identities;
- candidate organism TaxIDs;
- candidate species identities;
- complete eligible-universe membership;
- external decision-holdout membership;
- baseline membership;
- OPS outcomes;
- SR outcomes;
- selector distances;
- panel identities;
- panel membership;
- selector coverage;
- structural-feature values.

The taxonomy snapshot is infrastructure/reference evidence only at this stage.

No real BacSelect taxonomy resolution is generated by this acquisition method.
