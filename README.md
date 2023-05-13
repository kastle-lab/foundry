# kwg-refine

## Layout
* `data/` -- expected directory with csv file with data
* `output/` -- expected directory where output files will be placed
* `mapping/` -- required directory, expecting yaml mapping file
* `kwg_refine.py` -- main script

## Example
Essentially, this script will create a graph structure for a row in a csv. Currently, it assumes that there is a root node. It will then traverse the YAML file and create new nodes in the graph using the provided information.

```yaml
root: # (required)
  type: "type"                   # (optional) the rdf:type of the node if absent, will log a warning unless suppressed by "ref: true"
  uri:  "uri"                    # (required) the base uri for this instance
  varids: ["id"]                 # (optional) this is a list of values from the row in the CSV to create a unique URI.
  appellation: "appellation"     # (optional) this is a string to add at the end of the URI.
  connections:                   # (optional) this is a dict of connections 
    - p: "predicate"             # (required) the predicate to connect to the next node
      inv: "inverse"             # (optional) the inverse predicate
      o:                         # (required) the object of the triple / the next node. It has the same attributes as "root"
        type: ["type1", "type2"] # the node can have multiple types
        uri: uri
        varids: ["id"]
        appellation: "appellation"
    # There can be more than one connection from this node
    - p: "predicate"             # (required) the predicate to connect to the next node
      o:                         # (required) the attributes below are for a datatype node
        datatype: "datatype"     # (optional) the uri for the datatype, if this attribute is present (checked first) an rdf:type will NOT be assigned.
        val_source: "val_source" # (exclusive 'or' with value, required) the source column for this literal, used first if both are present
        value: "value"           # (exclusive 'or' with val_source, required) the datum value for this literal
    - p: "predicate"
      o: "uri"                   # (exlusive 'or' with root attributes) a URi to use directly (i.e., the script will not even look for varids or appellation)
    - p: "predicate"
      o:
        uri: "uri"
        varids: ["varid"]
        ref: true                # Will suppress untyped warning
    - p: ["predicate", "predicate"] # It's possible to point to the same object with multiple predicates (rare usecase, but essentially shortcuts the use of a po: with ref construction)
      o: "uri"
```
