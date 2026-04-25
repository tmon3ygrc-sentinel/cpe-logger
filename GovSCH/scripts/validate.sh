#!/usr/bin/env bash

# Simple JSON Schema validation script using AJV CLI

if [ "$#" -ne 2 ]; then
    echo "Usage: ./scripts/validate.sh <schema_path> <document_path>"
    exit 1
fi

SCHEMA=$1
DOCUMENT=$2

# Check if AJV is installed
if ! command -v ajv &> /dev/null; then
    echo "Error: AJV CLI is not installed."
    echo "Install it with: npm install -g ajv-cli"
    exit 1
fi

# Run validation
ajv validate -s "$SCHEMA" -d "$DOCUMENT"
