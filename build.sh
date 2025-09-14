#!/usr/bin/env bash
pip install --upgrade pip  # Update pip to avoid warnings
pip install -r requirements.txt
mkdir -p ephe
curl -L -o ephe/sepl_18.se1 ftp://ftp.astro.com/pub/swisseph/ephe/sepl_18.se1
curl -L -o ephe/semo_18.se1 ftp://ftp.astro.com/pub/swisseph/ephe/semo_18.se1
curl -L -o ephe/seas_18.se1 ftp://ftp.astro.com/pub/swisseph/ephe/seas_18.se1