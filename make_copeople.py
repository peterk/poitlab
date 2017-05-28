# Create a graphml file of articles, people and places
import requests
import certifi
import json
from lxml import html
from rdflib.namespace import Namespace
from rdflib import Graph, BNode, RDF, RDFS, URIRef, Literal, XSD
import hashlib
import os.path
import pickle
from SPARQLWrapper import SPARQLWrapper, JSON
import csv
import coloredlogs, logging
import networkx as nx
from networkx.readwrite import json_graph
import sys
from itertools import combinations

NAMESPACES = {	
        'schema' : Namespace('http://schema.org/'),
        'dcterms' : Namespace('http://purl.org/dc/terms/'),
        'wdt' : Namespace('http://www.wikidata.org/prop/direct/'),
        'wd' : Namespace('http://www.wikidata.org/entity/')
        }

g = Graph()
g.load("./data/poit.rdf")

# Set up colored logging!
logger = logging.getLogger("poitlab")
coloredlogs.install(level='DEBUG')

# Create a graph of co-occurring people in posts
copeople = nx.Graph() 

sq = """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>        
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT DISTINCT ?postid ?person ?label ?citizencountry 
WHERE {
?person wdt:P31 wd:Q5 .
?person rdfs:label ?label .
?post schema:about ?person .
?post dcterms:identifier ?postid .
OPTIONAL {
?person schema:nationality ?citizenof .
?citizenof rdfs:label ?citizencountry .
}
FILTER NOT EXISTS{?person rdfs:seeAlso wd:Q1142091 }
}
ORDER BY ?postid
"""

qres = g.query(sq)

res = {}

for row in qres:

    if not str(row["postid"]) in res:
        res[str(row["postid"])] = []
    res[str(row["postid"])].append(row)

# Add edges netween all people in this post
for key in res:
    if not len(res[key]) == 0:
        post_node_ids = []
        for row in res[key]:
            logger.info(f"Adding: {row['person']} {row['label']} {row['citizencountry']}")
            copeople.add_node(row["person"], {"label": row["label"], "group": row["citizencountry"] if row["citizencountry"] else "Unknown"})
            post_node_ids.append(row["person"])

        # add combination of edges
        copeople.add_edges_from(combinations(post_node_ids,2))

# Add property values for size based on degree
for node in copeople.nodes():
    copeople.node[node]["size"] = copeople.degree(node)

logger.info(f"Co-occurence graph node count: {copeople.number_of_nodes()}")

nx.write_gml(copeople, "./graph/copeople.gml")

data = json_graph.node_link_data(copeople)

data['links'] = [ {  'source': data['nodes'][link['source']]['id'], 'target':
    data['nodes'][link['target']]['id'] } for link in data['links']]

with open('./graph/copeople.json', 'w') as f:
  json.dump(data, f, ensure_ascii=False, indent=4)

