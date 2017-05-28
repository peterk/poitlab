import json
from rdflib.namespace import Namespace
from rdflib import Graph, BNode, RDF, RDFS, URIRef, Literal, XSD
import coloredlogs, logging

logger = logging.getLogger("poitlab")
coloredlogs.install(level='DEBUG')

NAMESPACES = {	
   'schema' : Namespace('http://schema.org/'),
   'dcterms' : Namespace('http://purl.org/dc/terms/')
}

g = Graph()

g.parse("./data/poit.rdf")

cq= """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>        
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX dc: <http://purl.org/dc/terms/>
PREFIX sdo: <http://schema.org/>    
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?post_id ?person ?label ?desc ?thumbnail 
WHERE {
      ?person wdt:P31 wd:Q5 .
      ?person rdfs:label ?label .
      ?person sdo:description ?desc .
      ?post sdo:about ?person .
      ?post dc:identifier ?post_id .
      OPTIONAL {
        ?person sdo:thumbnailUrl ?thumbnail .
      }

      FILTER NOT EXISTS { ?person rdfs:seeAlso wd:Q1142091 }
}
"""

qres = g.query(cq)


post_ids = sorted(set([row['post_id'].value for row in qres]))

for post_id in post_ids:
    people = []
    logger.info(f"Working on {post_id}")
    for row in qres:
        if int(row["post_id"].value) == int(post_id):
            person = {}
            person["name"] = row["label"].value
            person["uri"] = row["person"]
            person["description"] = row["desc"].value
            if row["thumbnail"]:
                person["thumbnail"] = row["thumbnail"].value
            else:
                person["thumbnail"] = "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/User_byStone.png/120px-User_byStone.png"
            people.append(person)

    if len(people) > 0:
        with open(f"./data/postpeople/{post_id}.json", 'w') as outfile:
            json.dump(people, outfile)
    else:
        logger.warn(f"No people for {post_id}")
