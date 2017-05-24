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
import json

NAMESPACES = {	
        'schema' : Namespace('http://schema.org/'),
        'dcterms' : Namespace('http://purl.org/dc/terms/'),
        'wdt' : Namespace('http://www.wikidata.org/prop/direct/'),
        'wd' : Namespace('http://www.wikidata.org/entity/')
        }

ng = nx.DiGraph()
g = Graph()
g.load("./data/poit.rdf")

for post in g.subjects( RDF.type, NAMESPACES["schema"]["NewsArticle"]):
    print(g.value(post, NAMESPACES["dcterms"]["title"] ))
    print(post)
    ng.add_node(post, title=g.value(post, NAMESPACES["dcterms"]["title"]),
            date=g.value(post, NAMESPACES["schema"]["datePublished"]),
            itype="Post")

    for post,p,item in g.triples( (post, NAMESPACES["schema"]["about"], None) ):
        print("\t" + g.label(item))

        itemtype= "other"
        print(g.value(item, NAMESPACES["wdt"]["P31"]))
        if g.value(item, NAMESPACES["wdt"]["P31"]) == NAMESPACES["wd"]["Q5"]:
            itemtype = "human"
            imageurl = g.value(item, NAMESPACES["schema"]["image"])
            if imageurl:
                ng.add_node(item, title=g.label(item), itype=itemtype, imageurl=imageurl)
            else:
                ng.add_node(item, title=g.label(item), itype=itemtype)

        if g.value(item, NAMESPACES["wdt"]["P31"]) == URIRef("http://www.wikidata.org/entity/Q2221906" ):
            itemtype = "place"
            ng.add_node(item, title=g.label(item), itype=itemtype)
            
        print("\t\t" + itemtype)
        ng.add_edge(post, item)

data = json_graph.node_link_data(ng)
with open('./graph/graph.json', 'w') as f:
  json.dump(data, f, ensure_ascii=False, indent=4)


nx.write_gml(ng, "./data/poit.gml")

