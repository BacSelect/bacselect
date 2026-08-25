# Historical cache content-verification evidence

## Status

**COMPLETE — HISTORICAL CACHE CONTENT VERIFIED**

This checkpoint freezes the outcome of the prospective historical Project Finch
cache content-verification run used by BacSelect.

No identity-bearing accession table is committed in this checkpoint.

## Frozen production execution

BacSelect commit:

`e6ab34e64cdb949813e533550e19dababd1d80ab`

Slurm array job:

`2504392`

Dependent aggregation job:

`2504393`

Aggregation finished:

`2026-08-25T15:34:16Z`

## Verification result

The complete historical cache contract passed:

| Field | Result |
| --- | ---: |
| Historical batches | 111 |
| Historical accessions | 55,426 |
| Package-manifest rows | 166,844 |
| Cache content pass | 55,426 |
| Fallback to fresh | 0 |

All 111 batch artifact manifests verified and no non-empty Slurm error log was
observed in the completed run.

## Frozen aggregate artifact identities

Identity-bearing aggregate accession table:

`historical-cache-content-verification.tsv`

SHA256:

`7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752`

This table is retained in scratch and is **not committed to Git**.

Blinding-safe aggregate summary SHA256:

`278b3b453e7f243bc1eb902a7bda54bc206700bc81b94b8715c4ef75cd088a56`

Aggregate run provenance SHA256:

`dba2f9f6f8e7872d6614cb76062639a595fb652412ff9ecf543bfe83dfecd518`

Aggregate artifact-manifest SHA256:

`5a486271340f9521e111f45cb6a664158c64a0c12affc8eb37e1453bcc643bae`

## Frozen submission provenance

Submission definition SHA256:

`227c2acd98bc71ceffa77073394e570b9f8d3397e0f71097c829f9dd0471ea9f`

Submission job-ID table SHA256:

`7c306e364f815751bf076708614801ba51ed661e46e844ad660f36ec94207a98`

Submission artifact-manifest SHA256:

`a9fb2aee4486c33fee2ea774d252fe02cd7d458d0ab1911dda466af6bdd444ef`

## Interpretation for BacSelect cache reuse

The historical content-integrity test introduces **zero** cache-triggered
fallbacks.

The frozen BacSelect acquisition design identified 55,151 current
metadata-retained assemblies as historical-cache candidates and 15,326 as
uncached.

Because all 55,426 accessions in the historical cache passed the content
verification, no member of the 55,151-candidate subset is forced to fresh
acquisition by a cache-content failure.

Accordingly, the incremental fresh-acquisition count remains provisionally
15,326 before construction and freezing of the final cache-reuse/fresh-download
manifests.

This statement concerns acquisition evidence only. It does not change the
scientific source-eligibility rules.

## Blinding boundary

This checkpoint commits only aggregate counts, provenance, and cryptographic
identities.

It does not commit accession lists, organism/species names, taxonomy
identifiers, OPS/SR identity, selector distances, or structural-feature
outcomes.

The identity-bearing aggregate TSV remains an internal scratch artifact bound
to this checkpoint by SHA256.

## Execution boundary

The completed verification performed no NCBI or other network acquisition,
copied no historical sequence dataset into BacSelect, read the existing Project
Finch cache in place, re-hashed package content against the frozen historical
manifests, and calculated no BacSelect structural features or external-holdout
OPS/SR distances.

## Next prospective step

The next stage is to construct and freeze the deterministic intersection between
the 55,151 current metadata-retained historical-cache candidates, the verified
historical cache evidence, and the 15,326 uncached current assemblies.

That stage will produce the final cache-reuse and incremental fresh-download
manifests before any BacSelect genome sequence is downloaded.

The selector-resolution decision remains unresolved.
