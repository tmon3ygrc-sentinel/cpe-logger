#!/usr/bin/env python3
import sys, json, yaml
from jsonschema import validate, ValidationError

def load_file(path):
    with open(path, 'r') as f:
        if path.endswith(('.yaml', '.yml')):
            return yaml.safe_load(f)
        return json.load(f)

if len(sys.argv) != 3:
    print("Usage: python scripts/validate.py <schema_path> <document_path>")
    sys.exit(1)

schema_path, document_path = sys.argv[1], sys.argv[2]

try:
    schema = load_file(schema_path)
    document = load_file(document_path)
    validate(instance=document, schema=schema)
    print("✅ Document is valid against the schema.")
except ValidationError as e:
    print(f"❌ Validation error: {e.message}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
