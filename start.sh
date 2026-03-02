#!/bin/sh
cd "$(dirname "${BASH_SOURCE[0]:-$0}")"
uv sync --upgrade
screen uv run main.py 