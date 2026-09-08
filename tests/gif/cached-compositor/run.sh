#!/bin/sh
# Experimental shared-service simulation; all generated outputs use the explicit build directory.
set -eu
test "$#" -eq 2 || { echo "usage: $0 ORIGINAL.gif BUILD_DIRECTORY" >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$source_dir/../compositor/fixtures.py" "$1" "$2"
output_dir=$(CDPATH= cd -- "$2" && pwd)
verilator --cc --exe --build -j 4 --top-module gif_cached_pipeline --Mdir "$output_dir/obj" \
  "$source_dir/gif_cached_pipeline.sv" "$source_dir/../compositor/gif_ci8_compose.sv" \
  "$source_dir/../cached/gif_lzw_cached.sv" "$source_dir/../cached/cached_dictionary.sv" \
  "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vgif_cached_pipeline" "$output_dir/fixtures.bin" "$output_dir" 0 > "$output_dir/faults.log"
"$output_dir/obj/Vgif_cached_pipeline" "$output_dir/fixtures.bin" "$output_dir" > "$output_dir/results.log"
cat "$output_dir/faults.log" "$output_dir/results.log"
