import os
import logging
import csv

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# Set up logging
logging.basicConfig(level=logging.INFO)    

################################################################
##### MAPPING INIT #####
################################################################
# directory stuff
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

# Get the root
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
	try:
		### Check if this is a datatype value
		datatype = create_uri_from_string(mapping["datatype"])
		literal_value = Literal(row[mapping["value"]],datatype=datatype)
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
	### Check that there is a type
	try:
		# CV -- controlled vocabulary
		# Generally means the uri in the yaml has been minted elsewhere
		if mapping["type"] == "cv":
			controlled_uri = create_uri_from_string(mapping["uri"])
			return controlled_uri
		else:
			# Declare the class (i.e., type) of this node
			class_uri = create_uri_from_string(mapping["type"])
			# Add it to the graph fragment
			graph.add( (instance_uri, a, class_uri) )
	except KeyError:
		raise Exception("Type field must be present")

	# Connect this node to next layer
	try:
		for connection in mapping["connections"]:
			target_uri = apply_mapping(row, connection["o"], graph)
			pred_uri = create_uri_from_string(connection["p"])
			graph.add( (instance_uri, pred_uri, target_uri) )
	except KeyError:
		"""There are no downstream connections."""
	return instance_uri
with open(data_path, "r") as data_stream:
	logging.info("Open success.")
	reader = csv.DictReader(data_stream)
	logging.info("Load success.")

	for row in reader:
		graph = init_kg()
		apply_mapping(row, root, graph)
		# serialize the fragment
		logging.info("Serializing the fragment.")
		output_file = f"output-{row['id']}.ttl"
		output_path = os.path.join(output_dir, output_file)
		graph.serialize(format="turtle", encoding="utf-8", destination=output_path)
		logging.info("Serialized.")