#!/bin/sh
cd `dirname $0`
. ./venv/bin/activate
screen python3 ./main.py
