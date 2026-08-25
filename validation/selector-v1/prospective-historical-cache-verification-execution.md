# BacSelect historical cache verification execution

## Status

**PROSPECTIVE EXECUTION DESIGN — REAL CACHE RE-HASH NOT YET LAUNCHED**

This execution layer is frozen after the historical cache verifier and before
the first BacSelect full-content re-hash of the historical Project Finch
sequence snapshot.

## Frozen verifier

Verifier SHA256:

`c0f2114907111ae9f7f89695fefcafa79fe4da3e3ed71acc597c5101db13963d`

Prospective verifier implementation note SHA256:

`f324c9021ddea58b9098f72a91b20b0040343007e9ce259e6c1ae9e2803fad6c`

## Source snapshot

The runner reads, in place:

`/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/ncbi-sequence-validation-snapshot`

The snapshot is never copied by this execution layer.

The observed historical snapshot contains 111 batches.

Observed batch disk footprints range from approximately 3.4 GiB to 12.7 GiB.

## Array topology

The verifier is executed as a Slurm array:

`1-111%4`

Each task maps exactly to one historical `batch-NNN` directory.

The maximum concurrency is four tasks.

The workload is deliberately I/O-conservative. SHA256 calculation is streaming
and single-threaded; aggressive array concurrency would add unnecessary load
to shared storage.

## Array resources

Partition: `prod`

CPU: `1`

Memory: `2G`

Walltime: `04:00:00`

The 2-GiB memory request is intentionally generous relative to the streaming
8-MiB verifier buffer and small tabular metadata.

The four-hour walltime is a fail-safe ceiling, not an expected runtime.

## Aggregation resources

Aggregation uses `prod`, 1 CPU, 2 GiB memory, and a 1-hour walltime.

The aggregation job is submitted with:

`afterok:<array-job-id>`

It runs only after every array task exits successfully.

A cache mismatch recorded as `fallback_to_fresh` is a valid verifier result and
does not cause the array task itself to fail.

A structural execution/provenance error causes the task to fail and prevents
automatic aggregation.

## Environment

The runner resolves the existing Conda executable from `CONDA_EXE` or `PATH`
and executes:

`conda run --no-capture-output -n bacselect-dev`

`PYTHONPATH` is set to the committed BacSelect `src` directory.

The verifier itself uses the Python standard library only.

## Repository binding

Every task and the aggregation job require:

- repository `HEAD` equals the submitted commit;
- local `origin/main` equals the submitted commit;
- the Git working tree is clean;
- the verifier SHA256 equals the frozen verifier identity.

The scientific output root is commit-scoped:

`/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/historical-cache-verification/<git-commit>`

The submission helper refuses to reuse an existing commit-scoped output root.

The repository must remain unchanged while the array and aggregation jobs are
active.

## Logs

Slurm logs are commit-scoped under:

`$HOME/slurm-logs/bacselect/historical-cache-verification/<git-commit>`

Array logs use `%x-%A_%a.out` and `%x-%A_%a.err`.

Aggregation logs use `%x-%j.out` and `%x-%j.err`.

The log directory is created before `sbatch`.

## Batch outputs

Each successful array task writes:

- `package-file-verification.tsv`;
- `accession-cache-verification.tsv`;
- `batch-cache-verification-summary.json`;
- `run-provenance.tsv`;
- `batch-artifacts-sha256.txt`.

The runner refuses to overwrite an existing batch output directory.

## Aggregate outputs

The dependent aggregation job first validates every
`batch-artifacts-sha256.txt`.

It then requires exactly:

- 111 batch result directories;
- 55,426 aggregate accessions;
- 166,844 package-manifest rows.

It writes:

- `historical-cache-content-verification.tsv`;
- `historical-cache-content-verification-summary.json`;
- `run-provenance.tsv`;
- `aggregate-artifacts-sha256.txt`.

## Submission provenance

Before submission, the helper records the submitted Git commit, local
`origin/main`, source snapshot path, scientific output root, log root, resource
and array definitions, wrapper/verifier/method SHA256 identities, and
submission timestamp.

After successful scheduler submission it records the array and dependent
aggregation job IDs.

## Network and storage boundary

The array and aggregation wrappers contain no NCBI, HTTP, download, rehydrate,
`curl`, or `wget` operation.

They do not copy or duplicate historical sequence data.

The only large-data operation is sequential read access required to calculate
SHA256 values over the existing cache.

## Result interpretation

This execution verifies all 55,426 historical cache accessions.

It does not itself define the BacSelect current cache-reuse set.

After aggregation, the cache-verification result will be intersected with the
already frozen 55,151 current metadata-retained cache candidates.

Any current cache candidate with `fallback_to_fresh` is added to the
incremental fresh-download target set.

No assembly is scientifically excluded because cache verification failed.

## Prospectivity statement

At this execution-design freeze:

- the real historical cache has not been fully re-hashed by BacSelect;
- no cache-pass/fallback result has been frozen;
- no incremental fresh-download manifest has been generated;
- no BacSelect genome sequence has been downloaded;
- no source structural-integrity result has been generated for the fresh
  holdout;
- no structural feature has been calculated;
- no OPS/SR external-holdout distance has been calculated;
- the selector-resolution decision remains unresolved.
