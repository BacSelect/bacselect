# BacSelect selector-v1 taxonomy snapshot acquisition freeze

The first BacSelect selector-v1 NCBI Taxonomy `new_taxdump` acquisition
completed successfully and was independently re-audited before any candidate
taxonomy resolution.

## Snapshot identity

- taxonomy snapshot ID: `taxonomy-20260826T070308Z`
- BacSelect execution commit: `078da985632603196b0912ebfb5a7a050be8eedd`
- archive SHA256: `005d1b674bb12719c003652c867486f83a5c860b4beb1016adf17f3c56c2d844`
- `nodes.dmp` SHA256: `1d096a81dbd87eccc6d412b28c37ca1eee292fa80e22ae4347c91dcbc7f03153`
- `merged.dmp` SHA256: `3dcd79305dbebc33f50292e7877b7094f99ba920041c7bce199c3b45b4c9e725`
- `delnodes.dmp` SHA256: `9dab07574818ae7696d4a18d5512295e3054fb8260c167a3c894366866f10221`

## Source-snapshot binding

- source snapshot ID: `snapshot-20260825T132821Z`
- raw source report SHA256: `b1b016891ae4e976d03606dfb2f35f74b03d21cf3ec82832f77f4d113bd622d5`
- source acquisition SHA256: `6a1a9b35ee2590b7cd6eac1b087e83254c1acbe9af912475bd9c9c1494ef8741`

## Frozen implementation identities

- taxonomy acquisition method SHA256: `4cdf7347be4e660e8ed8ea94bfe7a0e6c36b06c25f1ff399bd264eaf7c841f88`
- taxonomy acquisition implementation SHA256: `c76f04ab3ab0149d5ede2e1069e547e99588ebba98f6ac1aac0ee5727015cef9`
- taxonomy resolver SHA256: `9c8c4149c5db2a757e8c201a6523bdb113511b5f72a4dd2893572dd8c7928e4d`
- execution wrapper SHA256: `813affdb5049997486a767eaf268a3cc3ddc48d0eaaa5d58a252af4b99a9d61d`

## Acquisition evidence

- acquisition exit status: `0`
- acquisition provenance SHA256: `b2fa02a1c0114c464e3d4a5ef79131766bcd910d4a5dfc8243bb1b94ecc29959`
- content manifest SHA256: `96ca916b1f23f8b0620fc2a951e89155865972d0501d43bcbb1e84f6faeccddf`
- taxonomy snapshot freeze record SHA256:
  `4c89bc24bd06925b24f94b0313cf9ec987adc97b88dd72be19c037db6232b05b`
- execution evidence manifest SHA256:
  `f4667d32114887da0ac9b678120087d901293f4a08d964e004999b6f1aafedfa`

The accepted archive contains 159237632 bytes.

The acquisition stderr SHA256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Audit result

Independent post-acquisition verification passed for:

- source-snapshot binding;
- archive and resolver-input SHA256 identities;
- acquisition provenance identity;
- content-manifest identity;
- frozen snapshot record identity;
- manifest file sizes and SHA256 values;
- taxonomy structural validation.

## Scientific boundary

At this freeze:

- taxonomy resolution performed: `no`;
- candidate TaxIDs read: `no`;
- candidate species generated: `no`;
- complete eligible universe generated: `no`;
- external holdout membership generated: `no`;
- structural features calculated: `no`;
- selector outcomes calculated: `no`.

The taxonomy snapshot is now eligible as a frozen input for a separately
implemented and audited candidate-taxonomy resolution stage.
