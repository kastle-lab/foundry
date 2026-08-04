# Michael Robot YAML Comparison Report

## Files compared

- Ground-truth mapping: `robots-arm-mapping.yaml`
- Generated mapping: `generated-robot.yaml`
- Ontology checked for context: `robo-ont.rdf` from Michael's supplied ZIP

## Overall result

The generated YAML successfully includes all 10 unique predicates used by Michael's manual mapping. However, predicate-name coverage alone does not mean the complete mapping is equivalent.

A full scan of the uploaded YAML files found:

| Metric | Michael's YAML | Generated YAML |
|---|---:|---:|
| Total nested connections | 36 | 123 |
| Unique predicates | 10 | 30 |
| Root types | 2 | 2 |
| Unique classes/types | 18 | 20 |

The generator therefore covers the expected predicate names, but it creates a much larger and more generic traversal than Michael's dataset-specific mapping.

## 1. Root comparison

| Item | Michael's YAML | Generated YAML | Result |
|---|---|---|---|
| Root types | `SpatialThing`, `Agent` | `Agent`, `SpatialThing` | Semantic match |
| Root URI | `robo-r:agent` | `robo-r:agent` | Match |
| Root `varids` | `Serial`, `Type`, `Robot` | Not generated | Expected data-dependent difference |

The order and YAML formatting of the root types differ, but the meaning is the same.

## 2. Identifier relationships

Michael's mapping uses the broad property `hasIdentifier` and combines parent and specialized types:

- `Agent/SpatialThing → hasIdentifier → Identifier + Name`
- `Agent/SpatialThing → hasIdentifier → Identifier + Serial`

The generated mapping creates three separate relationships:

- `Agent/SpatialThing → hasIdentifier → Identifier`
- `Agent/SpatialThing → hasName → Name`
- `Agent/SpatialThing → hasSerial → Serial`

The supplied ontology defines `hasName` and `hasSerial` as subproperties of `hasIdentifier`.

**Classification:** ontology/YAML modeling difference and unresolved subproperty-handling rule.

The team needs to decide whether automatic generation should:

1. Use the broad parent property only,
2. Use the most specific subproperty,
3. Or generate both parent and subproperty relationships.

## 3. Specialized classes are missing

Michael's mapping uses multi-type nodes to identify dataset-specific branches, including:

- `AgentCategory`
- `MotionBased`
- `Reach`
- `Push`
- `Pull`
- `ThermalResistant`
- `UpperThreshold`
- `lowerThreshold`

The generated YAML mostly uses only generic types such as:

- `Category`
- `Capability`
- `Threshold`

**Classification:** confirmed generator limitation.

The current generator follows domain/range declarations but does not recreate the specialized subclass combinations selected in the manual mapping.

## 4. Extra ontology relationships

The generated YAML includes 20 predicates not used in Michael's manual mapping, including:

- `assumesRole`
- `assimilatesArchetype`
- `assimilatesRoleCategory`
- `enablesAction`
- `enablesCapability`
- `fulfillsArchetype`
- `hasName`
- `hasSerial`
- `hasSpatiotemporalExtent`
- `hasState`
- `hasTemporalExtent`
- `providesRole`
- `requiresArchetype`
- `requiresCapability`
- `requiresSpatialThing`

These may be valid ontology relationships, but Michael's manual YAML does not use them for this dataset.

**Classification:** expected difference from broad ontology traversal, not automatically a bug.

The generator currently asks, “What relationships exist in the ontology?”  
Michael's mapping answers, “What relationships are needed for this particular dataset?”

## 5. Repeated traversal and duplication

The generated YAML has 123 nested connections compared with 36 in the manual mapping. Several identical structural relationships appear repeatedly along different traversal paths.

Examples include repeated forms of:

- `Capability → enabledBySpatialThing → SpatialThing`
- `Capability → enablesAction → Action`
- `Capability → hasSpec → Specification`
- `SpatialThing → assumesRole → Role`
- `SpatialThing → belongsToCategory → Category`
- `SpatialThing → hasName → Name`
- `SpatialThing → hasSerial → Serial`

At the root level, `assumesRole` and `enablesCapability` each appear twice.

**Classification:** probable generator issue.

**Recommended improvement:** track visited structural triples using a key such as:

```text
(subject class set, predicate, object class/datatype set)
```

This should reduce repeated output while still allowing distinct valid branches.

## 6. Unexpected `robo-ont:z`

The generated YAML contains:

```yaml
- p: robo-ont:z
  o:
    type: robo-ont:Identifier
```

`robo-ont:z` does not appear in Michael's manual YAML and was not found as a property in the supplied robot ontology.

**Classification:** confirmed generator/URI-shortening bug that requires investigation.

## 7. Inverse predicates

Michael's manual YAML includes inverse names such as:

- `identifierOf`
- `isCategoryOf`
- `capabilityOf`
- `isSpecOf`
- `specKindOf`

The generated mapping does not reproduce these inverse values for the corresponding relationships. It only adds inverses for the task relationships `dependsOnTask` and `hasNextTask`.

The supplied robot ontology does not appear to explicitly declare Michael's manual inverse names with `owl:inverseOf`.

**Classification:** ontology/YAML inconsistency or design decision, not automatically a generator bug.

The team must decide whether inverse predicates must be:

- explicitly declared in the ontology,
- inferred from a naming rule,
- or supplied manually.

## 8. Category value difference

Michael's mapping represents categorization type as a literal value:

```text
Category → hasCategorizationType → rdfs:Literal
```

with `val_source: Type`.

The generated mapping represents it as a class:

```text
Category → hasCategorizationType → CategorizationType
```

**Classification:** ontology/YAML modeling inconsistency or dataset-specific mapping decision.

## 9. Units and literal data

Michael's mapping hardcodes specific resources such as:

- millimeters
- grams
- celsius

It also maps CSV columns through `val_source`, including robot name, serial, operating range, payload, and temperature.

The generated mapping creates a generic `Unit` node and datatype nodes without `val_source`.

**Classification:** expected data-dependent difference.

These fields cannot be recreated reliably from the ontology alone:

- `varids`
- `val_source`
- `appellation`
- dataset-specific unit resources

## 10. Main conclusions

### What currently works

- The ontology parses successfully: 638 triples.
- Root classes and root URI are correct.
- All 10 predicate names used by Michael's mapping are discovered.
- Basic domain/range relationships are generated.
- Datatype relationships such as strings and doubles are detected.

### What should be fixed in the script

1. Investigate and remove the unexpected `robo-ont:z`.
2. Add structural triple deduplication.
3. Improve subclass and multi-type handling.
4. Separate complete ontology coverage from dataset-specific mapping generation.
5. Improve the comparison report so it checks classes and subject–predicate–object structures, not only predicate names.

### What requires a team decision

1. Parent property versus most-specific subproperty.
2. How inverse predicates should be obtained.
3. Whether one comprehensive YAML or multiple YAML mappings should be generated.
4. How to choose dataset-relevant branches from the complete ontology.
5. How specialized subclasses should be selected.

## Recommended next step

Do not immediately rewrite the whole generator.

First run the same current generator against Chris's two mappings:

1. `LearningObjective`
2. `LearningStrategy`

Then compare whether the same issues occur:

- excessive traversal,
- repeated triples,
- missing specialized classes,
- subproperty differences,
- missing inverses,
- and data-dependent fields.
