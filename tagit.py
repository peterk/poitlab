import csv
import sys
import re
from noaho import NoAho
import coloredlogs, logging

logger = logging.getLogger("poitlab")
coloredlogs.install(level='DEBUG')

# This script:
# 1. reads links and labels form the ./data/link_labels.csv file
# 2. creates a trie for Aho-Corasick string matching
# 3. finds non-overlapping matches by length first
# 4. replace matches in a text file with links and writes the result to an output file in
# quasi-html format.

# Skip these generic words
skipwords = ["frantzösiske", "landet", "staden", "kongen", "konungen", "general", "sundet", "printzen", "öfwersten", "slottet", "keysaren"]

# Valid word boundaries
word_boundaries = ".\n\r\t /:"

trie = NoAho()
text = ""

def make_trie():
    pattern_list = []
    with open('./data/link_labels.csv') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not row["link"] in pattern_list and "https://sv.wikipedia.org/wiki/N.N." not in row["link"] and not row['label'].lower() in skipwords and len(row["label"]) > 3:
                pattern_list.append((row['label'], row['link']))
                #f.write(f"""s|{row['label']}|<a href="{row['link']}">{row['label']}</a>|\n""")

    if len(pattern_list) > 0:
        # sort by label length and make into dict
        pattern_list = sorted(pattern_list, key=lambda tup: len(tup[0]), reverse=True) 
        for pattern in pattern_list:
            trie[pattern[0]] = pattern[1]

        logger.info(f"{len(pattern_list)} patterns found for trie")



def debug_char(txt):
    for c in txt:
        print(c + "\t", end='')

    print()
    for c in txt:
        print(f"{ord(c)}\t", end='')
    print()



def filter_non_word_matches(matches):
    """Remove all matches not surrounded by word boundaries.
    """
    filtered = []
    for match in matches:
        logger.info(f"{match}")
        logger.info(f"{text[match[0]-1]} - {text[match[1]]}")
        if text[match[0]-1] in word_boundaries and text[match[1]] in word_boundaries:
            filtered.append(match)
        else:
            logger.warn(f"Skipping {match} {debug_char(text[match[0]-1:match[1]])}")
    logger.info(f"New matchcount: {len(list(filtered))}")
    return filtered



def replace_and_slice(matches):
    """Replace matches with their links and build new output.

    :matches: List of matching item string indices.
    :returns: Text with links.
    """
    outtext = ""
    matches = list(matches)
    matchcount = len(matches)
    valid_matchcount = 0


    for i in range(matchcount):
        match = matches[i]

        startpos = 0
        if i > 0:
            startpos = matches[i-1][1]
        
        logger.info(f"Startpos: {startpos}")

        start = match[0]
        end = match[1]
        link = match[2]
        
        outtext += text[startpos:start]
        outtext += f"""<a href="{link}">"""
        outtext += text[start:end]
        outtext += "</a>"

        logger.info(f"Added from match: {text[start-1:end+1]} {match}")
        valid_matchcount +=1

    # add remainder of text (from last match end until end of file)
    outtext += text[matches[-1][1]:-1]

    logger.info(f"Matches applied: {valid_matchcount}")
    return outtext



# Read input file
with open(sys.argv[1]) as textfile:
    text = textfile.read()

# Make the aho corasick trie
make_trie()

matches = filter_non_word_matches(trie.findall_long(text) )

with open(sys.argv[2], "w") as outputfile:
    outputfile.write(replace_and_slice( matches ))

logger.info(f"Wrote outfile: {sys.argv[2]}")


