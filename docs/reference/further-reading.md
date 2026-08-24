# Further reading

These resources provide context for BacSelect. They are not all BacSelect
dependencies, and the methods they describe should not be treated as equivalent
to BacSelect's structural selection framework.

## Public genome assemblies and retrieval

### NCBI Datasets

NCBI's current documentation for retrieving assembled genomes and metadata:

- <https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/genomes/>
- <https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/genomes/download-genome/>

Useful for understanding how public assembly accessions can be queried and
downloaded.

### NCBI genome assembly data model

- <https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/policies-annotation/data-model/>
- <https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/policies-annotation/genome-processing/version-status/>

These pages explain assembly levels, `GCA_` and `GCF_` identities, versioning
and the relationship between assembly records and component sequences.

## Species representatives and genome taxonomy

### Genome Taxonomy Database

- <https://gtdb.ecogenomic.org/faq>
- <https://gtdb.ecogenomic.org/methods>

GTDB is useful comparative context because it defines genome-based species
clusters and representative genomes.

BacSelect is not a replacement for GTDB and does not use GTDB representative
selection as its architecture-diversity objective.

## Sequence-similarity methods

### FastANI

Jain C, Rodriguez-R LM, Phillippy AM, Konstantinidis KT, Aluru S. High
throughput ANI analysis of 90K prokaryotic genomes reveals clear species
boundaries. *Nature Communications*. 2018;9:5114.

<https://doi.org/10.1038/s41467-018-07641-9>

FastANI estimates average nucleotide identity. ANI is a sequence-similarity
measure and is conceptually different from BacSelect structural distance.

### Mash

Ondov BD, Treangen TJ, Melsted P, et al. Mash: fast genome and metagenome
distance estimation using MinHash. *Genome Biology*. 2016;17:132.

<https://doi.org/10.1186/s13059-016-0997-x>

Mash provides fast sequence-set distance estimates from MinHash sketches.
BacSelect does not use Mash distance as its architecture-space metric.

## Farthest-first and k-center context

Gonzalez TF. Clustering to minimize the maximum intercluster distance.
*Theoretical Computer Science*. 1985;38:293-306.

<https://doi.org/10.1016/0304-3975(85)90224-5>

This is classic algorithmic background for farthest-first traversal and
metric k-center approximation.

It is relevant to understanding diversity-seeking selector ideas, but the final
BacSelect selector-v1 species-representation design is not yet frozen.

## Rank correlation

SciPy documentation for Spearman rank-order correlation:

- <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html>

BacSelect uses Spearman correlation as a diagnostic for relationships among
candidate structural features. Correlation analysis is validation evidence, not
the selector itself.
