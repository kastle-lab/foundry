# Chris LearningObjective YAML Comparison Report

## Files compared

- Chris's manual mapping: `learning_objectives.yaml`
- Generated mapping: `generated-learning-objectives.yaml`

## Overall result

The generated YAML has the correct root class and root URI, but it does not reproduce most of the dataset-specific structure in Chris's manual mapping.

| Metric | Chris's YAML | Generated YAML |
|---|---:|---:|
| Root-level connections | 5 | 4 |
| Total predicate entries | 8 | 12 |
| Unique predicates | 6 | 12 |
| Matched unique predicates | 2 | 2 |

The two matching predicates are:

- `aplo-ont:alignedWith`
- `aplo-ont:worksOnSituation`

The generated YAML is missing four predicates used by Chris:

- `aplo-ont:developsSkill`
- `aplo-ont:hasDescription`
- `aplo-ont:hasName`
- `rdf:value`

## 1. Root comparison

| Item | Chris's YAML | Generated YAML | Result |
|---|---|---|---|
| Root type | `aplo-ont:LearningObjective` | `aplo-ont:LearningObjective` | Match |
| Root URI | `aplo-r:learningObjective` | `aplo-r:learningObjective` | Match |
| Root `varids` | Present | Not generated | Expected data-dependent difference |
| Metadata | Present | Not generated | Expected data-dependent difference |

## 2. Expected structure in Chris's mapping

Chris's manual YAML contains these main branches:

1. `LearningObjective → hasName → xsd:string`
2. `LearningObjective → hasDescription → xsd:string`
3. `LearningObjective → worksOnSituation → LearningSituation → rdf:value`
4. `LearningObjective → developsSkill → Skill → rdf:value`
5. `LearningObjective → alignedWith → PedagogicalElement → hasName`

These branches are directly tied to CSV columns through `val_source`, `varids`, and `split`.

## 3. Structure produced by the generator

The generated YAML contains these root branches:

1. `LearningObjective → alignedWith → PedagogicalElement`
2. `LearningObjective → isLearningObjectiveSupportedBy → Media`
3. `LearningObjective → isLearningObjectiveTargetedBy → PedagogicalTechnique`
4. `LearningObjective → worksOnSituation → LearningSituation`

It also recursively follows inverse and related ontology relationships, including:

- `isAlignmentFor`
- `supportsLearningObjective`
- `targetsLearningObjective`
- `isPedagogicalTechniqueOf`
- `hasPedagogicalTechnique`
- `isSituationWorkedOnBy`
- `requiresTopicKnowledge`
- `isPriorTopicKnowledgeFor`

## 4. Main mismatches

### Missing literal properties

The generated YAML does not include:

- `hasName`
- `hasDescription`
- `rdf:value`

This means the generated mapping cannot yet reproduce the literal CSV-value branches used in Chris's mapping.

**Classification:** current generator limitation or ontology-modeling difference. The ontology must be inspected before assigning the exact cause.

### Missing `developsSkill`

Chris's manual mapping includes:

```text
LearningObjective → developsSkill → Skill
```

The generated YAML does not include this relationship.

**Classification:** unresolved. The ontology must be checked to determine whether the relationship is represented through domain/range, an OWL restriction, another ontology pattern, or only the manual mapping.

### Missing `rdf:value`

A search of all OWL, TTL, and RDF files under Chris's `schema` directory returned no occurrence of `rdf:value`. In the manual YAML, it is used to connect `LearningSituation` and `Skill` resources to CSV text values.

**Classification:** dataset-specific manual mapping choice, not a confirmed generator bug. The ontology-only generator cannot infer this predicate from the supplied schema.
### Extra ontology relationships

The generator includes ten predicates not used in Chris's manual mapping. These relationships may be valid in the ontology, but they are not required for this specific CSV mapping.

**Classification:** expected difference between broad ontology traversal and dataset-specific mapping selection.

### Inverse traversal and cycles

The generated YAML follows relationships back toward classes already visited. Examples include:

```text
LearningObjective → alignedWith → PedagogicalElement
PedagogicalElement → isAlignmentFor → LearningObjective
```

and:

```text
LearningObjective → worksOnSituation → LearningSituation
LearningSituation → isSituationWorkedOnBy → LearningObjective
```

These paths create circular or repeated structures that are absent from Chris's manual mapping.

**Classification:** probable generator traversal issue.

**Recommended improvement:** keep a path-aware visited set for structural triples and avoid immediately traversing an inverse edge back to the previous node.

## 5. Data-dependent differences

Chris's YAML contains fields that cannot be obtained from the ontology alone:

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
- `alignedWith` and `worksOnSituation` are discovered.
- Object-property relationships and explicit inverse properties are traversed.

### What needs investigation or improvement

1. Determine why `hasName`, `hasDescription`, `developsSkill`, and `rdf:value` are absent.
2. Inspect how these relationships are represented in Chris's ontology.
3. Reduce circular inverse traversal.
4. Separate complete ontology exploration from dataset-specific mapping generation.
5. Extend comparison beyond predicate names to subject–predicate–object structures and datatypes.
## Confirmed causes from ontology inspection

Further inspection confirmed the causes of the missing predicates:

- `hasName` and `hasDescription` use anonymous `owl:unionOf` domains containing both `LearningObjective` and `LearningStrategy`. The current generator does not expand union domains.
- `developsSkill` is fully declared in `full-schema.owl`, but not in the smaller `learning-objective-pattern.owl` used during the first test.
- Running the generator with `full-schema.owl` detected `developsSkill`, confirming that the earlier absence was caused by incomplete ontology coverage.
- `rdf:value` does not appear in Chris's schema ontology files and is a dataset-specific manual mapping choice.
- Using `full-schema.owl` generated 76 unique predicates compared with 6 in Chris's manual mapping, showing that unrestricted ontology traversal produces many irrelevant relationships.

## Next step

Run and compare the `LearningStrategy` pair. After that, inspect Chris's OWL ontology to identify whether the missing predicates use OWL restrictions or another modeling pattern.
