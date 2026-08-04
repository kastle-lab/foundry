# Chris LearningStrategy YAML Comparison Report

## Files compared

- Chris's manual mapping: `learning_strategies.yaml`
- Generated mapping: `generated-learning-strategies.yaml`

## Overall result

The generated YAML has the correct root class and root URI, but it reproduces only one of the four unique predicates used in Chris's manual mapping.

| Metric | Chris's YAML | Generated YAML |
|---|---:|---:|
| Root-level connections | 4 | 1 |
| Total predicate entries | 6 | 11 |
| Unique predicates | 4 | 11 |
| Matched unique predicates | 1 | 1 |

The one matching predicate is:

- `aplo-ont:hasPedagogicalTechnique`

The generated YAML is missing three predicates used by Chris:

- `aplo-ont:hasName`
- `aplo-ont:hasDescription`
- `aplo-ont:hasLearningObjective`

## 1. Root comparison

| Item | Chris's YAML | Generated YAML | Result |
|---|---|---|---|
| Root type | `aplo-ont:LearningStrategy` | `aplo-ont:LearningStrategy` | Match |
| Root URI | `aplo-r:learningStrategy` | `aplo-r:learningStrategy` | Match |
| Root `varids` | Present | Not generated | Expected data-dependent difference |
| Metadata | Present | Not generated | Expected data-dependent difference |

## 2. Expected structure in Chris's mapping

Chris's manual YAML contains these root branches:

1. `LearningStrategy → hasName → xsd:string`
2. `LearningStrategy → hasDescription → xsd:string`
3. `LearningStrategy → hasLearningObjective → LearningObjective`
4. `LearningStrategy → hasPedagogicalTechnique → PedagogicalTechnique`

The `LearningObjective` and `PedagogicalTechnique` nodes each contain a nested:

```text
hasName → xsd:string
```

These branches are tied to CSV columns through `varids`, `val_source`, and `split`.

## 3. Structure produced by the generator

The generated YAML contains only one root branch:

```text
LearningStrategy → hasPedagogicalTechnique → PedagogicalTechnique
```

It then recursively follows additional ontology relationships:

```text
PedagogicalTechnique → isPedagogicalTechniqueOf → LearningStrategy
PedagogicalTechnique → targetsLearningObjective → LearningObjective
LearningObjective → alignedWith → PedagogicalElement
LearningObjective → isLearningObjectiveSupportedBy → Media
LearningObjective → isLearningObjectiveTargetedBy → PedagogicalTechnique
LearningObjective → worksOnSituation → LearningSituation
LearningSituation → requiresTopicKnowledge → Topic
```

## 4. Main mismatches

### Missing literal properties

The generated YAML does not include:

- `hasName`
- `hasDescription`

This means it cannot reproduce the literal CSV-value branches used in Chris's mapping.

**Classification:** current generator limitation or ontology-modeling difference. The ontology must be inspected before assigning the exact cause.

### Missing direct `hasLearningObjective` relationship

Chris's manual mapping uses:

```text
LearningStrategy → hasLearningObjective → LearningObjective
```

The generated YAML instead reaches `LearningObjective` indirectly:

```text
LearningStrategy
→ hasPedagogicalTechnique
→ PedagogicalTechnique
→ targetsLearningObjective
→ LearningObjective
```

These paths are not structurally equivalent.

**Classification:** unresolved mapping-versus-ontology difference. The ontology must be checked to determine whether `hasLearningObjective` is directly declared, represented through another pattern, or added only in the manual mapping.

### Extra ontology relationships

The generator contains ten predicates not used in Chris's manual mapping:

- `aplo-ont:alignedWith`
- `aplo-ont:isAlignmentFor`
- `aplo-ont:isLearningObjectiveSupportedBy`
- `aplo-ont:isLearningObjectiveTargetedBy`
- `aplo-ont:isPedagogicalTechniqueOf`
- `aplo-ont:isSituationWorkedOnBy`
- `aplo-ont:requiresTopicKnowledge`
- `aplo-ont:supportsLearningObjective`
- `aplo-ont:targetsLearningObjective`
- `aplo-ont:worksOnSituation`

These may be valid ontology relationships, but Chris's dataset-specific mapping does not use them.

**Classification:** expected difference between broad ontology traversal and dataset-specific mapping selection.

### Circular inverse traversal

The generated YAML immediately follows inverse relationships back toward already visited classes. For example:

```text
LearningStrategy
→ hasPedagogicalTechnique
→ PedagogicalTechnique
→ isPedagogicalTechniqueOf
→ LearningStrategy
```

It also generates other forward-and-inverse pairs such as:

```text
LearningObjective → alignedWith → PedagogicalElement
PedagogicalElement → isAlignmentFor → LearningObjective
```

These circular paths are absent from Chris's manual mapping.

**Classification:** probable generator traversal issue.

**Recommended improvement:** use a path-aware visited set and avoid immediately traversing an inverse edge back to the previous class.

## 5. Data-dependent differences

Chris's YAML contains fields that cannot be selected reliably from the ontology alone:

- `metadata`
- `varids`
- `val_source`
- `split`
- CSV-specific resource choices

Their absence is expected for the current ontology-only prototype.

## 6. Conclusions

### What works

- The ontology parses successfully.
- The root class and root URI are correct.
- `hasPedagogicalTechnique` is discovered.
- Object-property relationships and inverse relationships are traversed.

### What needs investigation or improvement

1. Determine why `hasName` and `hasDescription` are absent.
2. Determine why the direct `hasLearningObjective` branch is absent.
3. Reduce circular inverse traversal.
4. Separate complete ontology exploration from dataset-specific mapping generation.
5. Extend comparison beyond predicate names to subject-predicate-object structures and datatypes.

## Combined observation from Chris's two tests

Both the LearningObjective and LearningStrategy tests show the same broad pattern:

- Correct root class and URI
- Missing literal-value predicates
- Missing dataset-selected relationships
- Extra ontology traversal
- Circular inverse paths
- Missing CSV-dependent fields

This suggests the current generator is useful as an ontology relationship explorer, but it does not yet reproduce Chris's dataset-specific Foundry mappings.
## Confirmed causes from ontology inspection

- `hasName` and `hasDescription` use anonymous `owl:unionOf` domains containing both `LearningObjective` and `LearningStrategy`.
- `hasLearningObjective` also uses an `owl:unionOf` domain containing `Module` and `LearningStrategy`.
- The current generator does not expand classes contained inside `owl:unionOf`, so these predicates are missed.
- Running with `full-schema.owl` generated 68 unique predicates compared with only 4 in Chris's manual mapping, demonstrating excessive ontology traversal.

## Next step

Inspect `learning-objective-pattern.owl` to determine exactly how the missing predicates are modeled. Only after that inspection should the script be changed.
