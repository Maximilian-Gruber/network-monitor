#!/bin/bash
set -e

echo "=============================="
echo " Network Monitor Setup (Mac)"
echo "=============================="

docker compose run --rm -it setup
docker compose up -d --build

echo ""
echo "Dashboard running at:"
echo "http://localhost:8050"

open http://localhost:8050
