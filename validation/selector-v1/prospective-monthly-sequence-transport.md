# BacSelect monthly sequence transport

## Status

**PROSPECTIVE MONTHLY STAGE 3B TRANSPORT CONTRACT — SYNTHETIC INPUTS ONLY**

This method freezes the deterministic transport contract before any real
monthly sequence download is enabled.

## Boundary

Stage 3B transports the exact Stage 2 fresh-acquisition targets into a complete
local NCBI Datasets package suitable for Stage 3A validation.

Transport and scientific validation remain separate.

Stage 3B may:

- construct the frozen NCBI Datasets download command;
- validate and safely extract the dehydrated ZIP;
- parse `ncbi_dataset/fetch.txt`;
- assess hydration completeness;
- retry incomplete Datasets hydration in a bounded deterministic manner;
- record transport provenance.

Stage 3B does not determine sequence eligibility.

Stage 3A alone validates the hydrated scientific payload.

## Dynamic batch identity

Monthly Stage 3B contains no frozen source-population or batch-count values.

For each batch it binds:

- current Stage 1 source-snapshot identity;
- SHA256 of the complete Stage 2 fresh-target manifest;
- SHA256 of the identity-bearing batch-target manifest;
- SHA256 of the exact accession input bytes;
- complete fresh-target count;
- dynamic batch index and batch count;
- configured batch size;
- first and last accession;
- production Git commit;
- transport implementation SHA256;
- frozen NCBI Datasets environment SHA256;
- exact NCBI Datasets version;
- absolute runtime Datasets executable.

The runtime path is operational provenance. It is not a replacement for the
frozen version and environment identity.

## NCBI Datasets command contract

The frozen dehydrated download arguments are:

`download genome accession --inputfile <accessions> --include
genome,gbff,seq-report --dehydrated --filename <partial.zip>
--no-progressbar`

The broad hydration arguments are:

`rehydrate --directory <package> --max-workers 10 --no-progressbar`

Targeted hydration is accession-specific:

`rehydrate --directory <package> --match <GCA accession.version>
--max-workers 1 --no-progressbar`

At most two targeted retry rounds are permitted for an unresolved accession.

These are transport parameters and do not encode a historical accession count.

## Dehydrated ZIP

Before extraction:

- ZIP structure must be readable;
- CRC verification must pass;
- no archive member may escape the requested extraction root.

The archive is transport evidence and must later be SHA256-addressed by the
execution layer.

## Hydration manifest

`ncbi_dataset/fetch.txt` must:

- exist;
- contain exactly three tab-delimited fields per row;
- contain non-negative integer expected sizes;
- contain safe relative destinations;
- contain unique destinations;
- place payloads below `data/<expected GCA>/...`;
- refer only to expected batch accessions;
- contain at least one entry for every expected batch accession.

## Hydration completeness

For every `fetch.txt` entry the hydrated destination must:

- exist as a file;
- be non-empty;
- match the advertised size whenever the advertised size is greater than zero.

Missing, empty or size-mismatched entries are unresolved transport evidence.

The execution layer may perform the frozen broad rehydrate followed by at most
two deterministic accession-specific retries.

After those retries, any unresolved entry fails the batch closed.

No EFetch or alternative scientific-data recovery is authorized.

## Targeted cleanup

Before an accession-specific retry, only destinations listed by `fetch.txt` for
that accession may be removed.

Unrelated package files must be retained.

## Pre-network provenance

The execution layer must durably write and read back the attempt-origin record
before invoking NCBI Datasets.

The record must contain the current monthly and implementation identities
defined above and initially records `dehydrated_zip_sha256` as null.

The completed ZIP hash is added only after successful download, integrity
checking and atomic promotion from the partial ZIP path.

## Stage 3A handoff

Transport completion is necessary but not sufficient.

A hydrated package is not accepted as scientific evidence until
`validate_hydrated_package()` from the frozen Stage 3A module passes.

Stage 3B must never repair a Stage 3A scientific validation failure.

## Execution boundary

`src/bacselect/monthly_sequence_transport.py` contains deterministic transport
primitives only.

It deliberately does not:

- execute external commands;
- perform network access;
- locate Conda or Micromamba;
- perform EFetch;
- depend on Project Finch;
- depend on institution-specific storage;
- invoke Slurm;
- publish artifacts or releases.

A later execution wrapper will invoke these frozen primitives using an explicit
absolute Datasets executable.

## Prospectivity

At this checkpoint:

- monthly Stage 1 acquisition remains disabled;
- Stage 3B command construction has synthetic coverage only;
- no monthly genome sequence is downloaded;
- no real Stage 2 batch is transported;
- no authoritative persistence backend is yet enabled;
- release publication remains disabled.

## Upstream provenance-record binding

The Stage 3B batch contract also binds the SHA256 identities of:

- the audited Stage 1 `source-snapshot-record.json`; and
- the audited Stage 2 monthly sequence-plan record.

These identities are written into the pre-network attempt record before any
Datasets download or rehydration command may execute.

The complete upstream chain carried into Stage 3B is therefore:

`source-snapshot record SHA256 -> sequence-plan record SHA256 -> fresh-target
manifest SHA256 -> batch-target manifest SHA256 -> accession-input SHA256`.

The execution wrapper must derive these values from audited files. They are not
independent caller assertions.
