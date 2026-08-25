# BacSelect selector-v1 release-final decision audit

## Status

**VALIDATION COMPLETE — SELECTOR DECISION FINAL AS UNRESOLVED**

**RELEASE BLOCKED FOR A SELECTOR-v1 PANEL**

This checkpoint closes the prospectively defined final 300/2400 selector-v1
validation programme under the decision rules that were frozen before the
relevant outcomes were interpreted.

The repository identity immediately before this audit was:

`fc462573b066fa4186ce8a14f8674eacb8e324f6`

Genome and species identities remain blinded.

## Evidence bound by this audit

This audit binds the following already frozen interpretation/decision records:

| Record | SHA256 |
| --- | --- |
| OPS-versus-SR selector decision | `52b088f7ffcbd5fc1f7bf30d03c3f89b72821dca6191681c5177c03e4faa9ca9` |
| leave-one-feature-out interpretation | `ee1da3b3b2b2fc6bece38a6f1dd0043870ef7670d05381ad5f63a8a2c3927498` |
| grouped-ablation interpretation | `1a69fe90c5d522c26484a978be4d6b02b3c40dedac317430e6cedcf11b5e4663` |
| deterministic-rebuild evidence freeze | `4448285ac6dad3ac0f76a4b7efe7ee2a0de93025fb7f83804506cbd1b4b0be75` |
| update-stability interpretation | `fdcd11ef428684b86b83d0c9eb5513aca31e50ae75d1a46240e3655ac696051f` |

The final 12-coordinate 300/2400 structural feature schema remains intact.

## Completion of the prospective validation programme

The final 300/2400 selector-v1 validation programme has completed the
pre-specified geometry-dependent and robustness work required before the
selector decision could be treated as final for release:

- final feature-space reconstruction;
- final geometry baselines;
- input-order invariance;
- OPS-versus-SR structural coverage;
- species-balanced random-baseline comparison;
- prospective OPS-versus-SR decision checkpoint;
- leave-one-feature-out sensitivity;
- grouped feature-family ablation;
- broader deterministic rebuild;
- update-stability validation;
- update-stability interpretation.

The completed robustness analyses validate reproducibility, sensitivity, and
behaviour under the tested source-universe changes. They do not introduce a new
OPS-versus-SR decision criterion.

## Frozen OPS-versus-SR decision

The pre-specified primary structural-coverage metric is the species-balanced
weighted 95th percentile nearest-panel Euclidean distance.

Its direction changes with panel size:

- OPS is lower at N=10, 20, 50, and 100;
- SR is lower at N=200 and 500.

The primary curves are therefore not uniformly ordered.

The pre-specified secondary coverage evidence also changes direction with panel
size.

The random-baseline ranks are descriptive and do not create an independent
selector rule.

The pre-specified rejection condition for the OPS one-genome-per-species
constraint was not met, but that does not select OPS.

The prospective design allowed a simplicity preference only if performance was
effectively indistinguishable without an unambiguous winner. No prospective
equivalence margin or quantitative definition of "effectively
indistinguishable" was frozen. Applying one now would be post-hoc.

The frozen coverage-stage selector decision is therefore:

**UNRESOLVED**

## Robustness evidence does not create a winner

The later pre-specified robustness analyses do not alter the selector decision.

Feature sensitivity retained the complete 12-coordinate schema.

The deterministic rebuild established exact reproducibility.

Update stability showed no uniform winner between OPS and SR. SR was markedly
more stable in some tested perturbations, particularly addition within already
represented or heavily sampled species and the taxonomy-split scenario. OPS
was more stable in the tested singleton-species merge. Both selectors were
strongly perturbed by addition of previously absent species.

The update-stability protocol prospectively defined no stability threshold,
aggregate stability score, equivalence margin, or selector-decision rule.

Those outcomes therefore cannot be converted into a post-hoc selector choice.

## Release-final decision

The completed validation programme permits the existing selector decision to
be treated as final under the current prospective framework.

That final decision is:

**UNRESOLVED**

Accordingly:

- OPS is not selected;
- SR is not selected;
- the simplicity clause is not invoked;
- no aggregate score is introduced;
- no equivalence margin is introduced;
- no stability threshold is introduced;
- no new tie-breaker is introduced;
- no organism identities are unblinded;
- no BacSelect selector-v1 genome panel is released from this validation
  programme.

This is a valid final outcome of the prospective validation design.

## Release gate

A public BacSelect release that claims a finalized selector-v1 genome panel is
**blocked** until the OPS-versus-SR ambiguity is resolved by a new prospective
selector-resolution phase.

That phase must define its scientific question and decision rule before any new
outcome used for selection is examined.

The completed evidence must not be reweighted, rescored, or selectively
reinterpreted to force a winner.

## Monthly automation gate

Monthly release automation must not publish a selector-v1 panel while the
selector remains unresolved.

Automation infrastructure may be developed and tested in a fail-closed,
non-publishing mode, but publication of monthly BacSelect panels requires a
frozen selector choice first.

Once a selector is legitimately frozen, the monthly production workflow must
bind the selected algorithm, feature schema, source-universe rules, software
environment, and release provenance, and must fail closed when any required
validation or identity check fails.

## Next scientific step

The next scientific step is a **new prospective selector-resolution phase**,
not another retrospective interpretation of the existing evidence.

Its design must be frozen before outcome-producing execution.

Only after that phase yields and freezes a selector decision should the project
proceed to:

1. selector unblinding/audit;
2. final selector-v1 panel generation;
3. release packaging and public release;
4. monthly fail-closed automation.

Until then, the final selector status is:

**UNRESOLVED — RELEASE BLOCKED**
