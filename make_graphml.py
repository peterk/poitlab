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
import sys
from itertools import combinations

NAMESPACES = {	
        'schema' : Namespace('http://schema.org/'),
        'dcterms' : Namespace('http://purl.org/dc/terms/'),
        'wdt' : Namespace('http://www.wikidata.org/prop/direct/'),
        'wd' : Namespace('http://www.wikidata.org/entity/')
        }

g = Graph()
g.load("./data/index.rdf")


# Create a graph of all objects by post
basegraph = nx.DiGraph()
for post in g.subjects( RDF.type, NAMESPACES["schema"]["NewsArticle"]):
    print(g.value(post, NAMESPACES["dcterms"]["title"] ))

    # add post node
    basegraph.add_node(post, title=g.value(post, NAMESPACES["dcterms"]["title"]),
            date=g.value(post, NAMESPACES["schema"]["datePublished"]),
            itype="Post")

    for post,p,item in g.triples( (post, NAMESPACES["schema"]["about"], None) ):
        print("\t" + g.label(item))
        itemtype = "Person"
        if g.value(item, NAMESPACES["schema"]["geo"]):
            itemtype="Place"
        print("\t\t" + itemtype)

        imageurl = g.value(item, NAMESPACES["schema"]["image"])
        if imageurl:
            basegraph.add_node(item, title=g.label(item), itype=itemtype, imageurl=imageurl)
        else:
            basegraph.add_node(item, title=g.label(item), itype=itemtype)

        basegraph.add_edge(post, item)

print(f"Base graph node count: {basegraph.number_of_nodes()}")
nx.write_gml(basegraph, "./data/poit.gml")



# Create a graph of co-occurring people in posts
copeople = nx.Graph() 

sq = """PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>        
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT DISTINCT ?postid ?person ?label 
WHERE {
?person wdt:P31 wd:Q5 .
?person rdfs:label ?label .
?post schema:about ?person .
?post dcterms:identifier ?postid .
FILTER NOT EXISTS{?person rdfs:seeAlso wd:Q1142091 }
}
ORDER BY ?postid

"""


qres = g.query(sq)

res = {}

for row in qres:
    if not str(row["postid"]) in res:
        res[str(row["postid"])] = []
    res[str(row["postid"])].append(str(row["label"]))

for key in res:
    copeople.add_edges_from(combinations(res[key],2))

print(f"Co-occurence graph node count: {copeople.number_of_nodes()}")
nx.write_gml(copeople, "./data/copeople.gml")

