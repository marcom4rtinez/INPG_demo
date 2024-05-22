#!/bin/bash

# Load infra-schema + infra-topology
poetry run infrahubctl schema load models/*.yml

# Wait a bit extra to be sure the schema are properly loaded
sleep 30

# Load infra-data
./scripts/create_demo_data.sh
