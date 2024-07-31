#!/usr/bin/env python

import sys
import json
import yaml
from jsonschema import validate, ValidationError

if len(sys.argv) != 3:
    print("Usage: python validate_jsonschema_yaml.py <schemafile> <datafile>") 
    sys.exit(1)

schema_file = sys.argv[1]
data_file = sys.argv[2]

# Load JSON schema
with open(schema_file) as f:
    schema = json.load(f)

# Load YAML data 
with open(data_file) as f:
    data = yaml.safe_load(f)

# Validate
try:
    validate(instance=data, schema=schema)
except ValidationError as e:
    print(e)
    sys.exit(1)

print("YAML data is valid")
sys.exit(0)
