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



NAMESPACES = {	
   'schema' : Namespace('http://schema.org/'),
   'dcterms' : Namespace('http://purl.org/dc/terms/')
}

#Find unknown places (linked with https://www.wikidata.org/wiki/Q2221906 )
unknown_places = []
unknown_persons = []
link_labels = []

def parse_identifiers(htmltext):
    """Parse wikidata identifiers from Wikipedia links in text.

    :htmltext: html text
    :returns: list of wikidata identifiers

    """
    tree = html.fromstring(htmltext)
    links = tree.xpath("//a[@href]")
    wikipedialinks = []

    for link in links:
        href = link.attrib["href"]
        if "wikipedia.org" in href:
            wikipedialinks.append(href)
            link_labels.append((href, link.text_content().strip()))

    titles = page_titles_from_links(wikipedialinks)
    return wikidata_from_wp(titles)


def parse_unknown_items(htmltext, url):
    tree = html.fromstring(htmltext)
    links = tree.xpath("//a[@href]")

    for link in links:
        href = link.attrib["href"]
        if href=="https://www.wikidata.org/wiki/Q2221906":
            unknown_places.append((link.text_content(), url))
        if href=="https://sv.wikipedia.org/wiki/N.N.":
            unknown_persons.append((link.text_content(), url))


def page_titles_from_links(wp_links):
    """Return a list of page titles parsed from wikipedia page links
    """
    titles = {}
    for link in wp_links:
        lang = link[8:10]
        if not lang in titles:
            titles[lang] = []
        title = link.split("/")[-1]
        titles[lang].append(title)

    return titles



def wikidata_from_wp(titles):
    """Lookup Wikidata IDs from a list of page titles
    """

    wikidata_uris = []

    for lang in titles:
        title_param = "|".join(titles[lang])

        q = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=pageprops&format=json&titles={title_param}"
        print(q)
        r = requests.get(q)
        jd = r.json()

        for key, value in jd["query"]["pages"].items():
            wdq = value["pageprops"]["wikibase_item"]
            if wdq:
                wikidata_uris.append("http://www.wikidata.org/entity/" + wdq)

    return wikidata_uris


def get_basics_for_wduri(wikidata_uri):
    print(wikidata_uri)
    md5 = hashlib.md5()
    md5.update(wikidata_uri.encode('utf-8'))
    filename = os.path.join("wdcache", md5.hexdigest())
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    queryres = None
    if os.path.isfile(filename):
        with open(filename, 'rb') as cachehandle:
           print("using cached result from '%s'" % filename)
           queryres = pickle.load(cachehandle)
    else:
        # gör till construct senare

        sparql.setReturnFormat(JSON)

        sq = f'''
        PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
        PREFIX wdt: <http://www.wikidata.org/prop/direct/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>        
        PREFIX wikibase: <http://wikiba.se/ontology#>
        PREFIX bd: <http://www.bigdata.com/rdf#>
        
        SELECT ?itemLabel ?lat ?lon ?country ?countryLabel
        WHERE
        {{ 
            OPTIONAL {{
            <{wikidata_uri}> p:P625 ?coords .
                ?coords ps:P625 ?coord.
                ?coords psv:P625 ?coordinate_node.  
            ?coordinate_node wikibase:geoLatitude ?lat .
            ?coordinate_node wikibase:geoLongitude ?lon .
            <{wikidata_uri}> wdt:P17 ?country .
            }}

              SERVICE wikibase:label {{ 
              bd:serviceParam wikibase:language "sv,en" .
              <{wikidata_uri}> rdfs:label ?itemLabel .
              ?country rdfs:label ?countryLabel .
            }}
        }}
        LIMIT 1
        '''

        sparql.setQuery(sq)
        queryres = sparql.query().convert()

        if not os.path.exists("./wdcache"):
            os.makedirs("./wdcache")

        with open(filename, 'wb') as cachehandle:
            pickle.dump(queryres, cachehandle)

    for result in queryres["results"]["bindings"]:
        if "itemLabel" in result:
            print(result["itemLabel"]["value"])
            g.add((URIRef(wikidata_uri), RDFS.label, Literal(result["itemLabel"]["value"])))
        if "lat" in result:
            geo = BNode()
            g.add((geo, RDF.type, NAMESPACES["schema"]["GeoCoordinates"] ))
            g.add((geo, NAMESPACES["schema"]["latitude"], Literal(result["lat"]["value"]) ))
            g.add((geo, NAMESPACES["schema"]["longitude"], Literal(result["lon"]["value"]) ))
            g.add((URIRef(wikidata_uri), NAMESPACES["schema"]["geo"], geo))


def jsonld_for_post(post):
    wdids = parse_identifiers(post["content"]["rendered"])


    itemuri = URIRef("http://oldnews.peterkrantz.se/data/index.rdf#" + post["date"])
    # Basic page data
    g.add((itemuri, RDF.type , NAMESPACES["schema"]["NewsArticle"]))
    g.add((itemuri, NAMESPACES["schema"]["isPartOf"], URIRef("http://libris.kb.se/resource/bib/2979645")))
    g.add((itemuri, NAMESPACES["schema"]["url"],Literal(post["link"])))
    g.add((itemuri, NAMESPACES["schema"]["datePublished"], Literal(post["date"],datatype=XSD.date)))
    g.add((itemuri, NAMESPACES["dcterms"]["title"], Literal(post["title"]["rendered"] , lang="sv")))

    for item in wdids:
        g.add((itemuri, NAMESPACES["schema"]["about"], URIRef(item)))
        get_basics_for_wduri(item)

    return g


def write_unknowns():
    with open("./data/unknown_persons.csv", "w") as f:
        writer = csv.writer(f)
        for row in unknown_persons:
            writer.writerow(row)

    with open("./data/unknown_places.csv", "w") as f:
        writer = csv.writer(f)
        for row in unknown_places:
            writer.writerow(row)



def write_link_labels():
    with open("./data/link_labels.csv", "w") as f:
        writer = csv.writer(f)
        for row in link_labels:
            writer.writerow(row)


def parse_data(url):
    print(f"Working on {url}")
    r = requests.get(url)
    jsondata = r.json()
    for post in jsondata:
        jsonld_for_post(post)
        parse_unknown_items(post["content"]["rendered"], post["link"])

    if "Link" in r.headers:
        if 'rel="next"' in r.headers["Link"]:
            url = r.headers["Link"].split(";")[0][1:-1]
            parse_data(url)


g = Graph()

url = 'http://oldnews.peterkrantz.se/wp-json/wp/v2/posts?per_page=100'
parse_data(url)

# Dump RDF
g.serialize(destination='./data/index.rdf', format='xml', indent=4, encoding="utf-8")

# Dump CSVs
write_unknowns()
write_link_labels()
