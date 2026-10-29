#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT
c++ -std=c++17 -pthread -Wall -Wextra -Werror -Isrc -Itests/privacy_stubs src/app/spirit_privacy.cc tests/test_privacy.cc -o "$OUT/test_privacy"
"$OUT/test_privacy"
