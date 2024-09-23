#!/bin/bash

poetry config virtualenvs.create true
poetry install --no-interaction --no-ansi

# Install Arista Collection
poetry run ansible-galaxy install -r ansible-requirements.yml

poetry run invoke start
