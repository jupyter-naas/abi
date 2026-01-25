import re


def to_pascal_case(text):
    return "".join(word.capitalize() for word in re.findall(r"[A-Za-z0-9]+", text))


def to_snake_case(text):
    return "_".join(word.lower() for word in re.findall(r"[A-Za-z0-9]+", text))


def to_kebab_case(text):
    return "-".join(word.lower() for word in re.findall(r"[A-Za-z0-9]+", text))
