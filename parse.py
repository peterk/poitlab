import requests
import certifi
import json
from lxml import html
from rdflib.namespace import Namespace, NamespaceManager
from rdflib import Graph, BNode, RDF, RDFS, URIRef, Literal, XSD
import hashlib
import os.path
import pickle
from SPARQLWrapper import SPARQLWrapper, JSON
import csv
import coloredlogs, logging
from urllib.parse import urlparse
import xmltodict


NAMESPACES = {	
   'schema' : Namespace('http://schema.org/'),
   'dcterms' : Namespace('http://purl.org/dc/terms/'),
   'wdt' : Namespace('http://www.wikidata.org/prop/direct/'),
   'wd' : Namespace('http://www.wikidata.org/entity/')
}

#Find unknown places (linked with https://www.wikidata.org/wiki/Q2221906 )
unknown_places = []
unknown_persons = []
link_labels = []

# Set up colored logging!
logger = logging.getLogger("poitlab")
coloredlogs.install(level='DEBUG')




def thumb_url(url, size):
    """Return a Wikimedia commons thumbnail URL from the canonical image url
    returned by wikidata. (Necessary to get e.g. tif image thumbnails)"""

    md5 = hashlib.md5()
    md5.update(url.encode('utf-8'))
    filename = os.path.join("wdcache", "thumb_" + md5.hexdigest())
    if os.path.isfile(filename):
        # Get from cache
        with open(filename, 'rb') as cachehandle:
            logger.info(f"Thumb from cache {filename}")
            return pickle.load(cachehandle)

    else:
        name = urlparse(url).path.split("/")[-1]
        r = requests.get(f"https://tools.wmflabs.org/magnus-toolserver/commonsapi.php?image={name}&thumbwidth={size}")
        wcd = xmltodict.parse(r.content)

        # Prepare for caching
        if not os.path.exists("./wdcache"):
            os.makedirs("./wdcache")

        with open(filename, 'wb') as cachehandle:
            logger.warn(f"Storing {filename}")
            pickle.dump(wcd["response"]["file"]["urls"]["thumbnail"], cachehandle)

        return wcd["response"]["file"]["urls"]["thumbnail"]




def parse_identifiers(htmltext):
    """Parse wikidata identifiers from Wikipedia links in text.

    :htmltext: html text containing wikipedia links.
    :returns: list of wikidata identifiers.
    """

    tree = html.fromstring(htmltext)
    links = tree.xpath("//a[@href]")
    wikipedialinks = []

    for link in links:
        href = link.attrib["href"]
        if "wikipedia.org" in href:
            wikipedialinks.append(href.strip())
            link_labels.append((href, link.text_content().strip()))

    titles = page_titles_from_links(wikipedialinks)

    return wikidata_from_wp(titles)



def parse_unknown_items(htmltext, url, post_id):
    tree = html.fromstring(htmltext)
    links = tree.xpath("//a[@href]")
    post_uri = uri_for_post(post_id)

    for link in links:
        href = link.attrib["href"].strip()

        # Unknown place
        if href=="https://www.wikidata.org/wiki/Q2221906":
            place = BNode()
            g.add( (place, RDFS.label, Literal(link.text_content().strip(), lang="sv")))
            # instance of geographic place
            g.add( (place, NAMESPACES["wdt"]["P31"], NAMESPACES["wd"]["Q2221906"] ))
            g.add( (post_uri, NAMESPACES["schema"]["about"], place) )

            unknown_places.append((link.text_content(), url))

        # Unknown person
        if href=="https://sv.wikipedia.org/wiki/N.N.":
            person = BNode()
            g.add( (person, RDFS.label, Literal(link.text_content().strip(), lang="sv")))
            # instance of human
            g.add( (person, NAMESPACES["wdt"]["P31"], NAMESPACES["wd"]["Q5"] ))
            g.add( (person, RDFS.seeAlso, NAMESPACES["wd"]["Q1142091"] ) )
            g.add( (post_uri, NAMESPACES["schema"]["about"], person) )

            unknown_persons.append((link.text_content(), url))




def page_titles_from_links(wp_links):
    """Return a list of page titles parsed from wikipedia page links.
    """
    titles = {}

    for link in wp_links:

        # Get wikipedia edition from language subdomain
        lang = urlparse(link).netloc.split(".")[0]

        if not lang in titles:
            titles[lang] = []
        
        title = link.split("/")[-1]

        if not title in titles[lang]:
            titles[lang].append(title)

    return titles





def wikidata_from_wp(titles):
    """Look up Wikidata URI:s from a list of page titles.
    """

    wikidata_uris = []

    # Ask for page props by language edition
    for lang in titles:
        title_param = "|".join(titles[lang])

        q = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageprops&format=json&titles={title_param}"
        logger.info(f"Requesting pageprops {q}")

        # Cache and reuse if possible
        md5 = hashlib.md5()
        md5.update(q.encode('utf-8'))
        filename = os.path.join("wdcache", "prop_" + md5.hexdigest())
        logger.info(f"Cache name is {filename}")
        if os.path.isfile(filename):
            # Get from cache
            with open(filename, 'rb') as cachehandle:
               jd = pickle.load(cachehandle)
        else:
            # No cache vailable
            r = requests.get(q)
            jd = r.json()

            # Prepare for caching
            if not os.path.exists("./wdcache"):
                os.makedirs("./wdcache")

            with open(filename, 'wb') as cachehandle:
                logger.warn(f"Storing {q}")
                pickle.dump(jd, cachehandle)

        for key, value in jd["query"]["pages"].items():
            wdq = value["pageprops"]["wikibase_item"]
            if wdq:
                wikidata_uris.append("http://www.wikidata.org/entity/" + wdq)
            else:
                logger.warn("Missing wikibase_item")

    return wikidata_uris


def get_basics_for_wduri(wikidata_uri):
    logger.info(f"Requesting data for {wikidata_uri}")
    md5 = hashlib.md5()
    md5.update(wikidata_uri.encode('utf-8'))
    filename = os.path.join("wdcache", "wd_" + md5.hexdigest())
    logger.info(f"Cache for {wikidata_uri} is {filename}")
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    queryres = None
    if os.path.isfile(filename):
        with open(filename, 'rb') as cachehandle:
           queryres = pickle.load(cachehandle)
    else:
        # gör till construct senare

        sparql.setReturnFormat(JSON)

        sq = f'''
SELECT ?itemLabel ?lat ?lon ?country ?countryLabel ?imageurl ?instance ?type
?entityDescription ?citizencountry ?citizencountryLabel ?librisid ?viafid
WHERE
{{
  BIND (<{wikidata_uri}> as ?entity)
  BIND(IF(EXISTS{{?entity wdt:P31 wd:Q5}},"human", IF(EXISTS{{?entity p:P625 ?c}},"place", "other")) AS ?type)
  OPTIONAL {{
    ?entity p:P625 ?coords .
    ?coords ps:P625 ?coord.
    ?coords psv:P625 ?coordinate_node.  
    ?coordinate_node wikibase:geoLatitude ?lat .
    ?coordinate_node wikibase:geoLongitude ?lon .
    ?entity wdt:P17 ?country .
  }}

  OPTIONAL {{
    ?entity wdt:P18 ?imageurl .
  }}
  
  OPTIONAL {{
    ?entity wdt:P27 ?citizencountry .
  }}

  OPTIONAL {{
    ?entity wdt:P906 ?librisid .
  }}
  
  OPTIONAL {{
    ?entity wdt:P214 ?viafid .
  }}

  SERVICE wikibase:label {{ 
    bd:serviceParam wikibase:language "sv,en,de,da,nl,fr" .
    ?entity rdfs:label ?itemLabel .
    ?entity schema:description ?entityDescription .
    ?country rdfs:label ?countryLabel .
    ?citizencountry rdfs:label ?citizencountryLabel .
  }}
}}
LIMIT 1
        '''

        sparql.setQuery(sq)
        queryres = sparql.query().convert()

        if not os.path.exists("./wdcache"):
            os.makedirs("./wdcache")

        with open(filename, 'wb') as cachehandle:
            logger.warn(f"Storing {wikidata_uri}")
            pickle.dump(queryres, cachehandle)


    for result in queryres["results"]["bindings"]:

        #check what this is and make simpler instance info
        if "type" in result:
            logger.info("Instance of %s" % result["type"]["value"])
            if "human" in result["type"]["value"]:
                g.add( (URIRef(wikidata_uri), NAMESPACES["wdt"]["P31"], NAMESPACES["wd"]["Q5"]) )
            if "place" in result["type"]["value"]:
                g.add( (URIRef(wikidata_uri), NAMESPACES["wdt"]["P31"], URIRef("http://www.wikidata.org/entity/Q2221906" )) )

        if "itemLabel" in result:
            logger.info(f'Got label {result["itemLabel"]["value"]}')
            g.add((URIRef(wikidata_uri), RDFS.label, Literal(result["itemLabel"]["value"])))

        if "entityDescription" in result:
            g.add((URIRef(wikidata_uri), NAMESPACES["schema"]["description"],
                Literal(result["entityDescription"]["value"], lang=result["entityDescription"]["xml:lang"])))

        if "lat" in result:
            geo = BNode()
            g.add((geo, RDF.type, NAMESPACES["schema"]["GeoCoordinates"] ))
            g.add((geo, NAMESPACES["schema"]["latitude"], Literal(result["lat"]["value"]) ))
            g.add((geo, NAMESPACES["schema"]["longitude"], Literal(result["lon"]["value"]) ))
            g.add((URIRef(wikidata_uri), NAMESPACES["schema"]["geo"], geo))

        if "citizencountry" in result:
            g.add((URIRef(wikidata_uri), NAMESPACES["schema"]["nationality"],
                URIRef(result["citizencountry"]["value"])))
            g.add((URIRef(result["citizencountry"]["value"]), RDFS.label,
                Literal(result["citizencountryLabel"]["value"])))

        if "imageurl" in result:
            imageurl = result["imageurl"]["value"]
            g.add((URIRef(wikidata_uri), NAMESPACES["schema"]["image"], Literal(imageurl)))

            thumbnail = thumb_url(imageurl, 120)
            g.add((URIRef(wikidata_uri), NAMESPACES["schema"]["thumbnailUrl"], Literal(thumbnail)))
            logger.info(f"Added thumbnail {thumbnail}")

        if "librisid" in result:
            g.add( (URIRef(wikidata_uri), NAMESPACES["wdt"]["P906"], Literal(result["librisid"]["value"] )) )

        if "viafid" in result:
            g.add( (URIRef(wikidata_uri), NAMESPACES["wdt"]["P214"], Literal(result["viafid"]["value"] )) )





def uri_for_post(post_id):
    """Make a URIRef for a wp post.
    """
    return URIRef("http://oldnews.peterkrantz.se/data/poit.rdf#" + str(post_id))


def jsonld_for_post(post):
    logger.info(f"Working on post -------> {post['id']}")
    wdids = parse_identifiers(post["content"]["rendered"])

    itemuri = uri_for_post(post["id"])
    # Basic page data
    g.add((itemuri, RDF.type , NAMESPACES["schema"]["NewsArticle"]))
    g.add((itemuri, NAMESPACES["schema"]["isPartOf"], URIRef("http://libris.kb.se/resource/bib/2979645")))
    g.add((itemuri, NAMESPACES["schema"]["url"],Literal(post["link"])))
    g.add((itemuri, NAMESPACES["schema"]["datePublished"], Literal(post["date"],datatype=XSD.date)))
    g.add((itemuri, NAMESPACES["dcterms"]["title"], Literal(post["title"]["rendered"] , lang="sv")))
    g.add((itemuri, NAMESPACES["dcterms"]["identifier"], Literal(post["id"],datatype=XSD.integer)))

    for item in wdids:
        g.add((itemuri, NAMESPACES["schema"]["about"], URIRef(item)))
        get_basics_for_wduri(item)

    return g


def write_unknowns():
    with open("./data/unknown_persons.csv", "w", encoding='utf-8') as f:
        writer = csv.writer(f, dialect=csv.excel)
        for row in sorted(unknown_persons, key=lambda tup: tup[0]):
            writer.writerow(row)

    with open("./data/unknown_places.csv", "w", encoding='utf-8') as f:
        writer = csv.writer(f, dialect=csv.excel)
        for row in sorted(unknown_places, key=lambda tup: tup[0]):
            writer.writerow(row)



def write_link_labels():
    with open("./data/link_labels.csv", "w", encoding='utf-8') as f:
        writer = csv.writer(f, dialect=csv.excel)
        for row in sorted(link_labels, key=lambda tup: tup[0]):
            writer.writerow(row)


def parse_data(url):
    logger.info(f"Working on {url}")
    r = requests.get(url)
    jsondata = r.json()
    for post in jsondata:
        jsonld_for_post(post)
        parse_unknown_items(post["content"]["rendered"], post["link"], post["id"])

    if "Link" in r.headers:
        logger.info(f"Header: {r.headers['Link']}")
        links = requests.utils.parse_header_links(r.headers["Link"])
        for link in links:
            if "next" in link["rel"]:
                url = link["url"]
                parse_data(url)


g = Graph()

for prefix in NAMESPACES:
    g.bind(prefix, NAMESPACES[prefix])

url = 'http://oldnews.peterkrantz.se/wp-json/wp/v2/posts?per_page=100'
parse_data(url)

# Dump RDF
g.serialize(destination='./data/poit.rdf', format='xml', indent=4, encoding="utf-8")

# Dump CSVs
write_unknowns()
write_link_labels()
