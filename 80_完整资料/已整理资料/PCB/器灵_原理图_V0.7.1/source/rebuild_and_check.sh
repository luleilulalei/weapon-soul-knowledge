#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export HOME="${SPIRIT_KICAD_HOME:-/tmp/spirit-kicad-home}"
mkdir -p "$HOME" validation
python3 source/generate_v071.py
kicad-cli sch export netlist --format kicadxml -o validation/Spirit.xml project/Spirit.kicad_sch
kicad-cli sch erc --format json -o validation/erc.json project/Spirit.kicad_sch
python3 source/verify_v071.py
kicad-cli sch export pdf -o Spirit_V0.7.1_review.pdf project/Spirit.kicad_sch
