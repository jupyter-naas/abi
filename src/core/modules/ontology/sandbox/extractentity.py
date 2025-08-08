import spacy

nlp = spacy.load("en_core_web_sm")

text = "The color of the shoes of Tom is red"
doc = nlp(text)
print(doc)
print([ent.text.lower() for ent in doc.ents])


test = "Give me the professional phone number of John Doe"
doc = nlp(test)
print(doc)
print([ent.text.lower() for ent in doc.ents])

test = "Give me the professional phone number of"
doc = nlp(test)
print(doc)
print([ent.text.lower() for ent in doc.ents])


text = "I am working at Naas.ai"
doc = nlp(text)
print(doc)
print([ent.text.lower() for ent in doc.ents])