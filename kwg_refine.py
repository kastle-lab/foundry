import os
import logging
import csv

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# Set up logging
logging.basicConfig(level=logging.WARNING)    

################################################################
##### MAPPING INIT #####
################################################################
# Directory stuff
mapping_dir = "mapping"
mapping_file = "earthquake-mapping.yaml"
mapping_path = os.path.join(mapping_dir, mapping_file)

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
	log.error(msg)
	raise Exception(msg)

################################################################
##### GRAPH INIT #####
################################################################
##### Graph stuff
import rdflib
from rdflib import URIRef, Graph, Namespace, Literal
from rdflib import OWL, RDF, RDFS, XSD, TIME
# Prefixes
name_space = "http://stko-kwg.geog.ucsb.edu/"
pfs = {
"kwgr": Namespace(f"{name_space}lod/resource/"),
"kwg-ont": Namespace(f"{name_space}lod/ontology/"),
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
"time": Namespace("http://www.w3.org/2006/time#"),
"ssn": Namespace("http://www.w3.org/ns/ssn/"),
"sosa": Namespace("http://www.w3.org/ns/sosa/"),
"cdt": Namespace("http://w3id.org/lindt/custom_datatypes#"),
"ex": Namespace("https://example.com/")
}
# Initialization shortcut
def init_kg(prefixes=pfs):
    kg = Graph()
    for prefix in pfs:
        kg.bind(prefix, pfs[prefix])
    return kg
# rdf:type shortcut
a = pfs["rdf"]["type"]

################################################################
##### DO MAPPING #####
################################################################
# open the data file
data_dir = "data"
data_file = "earthquake_fulldata_header_20.csv"
data_path = os.path.join(data_dir, data_file)
output_dir = "output"
if not os.path.exists(output_dir):
	os.makedirs(output_dir)
logging.info(f"Opening: {data_path}")

def create_uri_from_string(s):
	tokens = s.split(":")
	if len(tokens) == 1: # use default namespace
		prefix = pfs["ex"]
	elif len(tokens) == 2:
		prefix, classname = tokens
	else:
		msg = f"Malformed type found: {mapping['type']}"
		log.error(msg)
		raise Exception(msg)

	return pfs[prefix][classname]

def apply_mapping(row, mapping, graph):
	### Check if it's just linking to a specific URI
	if isinstance(mapping, str):
		return create_uri_from_string(mapping)

	### Check if this is a datatype value
	try:
		datatype = create_uri_from_string(mapping["datatype"])
		try:
			val = row[mapping["val_source"]]
		except KeyError:
			val = mapping["value"]
		literal_value = Literal(val,datatype=datatype)	
		return literal_value
	except KeyError:
		"""Just means it's not a datatype"""

	### Create the node for the current layer
	# Mint a URI for the node
	instance_uri_string = create_uri_from_string(mapping["uri"])
	try:
		varids = mapping["varids"]
		varid_vals = list()
		for varid in varids:
			try:
				varid_vals.append(row[varid])
			except KeyError:
				msg = "Variable ID missing from data file."
				logging.error(msg)
				raise Exception(msg)
		instance_uri_string += "." + '.'.join(varid_vals)
		try:
			instance_uri_string += "." + mapping["appellation"]
		except KeyError:
			pass
	except KeyError:
		pass
	instance_uri = URIRef(instance_uri_string)

	### Add types, if desired
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
			graph.add( (instance_uri, a, class_uri) )
	except KeyError:
		try:
			ref = mapping["ref"]
		except KeyError:
			ref = False
		if not ref:
			logging.warning(f"Added instance without type: {instance_uri}")
		pass

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
				graph.add( (instance_uri, pred_uri, target_uri) )
			try:
				inv_uri = create_uri_from_string(connection["inv"])
				graph.add( (target_uri, inv_uri, instance_uri) )
			except KeyError:
				"""There is no inverse, which is ok."""
	except KeyError:
		"""There are no downstream connections, which is ok."""
	return instance_uri

# Get the data
with open(data_path, "r") as data_stream:
	logging.info("Open success.")
	reader = csv.DictReader(data_stream)
	logging.info("Load success.")

	### Generate any constants (e.g., controlled vocabularies)
	for i, cv in enumerate(mapping["cvs"]):
		# Create an empty graph
		graph = init_kg()
		# Apply the mapping (pass by reference)
		class_uri = create_uri_from_string(cv["type"])
		for instance in cv["instances"]:
			instance_uri_string = f"{cv['uri']}.{instance}"
			instance_uri = create_uri_from_string(instance_uri_string)
			graph.add( (instance_uri, a, class_uri) )
		# Serialize and output the fragment
		logging.info("Serializing the fragment.")
		output_file = f"output-cv-{i}.ttl"
		output_path = os.path.join(output_dir, output_file)
		graph.serialize(format="turtle", encoding="utf-8", destination=output_path)
		logging.info("Serialized.")

	### Apply the mapping for each row in the csv
	for row in reader:
		# Create an empty graph
		graph = init_kg()
		# Apply the mapping (pass by reference)
		apply_mapping(row, root, graph)
		# Serialize and output the fragment
		logging.info("Serializing the fragment.")
		output_file = f"output-{row['id']}.ttl"
		output_path = os.path.join(output_dir, output_file)
		graph.serialize(format="turtle", encoding="utf-8", destination=output_path)
		logging.info("Serialized.")