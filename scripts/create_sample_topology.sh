#!/bin/bash
poetry run infrahubctl run generators/generate_topology.py topology=fra05-pod1
poetry run infrahubctl run generators/generate_topology.py topology=de1-pod1
poetry run infrahubctl run generators/generate_topology.py topology=de2-pod1

