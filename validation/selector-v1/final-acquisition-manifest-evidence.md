# Final acquisition-manifest evidence

## Status

**COMPLETE — FINAL CACHE-REUSE AND FRESH-ACQUISITION MANIFESTS BUILT**

This checkpoint freezes the deterministic operational acquisition partition for
the prospective BacSelect selector-resolution source snapshot.

Identity-bearing acquisition manifests remain in scratch and are not committed
to Git.

## Frozen production build

BacSelect commit:

`a8f045506ac4a3f17034cd9170867995a87eb894`

Frozen raw source SHA256:

`b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`

Frozen verified historical-cache accession evidence SHA256:

`7b2fa38ff2c1f43fc0536cabfa68091fdde9d4d3677092d49405bbac113fd752`

## Final acquisition partition

| Field | Result |
| --- | ---: |
| Source records | 70,850 |
| Metadata retained | 70,477 |
| Verified cache reuse | 55,151 |
| Fresh acquisition | 15,326 |
| Fresh batch size | 500 |
| Fresh batches | 31 |
| Final fresh batch size | 326 |

The cache-reuse and fresh-acquisition sets are disjoint and exhaustive over all
70,477 metadata-retained accessions.

All 15,326 fresh acquisitions have acquisition reason
`not_in_historical_cache`. No cache candidate was forced to fresh acquisition
by cache-integrity or fresh-vs-historical metadata reconciliation failure.

## Reused historical sequence evidence

Among the 55,151 reused historical sequence-evidence records:

- 55,145 are historically sequence-eligible;
- 6 are historically sequence-ineligible.

The six ineligible records remain on the cache-reuse path because byte-identical
historical ineligibility is valid reusable evidence. Cache reuse is an evidence
mechanism, not a rule that an assembly must be scientifically eligible.

## Frozen identity-bearing artifact hashes

Cache-reuse accession list SHA256:

`75cfaef4461fd2729eba79067b6aa69a53e570993a9ec4665208b50dab915c51`

Fresh-download accession list SHA256:

`fb6a1ca5bfea391beb761c2c28dd0baa520115ab7a31a31411a73ef121fe5899`

Cache-reuse manifest SHA256:

`32a61975f99b973c3e7a2f58ac98beafe7b63c437c4bf0e3f7f51872680faff1`

Fresh-download manifest SHA256:

`1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b`

Historical candidate-audit hash manifest SHA256:

`e6aad9f3adef78f8ce12228eee7d61d801643dd3cfbf11087f41b76c3bad7d37`

Fresh-batch index SHA256:

`2a52f7ba3b23867bfe85078b47b840e5a1e240b09187d130fb0578087b483c4a`

Acquisition-plan summary SHA256:

`3cd28008a355f487aedf4e2c833f078cab27a3580acb1650777312630eae83f3`

The identity-bearing files remain scratch-only.

## Fresh-batch contract

The 15,326 fresh accessions are lexicographically sorted and partitioned into
31 deterministic batches.

Batches 001–030 contain 500 accessions each.

Batch 031 contains 326 accessions.

The 31 batch manifests exactly reconstruct the complete fresh-download
accession list.

## Scientific and blinding boundaries

Baseline membership was not used to determine acquisition routing.

This checkpoint does not commit accession identities, BioSample identities,
organism names, species names, taxonomy identifiers, structural features,
OPS/SR identity, or selector distances.

The acquisition partition does not define the external holdout. It only records
whether sequence evidence is reused or must be acquired fresh within the frozen
metadata-retained universe.

## Network and sequence boundary

No network access occurred while building these manifests.

No BacSelect genome sequence was downloaded.

The next prospective stage may now freeze the fresh sequence-acquisition and
validation execution against the 31 fresh batches before any download is
launched.

The selector-resolution decision remains unresolved.
