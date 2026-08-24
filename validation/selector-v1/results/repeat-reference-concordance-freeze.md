# Selector v1 repeat reference concordance freeze

## Status

**PASS**

This record freezes the full-universe production reference-concordance gate for the
selector v1 repeat-scale validation.

The gate was defined to establish production equivalence at the existing reference
repeat scales, **k = 150** and **k = 400**, before any alternative-k repeat features
are calculated or interpreted.

## Production run

- Slurm production array: `2497409`
- Scientific repository commit:
  `b25037af85f65f080eb00c95e97328983923645e`
- Production output root:
  `/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/reference-concordance/b25037af85f65f080eb00c95e97328983923645e/production`
- Expected batches: **111**
- Expected target genomes: **55,306**
- Reference k values: **150, 400**

The earlier submission `2497281` was aborted before production worker execution and
is not part of this validation evidence.

## Frozen inputs and implementation

| Component | SHA256 |
|---|---|
| Target manifest | `bc4acba1384524f956887d02d2f54aa7e501a2c23e2930b779a4e6520d8fcee1` |
| Corrected reference matrix | `fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656` |
| Repeat engine binary | `e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968` |
| Repeat engine source | `bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925` |
| Repeat environment lock | `aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f` |
| Finch structural-feature driver | `e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50` |
| Finch basic structural features | `30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a` |
| Repeat-concordance module | `6dc25a2d382ebdf0a5c6327b211bb4dae064363727b42864a725b626bb325a51` |
| Batch worker | `4e012d24a04c547f2dd01564d4b01122de887b0858be2de20f457b64b120030b` |

The target manifest contained exactly **55,306** rows and its batch/accession
membership was used directly in the independent final audit. The audit does not
assume that `batch_index` is contiguous or resets within a batch.

## Independent final audit

The final audit completed successfully with:

- manifest rows: **55,306 / 55,306**
- result rows: **55,306 / 55,306**
- batches audited: **111 / 111**
- batches passed: **111**
- batches failed: **0**
- audit errors: **0**
- audit warnings: **0**
- `all_pass`: **true**
- audit exit status: **0**

For every target, the audit independently checked batch membership, accession,
manifest `batch_index`, candidate JSON identity and SHA256, production provenance,
empty mismatch lists, `passed: true`, source record count, and the expected six
k-dependent repeat fields:

- `06_non_unique_canonical_150mer_fraction`
- `07_non_unique_canonical_400mer_fraction`
- `08_maximum_canonical_150mer_multiplicity`
- `09_maximum_canonical_400mer_multiplicity`
- `11_inter_replicon_shared_canonical_150mer_fraction`
- `12_inter_replicon_shared_canonical_400mer_fraction`

## Frozen audit evidence

| Artifact | SHA256 |
|---|---|
| `audit_repeat_concordance.py` | `a1f8fd590a3cb1f3ea67eb252c4e1e628481e3e31aeaa87b390918200de78fb5` |
| `repeat-reference-concordance-audit-summary.json` | `6c2eb648bc8f7df8be19dc6c50d1dca13704b2d0591d993d6a1902ff212c3c1a` |
| `repeat-reference-concordance-batch-audit.tsv` | `1ce8e18b61ae841e1cc870f57b2c66a476db0bb667174aae270cbefe54714514` |
| `repeat-reference-concordance-errors.txt` | `51cfd463b6af8a57b3380487f986abf10f137073e9be453e44a7e9a5b4c0e72b` |

The summary's internal hashes for `batch-audit.tsv` and `errors.txt` match the
frozen copies above.

## Interpretation

This gate establishes that the production repeat implementation reproduces the
frozen reference values across the complete 55,306-genome validation universe at
the two existing reference scales, k = 150 and k = 400.

It does **not** determine which repeat scales should be retained in selector v1,
does not resolve the selector representation decision, and does not establish
concordance for alternative k values. Those remain prospective validation steps.
