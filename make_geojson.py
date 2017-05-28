import certifi
import json
from rdflib.namespace import Namespace
from rdflib import Graph, BNode, RDF, RDFS, URIRef, Literal, XSD
import pygeoj
from geojson import Feature, Point
import coloredlogs, logging


geoj = pygeoj.new()

NAMESPACES = {	
   'schema' : Namespace('http://schema.org/'),
   'dcterms' : Namespace('http://purl.org/dc/terms/')
}

g = Graph()

g.parse("./data/poit.rdf")

qres = g.query(
    """
    PREFIX sdo: <http://schema.org/>    
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dc: <http://purl.org/dc/terms/>

    SELECT DISTINCT ?newsitemlabel ?label ?lon ?lat ?newsitemdate ?url
       WHERE {
          ?item rdfs:label ?label .
          ?item sdo:geo ?geo .
          ?geo sdo:latitude ?lat .
          ?geo sdo:longitude ?lon .
          ?newsitem sdo:about ?item .
          ?newsitem dc:title ?newsitemlabel .
          ?newsitem sdo:datePublished ?newsitemdate .
          ?newsitem sdo:url ?url .
       }""")

for row in qres:
    p = Point((float(row[2].value), float(row[3].value)))
    desc = f"{row[1]}: {row[4]}<br><a href='{row[5]}'>{row[0]}</a>"
    f = Feature(geometry=p)
    f.properties = {"description": desc, "name":row[1], "time": row[4], "url": row[5]}
    geoj.add_feature(f)

geoj.save("./map/poit.json")
