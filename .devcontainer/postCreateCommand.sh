#!/bin/bash

# Load infra-schema + infra-topology
poetry run inv load-schema

# Wait a bit extra to be sure the schema are properly loaded
sleep 30

# Load infra-data
poetry run inv load-data
