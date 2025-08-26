import spacy
from abi import logger

nlp = spacy.load("en_core_web_sm")

def extract_entities(text):
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        entities.append({
            'text': ent.text,
            'label': ent.label_,
            'start': ent.start_char,
            'end': ent.end_char
        })
    return entities

# Test cases
texts = [
    "The color of the shoes of Tom is red",
    "Give me the professional phone number of John Doe",
    "Give me the professional phone number of",
    "I am working at Naas.ai"
]

for text in texts:
    logger.info(f"Text: {text}")
    entities = extract_entities(text)
    logger.info(f"Entities found: {len(entities)}")
    for entity in entities:
        logger.info(f"- {entity['text']} ({entity['label']})")

# Spacy is good at extracting person names as entities, but has limitations with organization names
# As shown in the test results below:
# - It successfully detects "Tom" and "John Doe" as PERSON entities
# - It fails to detect "Naas.ai" as an organization, returning 0 entities
# - Empty queries like "Give me the professional phone number of" return 0 entities as expected
#
# Results:
# Text: "The color of the shoes of Tom is red" -> Found: "Tom (PERSON)"
# Text: "Give me the professional phone number of John Doe" -> Found: "John Doe (PERSON)" 
# Text: "Give me the professional phone number of" -> Found: No entities
# Text: "I am working at Naas.ai" -> Found: No entities (fails to detect organization)
