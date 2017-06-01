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

NAMESPACES = {	
        'schema' : Namespace('http://schema.org/'),
        'dcterms' : Namespace('http://purl.org/dc/terms/'),
        'wdt' : Namespace('http://www.wikidata.org/prop/direct/'),
        'wd' : Namespace('http://www.wikidata.org/entity/')
        }


# Set up colored logging!
logger = logging.getLogger("poitlab")
coloredlogs.install(level='DEBUG')



def books_by_auth(auth):
    result = []

    sq = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>
    PREFIX dbpedia: <http://dbpedia.org/ontology/>
    PREFIX rdfs: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    prefix dc: <http://purl.org/dc/elements/1.1/> 

    SELECT *
    WHERE {{
    ?book dc:creator <http://libris.kb.se/resource/auth/{auth}> .
    <http://libris.kb.se/resource/auth/{auth}> foaf:name ?name .
    ?book dc:title ?title .
    }} LIMIT 1
    """

    sparql = SPARQLWrapper("http://libris.kb.se/sparql")
    sparql.setReturnFormat(JSON)
    sparql.setQuery(sq)
    qres = sparql.query().convert()

    for row in qres["results"]["bindings"]:
        result.append([row['name']['value'], row['book']['value'], row['title']['value']])
        logger.info(f"Adding: {row['name']['value']} {row['book']['value']} {row['title']['value']}")

    return result



def write_books():
    with open("./data/books_by_poitpeople.csv", "w", encoding='utf-8') as f:
        writer = csv.writer(f, dialect=csv.excel)
        for row in sorted(books, key=lambda tup: tup[2]):
            writer.writerow(row)



g = Graph()
g.load("./data/poit.rdf")


sq = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>        
PREFIX wd: <http://www.wikidata.org/entity/>

SELECT ?person ?label ?librisid
WHERE {
      ?person wdt:P31 wd:Q5 .
      ?person rdfs:label ?label .
      ?person wdt:P906 ?librisid .
}
"""

qres = g.query(sq)

books = []

for row in qres:
    logger.info(list(row))
    if row["librisid"]:
        books.extend(books_by_auth(row["librisid"]))

print(books)
write_books()
    
