import certifi
import json
from rdflib.namespace import Namespace
from rdflib import Graph, BNode, RDF, RDFS, URIRef, Literal, XSD
import pygeoj
from geojson import Feature, Point
import coloredlogs, logging

logger = logging.getLogger("poitlab")
coloredlogs.install(level='DEBUG')

NAMESPACES = {	
   'schema' : Namespace('http://schema.org/'),
   'dcterms' : Namespace('http://purl.org/dc/terms/')
}

g = Graph()

g.parse("./data/poit.rdf")


# Loop posts and create a small geojson file for each of them


qres = g.query("""
PREFIX sdo: <http://schema.org/>    
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dc: <http://purl.org/dc/terms/>

SELECT DISTINCT ?label ?lon ?lat ?post_id
   WHERE {
      ?item rdfs:label ?label .
      ?item sdo:geo ?geo .
      ?geo sdo:latitude ?lat .
      ?geo sdo:longitude ?lon .
      ?newsitem sdo:about ?item .
      ?newsitem dc:identifier ?post_id .
}  ORDER BY ?post_id
""")

post_ids = set([row['post_id'].value for row in qres])



for post_id in post_ids:
    geoj = pygeoj.new()
    logger.info(f"Working on {post_id}")
    for row in qres:
        if int(row["post_id"].value) == int(post_id):
            p = Point((float(row["lon"].value), float(row["lat"].value)))
            f = Feature(geometry=p)
            f.properties = {"description": row['label'].value, "name":row['label'].value}
            geoj.add_feature(f)

    if len(geoj) > 0:
        logger.info(f"Saving features for {post_id}")
        geoj.save(f"./data/postmap/{post_id}.json")
    else:
        logger.warn(f"No features for {post_id}")
