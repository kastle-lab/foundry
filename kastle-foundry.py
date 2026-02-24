import xml.etree.ElementTree as ET
from rdflib import OWL, RDF, RDFS, XSD, TIME
from rdflib import URIRef, Graph, Namespace, Literal
import rdflib
import sys
import os
import logging
import csv
import argparse

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
from urllib.parse import quote

parser = argparse.ArgumentParser(
    description="Generate RDF knowledge graphs from a mapping and CSV/XML data."
)
parser.add_argument(
    "-m", "--mapping",
    required=True,
    help="Path to the YAML mapping file"
)
parser.add_argument(
    "-d", "--data",
    required=True,
    help="Path to the input data file (CSV or XML)"
)
parser.add_argument(
    "-o", "--output-dir",
    default="output",
    help="Directory to write output Turtle files"
)
parser.add_argument(
    "--namespace", "--n",
    required=True,
    help="Base namespace URI"
)
parser.add_argument(
    "--prefix",
    default="ex",
    help="Prefix to use for the base namespace (default: ex)"
)
parser.add_argument(
    "-v", "--verbose",
    action="store_true",
    help="Enable verbose logging (DEBUG level)"
)
parser.add_argument(
    "--log-file",
    help="Log file name (if omitted, logs go to stderr)"
)

cli_args = parser.parse_args()

# 
# Set up and configure logging
log_level = logging.DEBUG if cli_args.verbose else logging.WARNING

logging_kwargs = {
    "level": log_level,
    "format": "%(asctime)s - %(levelname)s - %(message)s",
}

if cli_args.log_file:
    logging_kwargs["filename"] = cli_args.log_file
    logging_kwargs["filemode"] = "w"  # overwrite each run

logging.basicConfig(**logging_kwargs)

################################################################
##### MAPPING INIT #####
################################################################
# Directory stuff
mapping_path = cli_args.mapping

# Open the mapping file
logging.info(f"Opening: {mapping_path}")
mapping = None
with open(mapping_path, "r") as mapping_stream:
    logging.info("Open success.")
    mapping = load(mapping_stream, Loader=Loader)
    logging.info("Load success.")
# Catch any loading problems that the parser didn't catch
if mapping is None:
    raise Exception("Mapping not properly loaded.")
# Get the root mapping (i.e., what will be recursively applied to the data)
root = None
try:
    root = mapping["root"]
except KeyError:
    msg = "Missing root in mapping file, which is required"
    logging.error(msg)
    raise Exception(msg)


################################################################
##### DO MAPPING #####
################################################################
# open the data file
data_path = cli_args.data
output_dir = cli_args.output_dir
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
logging.info(f"Opening: {data_path}")

################################################################
##### GRAPH INIT #####
################################################################
# Graph stuff
# Prefixes
name_space = cli_args.namespace
pf_to_use = cli_args.prefix
pfs = {
    f"{pf_to_use}-r": Namespace(f"{name_space}lod/resource/"),
    f"{pf_to_use}-ont": Namespace(f"{name_space}lod/ontology/"),
    "geo": Namespace("http://www.opengis.net/ont/geosparql#"),
    "geof": Namespace("http://www.opengis.net/def/function/geosparql/"),
    "sf": Namespace("http://www.opengis.net/ont/sf#"),
    "wd": Namespace("http://www.wikidata.org/entity/"),
    "wdt": Namespace("http://www.wikidata.org/prop/direct/"),
    "rdf": RDF,
    "rdfs": RDFS,
    "xsd": XSD,
    "owl": OWL,
    "time": TIME,
    "dbo": Namespace("http://dbpedia.org/ontology/"),
    "ssn": Namespace("http://www.w3.org/ns/ssn/"),
    "sosa": Namespace("http://www.w3.org/ns/sosa/"),
    "cdt": Namespace("http://w3id.org/lindt/custom_datatypes#"),
    "ex": Namespace("https://example.com/"),
    "dcterms": Namespace("http://purl.org/dc/terms/"),
}

# rdf:type shortcut
a = pfs["rdf"]["type"]

# Initialization shortcut
def init_kg(prefixes=pfs):
    kg = Graph()
    for prefix in prefixes:
        kg.bind(prefix, prefixes[prefix])
    return kg

def create_uri_from_string(s):
    tokens = s.split(":")
    if len(tokens) == 1:  # use default namespace
        prefix = pfs[f"{pf_to_use}-r"]
    elif len(tokens) == 2:
        prefix, classname = tokens
    else:
        msg = f"Malformed type found: {mapping['type']}"
        logging.error(msg)
        raise Exception(msg)
    if prefix not in pfs:
        logging.error(f"Unknown prefix '{prefix}' in '{s}'")
        raise Exception(f"Unknown prefix '{prefix}' in '{s}'")

    return pfs[prefix][classname]


def apply_mapping(row, mapping, graph):
    # Check if it's ONLY linking to a specific URI
    if isinstance(mapping, str):
        return create_uri_from_string(mapping)

    # Check if this is a datatype value
    try:
        if row[mapping["val_source"]] or mapping["value"]:
            # Get the datatype
            datatype = create_uri_from_string(mapping["datatype"])
            # Get the value for the literal
            # There are two ways to do this, with val_source checked first
            # The spec says that val_source and value are exlusive
            try:
                # Retrieve the data from a row in the data source
                val = row[mapping["val_source"]]
            except KeyError:
                # The data is hardcoded as part of the mapping
                try:
                    val = mapping["value"]
                except KeyError:
                    msg = "'value' or 'val_source' must be defined for a datatype node."
                    logging.error(msg)
                    raise Exception(msg)
            # Encode the data
            literal_value = Literal(val, datatype=datatype)
            # Return it to be linked
            # There should never be a connection from a datatype node
            return literal_value
    except KeyError:
        """Just means it's not a datatype, so we keep going"""
        logging.info("Not a datatype node, keep going.")

    # Create the node for the current layer
    # Mint a URI for the node
    instance_uri_string = create_uri_from_string(mapping["uri"])
    try:
        varids = mapping["varids"]
        varid_vals = list()
        for varid in varids:
            try:
                varid_vals.append(quote(row[varid], safe=""))
            except KeyError:
                msg = "Variable ID missing from data file."
                logging.error(msg)
                raise Exception(msg)
        instance_uri_string += "." + '.'.join(varid_vals)
        try:
            instance_uri_string += "." + mapping["appellation"]
        except KeyError:
            logging.info("Appellation not defined, skipping.") # Appellation is optional
    except KeyError:
        logging.info("Varids not defined, skipping.") # Varids are optional, if unusual to be so
    # Create the URI from the constructed string
    instance_uri = URIRef(instance_uri_string)

    # Add types, if desired
    try:
        # Detect if there are multiple types
        types = list()
        if isinstance(mapping["type"], str):
            types.append(mapping["type"])
        else:
            types = mapping["type"]
        for t in types:
            # Declare the class (i.e., type) of this node
            class_uri = create_uri_from_string(t)
            # Add it to the graph fragment
            graph.add((instance_uri, a, class_uri))
    except KeyError:
        try:
            ref = mapping["ref"]
        except KeyError:
            # If 'ref' is not explicitly defined, then it is false.
            ref = False
        if not ref:
            logging.warning(f"Added instance without type: {instance_uri}")

    # Connect this node to next layer
    try:
        for connection in mapping["connections"]:
            # Get URI for target (i.e., the object)
            target_uri = apply_mapping(row, connection["o"], graph)
            # Get URI(s) for predicates
            preds = connection["p"]
            if not isinstance(preds, list):
                preds = [preds]
            for pred in preds:
                pred_uri = create_uri_from_string(pred)
                graph.add((instance_uri, pred_uri, target_uri))
            try:
                inv_uri = create_uri_from_string(connection["inv"])
                graph.add((target_uri, inv_uri, instance_uri))
            except KeyError:
                """There is no inverse, which is ok."""
    except KeyError:
        """There are no downstream connections, which is ok."""
    return instance_uri


def iter_val_sources(mapping_node):
    """Yield every val_source used anywhere in the mapping."""
    if isinstance(mapping_node, dict):
        if "val_source" in mapping_node:
            yield mapping_node["val_source"]
        # datatype nodes also live under "o"
        for k, v in mapping_node.items():
            if isinstance(v, (dict, list)):
                yield from iter_val_sources(v)
    elif isinstance(mapping_node, list):
        for item in mapping_node:
            yield from iter_val_sources(item)


def xml_get_texts(xml_root, path):
    """
    Return list of text values for a simple slash-separated tag path.
    Joins repeated leaf tags (e.g., multiple <Author> tags).
    """
    parts = [p for p in path.split("/") if p]
    elems = [xml_root]
    for part in parts:
        next_elems = []
        for e in elems:
            next_elems.extend(list(e.findall(part)))
        elems = next_elems
        if not elems:
            return []
    out = []
    for e in elems:
        if e.text is not None:
            t = e.text.strip()
            if t != "":
                out.append(t)
    return out


def build_row_from_xml(xml_path, mapping):
    """
    Build a dict like csv.DictReader would, with keys for:
    - ID/Control_ID/etc. (top-level)
    - every val_source found in the mapping
    Missing paths are included as empty strings to avoid KeyError in apply_mapping().
    """
    tree = ET.parse(xml_path)
    xr = tree.getroot()

    # ensure all varids exist in row
    def collect_varids(mapping_node):
        ids = set()
        if isinstance(mapping_node, dict):
            if "varids" in mapping_node:
                ids.update(mapping_node["varids"])
            for v in mapping_node.values():
                if isinstance(v, (dict, list)):
                    ids.update(collect_varids(v))
        elif isinstance(mapping_node, list):
            for item in mapping_node:
                ids.update(collect_varids(item))
        return ids
    
    row = {}
    for vid in collect_varids(mapping):
        el = xr.find(vid)
        row[vid] = (el.text.strip() if (el is not None and el.text) else "")

    vs_values = {}
    for vs in sorted(set(iter_val_sources(mapping))):
        vals = xml_get_texts(xr, vs)
        # normalize + dedupe, preserving order
        vals = [v.strip() for v in vals if v and v.strip()]
        seen = set()
        vals = [v for v in vals if not (v in seen or seen.add(v))]

        vs_values[vs] = vals
        row[vs] = vals[0] if vals else ""

    rows = [row]

    def row_sig(d):
        return tuple(sorted(d.items()))

    seen_rows = {row_sig(row)}

    for vs, vals in vs_values.items():
        if len(vals) > 1:
            for extra_val in vals[1:]:
                r = dict(row)
                r[vs] = extra_val
                sig = row_sig(r)
                if sig not in seen_rows:
                    rows.append(r)
                    seen_rows.add(sig)

    return rows

j = 0
rows = None
if data_path.lower().endswith(".xml"):
    rows = build_row_from_xml(data_path, mapping)

    # Generate any constants (e.g., controlled vocabularies)
    try:
        for i, cv in enumerate(mapping["cvs"]):
            # Create an empty graph
            graph = init_kg()
            # Apply the mapping (pass by reference)
            class_uri = create_uri_from_string(cv["type"])
            for instance in cv["instances"]:
                instance_uri_string = f"{cv['uri']}.{instance}"
                instance_uri = create_uri_from_string(instance_uri_string)
                graph.add((instance_uri, a, class_uri))
            # Serialize and output the fragment
            logging.info("Serializing the fragment.")
            base = os.path.splitext(os.path.basename(data_path))[0]
            output_file = f"output-cv-{base}-{i}.ttl"
            output_path = os.path.join(output_dir, output_file)
            graph.serialize(format="turtle", encoding="utf-8",
                            destination=output_path)
            logging.info("Serialized.")
    except KeyError as e:
        logging.info("No CVs detected.")

    for row in rows:
        # Create an empty graph
        graph = init_kg()
        # Apply the mapping (pass by reference)
        apply_mapping(row, root, graph)
        # Serialize and output the fragment
        logging.info("Serializing the fragment.")
        base = os.path.splitext(os.path.basename(data_path))[0]
        output_file = f"output-{base}-{j}.ttl"
        output_path = os.path.join(output_dir, output_file)
        graph.serialize(format="turtle", encoding="utf-8",
                        destination=output_path)
        logging.info("Serialized.")
        j += 1
else:
    # Get the data out of the CSV
    with open(data_path, "r") as data_stream:
        # Load the csv
        logging.info("CSV Open success.")
        reader = csv.DictReader(data_stream)
        if reader == None:
            logging.info("CSV Load failure.")
        logging.info("CSV Load success.")

        # Generate any constants (e.g., controlled vocabularies)
        try:
            for i, cv in enumerate(mapping["cvs"]):
                # Create an empty graph
                graph = init_kg()
                # Apply the mapping (pass by reference)
                class_uri = create_uri_from_string(cv["type"])
                for instance in cv["instances"]:
                    instance_uri_string = f"{cv['uri']}.{instance}"
                    instance_uri = create_uri_from_string(instance_uri_string)
                    graph.add((instance_uri, a, class_uri))
                # Serialize and output the fragment
                logging.info("Serializing the fragment.")
                base = os.path.splitext(os.path.basename(data_path))[0]
                output_file = f"output-cv-{base}-{i}.ttl"
                output_path = os.path.join(output_dir, output_file)
                graph.serialize(format="turtle", encoding="utf-8",
                                destination=output_path)
                logging.info("Serialized.")
        except KeyError as e:
            logging.info("No CVs detected.")

        # Apply the mapping for each row in the csv
        for row in reader:
            # Create an empty graph
            graph = init_kg()
            # Apply the mapping (pass by reference)
            apply_mapping(row, root, graph)
            # Serialize and output the fragment
            logging.info("Serializing the fragment.")
            base = os.path.splitext(os.path.basename(data_path))[0]
            output_file = f"output-{base}-{j}.ttl"
            output_path = os.path.join(output_dir, output_file)
            graph.serialize(format="turtle", encoding="utf-8",
                            destination=output_path)
            logging.info("Serialized.")
            j += 1

# Usage:
#   python kastle-foundry.py \
#       -m <mapping_file> \
#       -d <data_file> \
#       -o <output_dir> \
#       --namespace <namespace> \
#       [--prefix <prefix_for_namespace>] \
#       [-v] \
#       [--log-file <log_filename>]
#
# Examples:
#  Example 1:
#    python kastle-foundry.py \
#        -m example_inputs/earthquake-mapping.yaml \
#        -d example_inputs/earthquake_example_data.csv \
#        -o output/ \
#        --namespace http://stko-kwg.geog.ucsb.edu/ \
#        --prefix kwg \
#        -v \
#        --log-file kastle-foundry.log
#  Example 2:
#    python kastle-foundry.py \
#        -m example_inputs/earthquake-mapping.yaml \
#        -d example_inputs/earthquake_example_data.csv \
#        -o output/ \
#        --namespace http://stko-kwg.geog.ucsb.edu/ \
#        --prefix kwg