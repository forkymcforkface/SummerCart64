#!/bin/sh
# Standalone adapter regression; no physical memory or firmware changes.
set -eu
[ "$#" -eq 1 ] || { echo "usage: $0 BUILD_DIRECTORY" >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
output_dir=$(python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]).resolve(); s=pathlib.Path(sys.argv[2]).resolve(); assert p != s and s not in p.parents; print(p)' "$1" "$source_dir/..")
mkdir -p "$output_dir"
verilator --cc --exe --build -j 4 --top-module bus_test --Mdir "$output_dir/obj" \
 "$source_dir/../../../fw/rtl/memory/mem_bus.sv" "$source_dir/gif_sc64_bus.sv" \
 "$source_dir/bus_test.sv" "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vbus_test" > "$output_dir/results.log"
cat "$output_dir/results.log"
