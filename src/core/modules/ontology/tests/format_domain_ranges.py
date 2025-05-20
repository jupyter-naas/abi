import json
from abi import logger
import pydash as _
from pprint import pprint

file_path = "docs/ontology/reference/model/ontology.json"
operators = {"unionOf": "or", "intersectionOf": "and", "complementOf": "not"}
with open(file_path) as f:
    onto = json.load(f)

file_path_onto_classes = "docs/ontology/reference/model/onto_classes.json"
with open(file_path_onto_classes) as f:
    onto_classes = json.load(f)

file_path_onto_tuples = "docs/ontology/reference/model/onto_tuples.json"
with open(file_path_onto_tuples) as f:
    onto_tuples = json.load(f)


_onto_oprop = _.filter_(
    onto,
    lambda x: "http://www.w3.org/2002/07/owl#ObjectProperty" in x["type"]
    if "type" in x
    else None,
)
logger.info(f"🔍 Found {len(_onto_oprop)} object properties in the ontology.")


# get_first_rest is used to get the values from unionOf, intersectionOf and complementOf.
def get_first_rest(tpl):
    first = None
    rest = None
    for i in tpl:
        a, b = i

        if str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#first":
            first = str(b)

        if (
            str(a) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
            and str(b) != "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"
        ):
            rest = str(b)
    return first, rest


# get_linked_classes is a recursive function used for Object Properties ranges and domains.
# It will build a tree of classes based on the unionOf, intersectionOf and complementOf.
# It is usefull to understand what are the conditions for a class to be in the range or domain of an object property.
def get_linked_classes(cls_id, rel_type=None):
    # If it's a leaf we return a dict with the class id and the operator.
    if "http" in cls_id:
        if rel_type is not None and rel_type in operators:
            return {operators[rel_type]: [cls_id]}
        return [cls_id]

    # If it's a class, we want to go over the unionOf, intersectionOf and complementOf.
    if cls_id in onto_classes:
        cls = onto_classes[cls_id]
        res = (
            [get_linked_classes(e, "unionOf") for e in _.get(cls, "unionOf", [])]
            + [
                get_linked_classes(e, "intersectionOf")
                for e in _.get(cls, "intersectionOf", [])
            ]
            + [
                get_linked_classes(e, "complementOf")
                for e in _.get(cls, "complementOf", [])
            ]
        )
        print(res)
        return res
    else:
        # If it's not a class, then we will have a 'first' and a 'rest' to handle.
        first, rest = get_first_rest(onto_tuples[cls_id])
        print(first, rest)

        # We grab the operator based on the rel_type.
        operator = operators[rel_type]

        # We get the left/first value.
        left = get_linked_classes(first, rel_type)
        if rest:
            # We get the right/rest value.
            right = get_linked_classes(rest, rel_type)

            if operator in right and operator in left:
                if (
                    operator in right
                    and type(right[operator]) is dict
                    and operator in right[operator]
                    and type(right[operator][operator]) is list
                ):
                    right[operator] = right[operator][operator]

                return {operator: _.flatten([left[operator], right[operator]])}
            else:
                return {operator: _.flatten([left, right])}
        else:
            return {operator: left}


# We map the ranges and domains to the classes by calling get_linked_classes.
def map_ranges_domains(x):
    if "domain" in x:
        x["domain"] = _.map_(
            x["domain"], lambda x: x if "http" in x else get_linked_classes(x)[0]
        )
    if "range" in x:
        x["range"] = _.map_(
            x["range"], lambda x: x if "http" in x else get_linked_classes(x)[0]
        )
    return x


for oprop in _onto_oprop:
    if oprop["__id"] == "http://purl.obolibrary.org/obo/BFO_0000057":
        oprop = map_ranges_domains(oprop)
        if "domain" in oprop and "range" in oprop:
            pprint(oprop)
            break
