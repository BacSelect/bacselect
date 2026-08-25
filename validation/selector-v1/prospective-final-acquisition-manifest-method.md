# BacSelect final acquisition-manifest construction

## Status

**PROSPECTIVE MANIFEST BUILDER — NO NEW BACSELECT GENOME DOWNLOAD YET**

This method freezes how BacSelect converts the already frozen source snapshot,
metadata parser, historical candidate audits, and completed cache-content
verification into the final operational cache-reuse and fresh-download
manifests.

## Scientific boundary

The acquisition partition is not the external-holdout definition.

Baseline membership is deliberately absent from the builder API.

The scientific source universe is reconstructed directly from the frozen raw
NCBI summary snapshot using the frozen BacSelect metadata-eligibility parser.

The operational question is then only whether valid historical sequence
evidence can be reused for each metadata-retained accession.

## Frozen raw source input

Raw JSONL:

`assembly_data_report.raw.jsonl`

SHA256:

`b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`

Expected source records:

`70,850`

The frozen metadata parser is:

`src/bacselect/source_eligibility.py`

SHA256:

`6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2`

Reconstruction must yield exactly:

`70,477` metadata-retained accessions.

## Frozen historical cache evidence

The identity-bearing completed cache-verification TSV has SHA256:

`7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752`

It contains:

- 55,426 unique historical accessions;
- 55,426 cache-content passes;
- zero cache-content fallbacks.

The historical Project Finch snapshot contains 111
`candidate-sequence-audit.tsv` files.

Three historical schema variants exist, but all 111 expose the required reuse
fields:

- canonical GenBank accession.version;
- expected BioSample;
- observed BioSample;
- assembly status;
- current accession;
- assembly level;
- sequence eligibility;
- exclusion reasons.

For each batch, the builder re-hashes the candidate audit and requires an exact
match to `candidate_sequence_audit_sha256` in that batch's frozen
`batch-summary.json`.

## Reuse contract

For a metadata-retained accession present in the historical cache, reuse
requires all of the following:

1. the verified-cache row and historical candidate audit refer to the same
   historical batch;
2. cache content verification is `pass`;
3. accession-scoped package files passed;
4. batch-common provenance passed;
5. canonical accession.version is valid;
6. historical current accession equals that accession.version;
7. historical assembly status is `current`;
8. historical assembly level is `Complete Genome`;
9. fresh BioSample equals historical expected BioSample;
10. fresh BioSample equals historical observed BioSample.

Historical `sequence_eligibility` is not required to equal `eligible`.

A byte-identical historical ineligibility result is valid reusable evidence.
For example, a historical ambiguous-base exclusion should remain an exclusion
rather than trigger unnecessary sequence reacquisition.

Any reuse-contract failure sends the accession to fresh acquisition. It never
causes a scientific exclusion by itself.

## Frozen expected partition

The already prospective cache-overlap audits and completed content verification
imply the following exact partition for this frozen snapshot:

- metadata retained: 70,477;
- verified historical cache reuse: 55,151;
- fresh acquisition: 15,326.

These two acquisition sets must be disjoint and exhaustive over all 70,477
metadata-retained accessions.

Any different count fails closed.

## Fresh acquisition batching

Fresh accession manifests are lexicographically sorted.

Batch size is exactly 500 accessions.

The expected 15,326 fresh accessions therefore produce:

- 31 batches total;
- batches 001–030 with 500 accessions each;
- batch 031 with 326 accessions.

Each batch receives an exact newline-delimited ASCII `accessions.txt` and a
SHA256 recorded in `fresh-batch-index.tsv`.

## Identity-bearing outputs

The builder writes the following internal scratch artifacts:

- `cache-reuse-accessions.txt`;
- `fresh-download-accessions.txt`;
- `cache-reuse-manifest.tsv`;
- `fresh-download-manifest.tsv`;
- `historical-candidate-audits-sha256.tsv`;
- `fresh-batch-index.tsv`;
- `fresh-batches/batch-NNN/accessions.txt`.

These artifacts may contain accession and BioSample identities and are not
public selector-outcome artifacts.

They should remain scratch-only unless a later explicit provenance decision
requires otherwise.

## Blinding-safe output

`acquisition-plan-summary.json` contains counts, fixed input identities, and
whole-artifact SHA256 values only.

After the real manifest construction, the summary and cryptographic identities
can be frozen in Git without committing accession identities.

## Determinism

The builder:

- reconstructs eligibility from the frozen raw source snapshot;
- sorts all accession manifests lexicographically;
- rejects duplicate accessions;
- rejects mismatched historical batch assignments;
- verifies the raw source SHA256;
- verifies the completed cache-verification TSV SHA256;
- re-verifies every historical candidate-audit SHA256;
- requires exact frozen partition counts;
- requires exact fresh batch count and final batch size;
- refuses to overwrite an existing output directory.

## No network boundary

The builder performs no NCBI call, HTTP request, download, or rehydration.

No new sequence data are read or downloaded by this stage.

Historical candidate audit TSVs and the frozen NCBI summary JSONL are metadata
inputs.

## Prospectivity statement

At this method freeze:

- the final identity-bearing cache/fresh manifests have not yet been generated
  by BacSelect;
- no new BacSelect genome sequence has been downloaded;
- no fresh sequence validation has occurred;
- no repeated-BioSample topology-aware fingerprint has been generated for the
  current snapshot;
- no current source-truth screen has been completed;
- no current taxonomy/species resolution has been completed;
- no external-holdout structural features have been calculated;
- no OPS/SR external-holdout outcome has been calculated;
- the selector-resolution decision remains unresolved.
