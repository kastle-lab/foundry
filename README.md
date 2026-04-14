# Kastle Foundry

Kastle Foundry generates RDF/Turtle files from a YAML mapping and CSV or XML input.
It creates one graph fragment per input row.

## Requirements

### Dependecies

- Python 3.10+
- `rdflib`
- `pyyaml`

Install dependencies:

```bash
pip install rdflib pyyaml
```

###### _IMPORTANT NOTE:_

&emsp;For CSV files you must use a `UTF-8` encoding. Otherwise, the program may have unexpected behavior.

## CLI Usage

To run the script:

```bash
python kastle-foundry.py \
  -m <mapping.yaml> \
  -d <input.csv|input.xml|input_directory> \
  --namespace <base_namespace_uri> \
  [-o <output_dir>] \
  [--prefix <prefix>] \
  [-v] \
  [--log-file <logfile_name>]
```

**Note**: _Using verbose debug logging may consume significant storage space for larger datasets._

Arguments:

- `-m, --mapping` (required): YAML mapping file.
- `-d, --data` (required): a CSV file, XML file, or a directory containing `.csv` / `.xml`.
- `--namespace` (required): base namespace URI used to construct `<prefix>-r` and `<prefix>-ont`.
- `-o, --output-dir` (optional): output directory, default `output`.
- `--prefix` (optional): namespace prefix base, default `ex`.
- `-v, --verbose` (optional): enable debug logging.
- `--log-file` (optional): write logs to a file instead of stderr.

Output naming:

- row graphs: `output-<input_basename>-<index>.ttl`
- controlled vocabulary graphs (`cvs`): `output-cv-<input_basename>-<index>.ttl`

### CLI Usage With Included Example

```bash
python kastle-foundry.py \
  -m example_inputs/earthquake-mapping.yaml \
  -d example_inputs \
  -o output \
  --namespace http://stko-kwg.geog.ucsb.edu/ \
  --prefix kwg \
  -v \
  --log-file kastle-foundry.log
```

As shown in the example, using `-d` to `example_inputs/` will process all CSV/XML files in that directory.

## Mapping Model

```yaml
root: # (required)
  type: "type" # (optional) the rdf:type of the node if absent, will log a warning unless suppressed by "ref: true"
  uri: "uri" # (required) the base URI for this instance
  varids: ["id"] # (optional) this is a list of values from the row in the CSV to create a unique URI.
  appellation: "appellation" # (optional) this is a string to add at the end of the URI.
  connections: # (optional) this is a dict of connections
    - p: "predicate" # (required) the predicate to connect to the next node
      inv: "inverse" # (optional) the inverse predicate
      o: # (required) the object of the triple / the next node. It has the same attributes as "root"
        type: ["type1", "type2"] # the node can have multiple types
        uri: uri
        varids: ["id"]
        appellation: "appellation"
    # There can be more than one connection from this node
    - p: "predicate" # (required) the predicate to connect to the next node
      o: # (required) the attributes below are for a datatype node
        datatype: "datatype" # (optional) the URI for the datatype, if this attribute is present (checked first) an rdf:type will NOT be assigned.
        val_source: "val_source" # (exclusive 'or' with value, required) the source column for this literal, used first if both are present
        value: "value" # (exclusive 'or' with val_source, required) the datum value for this literal
        required: true # (optional) ensures an error occurs if true, or a warning if false (defaults to false) for a missing val_source or value.
    - p: "predicate"
      o: "uri" # (exlusive 'or' with root attributes) a URI to use directly (i.e., the script will not even look for varids or appellation)
    - p: "predicate"
      o:
        uri: "kwg-r:instant"
        varids: ["id"]
        ref: true # (optional) reference an existing URI pattern without adding type; suppresses untyped warning
    - p: ["predicate", "predicate"] # it's possible to point to the same object with multiple predicates (rare usecase, but essentially shortcuts the use of a po: with ref construction)
      o:
        datatype: "datatype"
        val_source: ["val_source_1", "val_source_2"]
        value: "value"
```

### Arguments

#### Required

- `root`: top-level mapping key.
- `uri`: required for instance nodes.
- `p`: required for each connection; list is allowed.
- `o`: required for each connection. Can be a nested mapping object or a direct URI-like string.
- Datatype-node value source: when `datatype` is present, at least one of `val_source` or `value` must be provided.

#### Optional

- `type`: instance rdf:type; accepts a single URI-like string or a list of strings.
- `varids`: list of input-field names appended (dot-separated, URL-encoded) to `uri`.
- `appellation`: constant suffix appended after `varids`.
- `connections`: list of downstream predicate-object mappings.
- `inv`: inverse predicate for a connection.
- `datatype`: marks a node as a datatype/literal node and sets literal datatype URI.
- `val_source`: input field name or ordered list of field names (if `value` is also present, uses `val_source` first).
- `value`: constant literal value fallback when `val_source` is not provided.
- `required`: boolean flag on datatype nodes; logs error (`true`) vs warning (`false`) when literal value is missing.
- `ref`: boolean flag for untyped instance references; suppresses untyped-node warning when `true`.

## Minimal root example:

```yaml
root:
  type: "kwg-ont:Earthquake"
  uri: "kwg-r:earthquake"
  varids: ["id"]
```

`varids` are appended to the URI as dot-separated, URL-encoded values.
If `appellation` is present, it is appended after `varids`.

## Complex Behaviors

### 1) Referencing a Node Without Adding Type (`ref: true`)

Use `ref: true` when you intentionally point to an instance URI without assigning a type in that branch.
This suppresses the untyped-node warning.

```yaml
- p: "sosa:phenomenonTime"
  o:
    uri: "kwg-r:instant"
    varids: ["id"]
    ref: true
```

**Note**: `ref: true` does not create special link semantics; it only suppresses the missing-type warning. Reusing the same URI is what makes multiple branches point to the same resource.

### 2) Inverse Predicate (`inv`)

```yaml
- p: "sosa:isFeatureOfInterestOf"
  inv: "sosa:hasFeatureOfInterest"
  o:
    type: "kwg-ont:EarthquakeObservationCollection"
    uri: "kwg-r:earthquakeObservationCollection"
    varids: ["id"]
```

This adds both `(subject p object)` and `(object inv subject)`.

### 3) Multiple Predicates to the Same Object

```yaml
- p: ["geo:hasGeometry", "geo:hasDefaultGeometry"]
  o: "ex:test"
```

Both predicates are emitted for the same object.

### 4) Literal Node From Input Data (`val_source`)

```yaml
- p: "sosa:hasSimpleResult"
  o:
    datatype: "xsd:double"
    val_source: "mag"
```

`val_source` can also be a list; it will mint a literal for each item in that list.

### 5) Literal Node With Constant Value (`value`)

```yaml
- p: "rdfs:label"
  o:
    datatype: "xsd:string"
    value: "EARTHQUAKE!"
```

### 6) Direct URI Object

```yaml
- p: "sosa:observedProperty"
  o: "kwg-r:earthquakeObservableProperty.mag"
```

In this form, `o` is used directly as a URI reference (no `varids`/`appellation` processing).

### Prefix Rules

String values like `kwg-ont:Earthquake`, from the example, must use known prefixes.
Known prefixes include:

- `<prefix>-r` and `<prefix>-ont` from CLI `--prefix` and `--namespace`
- standard entries in the script (`rdf`, `rdfs`, `xsd`, `owl`, `time`, `geo`, `sosa`, etc.)

If an unknown prefix is used, the run fails with an error.
