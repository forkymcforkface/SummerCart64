#!/bin/sh
# Actual-controller simulation; every generated artifact uses the explicit build directory.
set -eu
test "$#" -eq 2 || { echo "usage: $0 ORIGINAL.gif BUILD_DIRECTORY" >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
rtl_dir=$(CDPATH= cd -- "$source_dir/../../../fw/rtl" && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$source_dir/../compositor/fixtures.py" "$1" "$2"
output_dir=$(CDPATH= cd -- "$2" && pwd)
verilator --cc --exe --build -j 4 --top-module gif_sc64_pipeline --Mdir "$output_dir/obj" \
  "$rtl_dir/memory/mem_bus.sv" "$rtl_dir/n64/n64_scb.sv" \
  "$rtl_dir/memory/memory_arbiter.sv" "$rtl_dir/memory/memory_sdram.sv" \
  "$source_dir/../sc64-bus/gif_sc64_bus.sv" \
  "$source_dir/../cached/gif_lzw_cached.sv" "$source_dir/../cached/cached_dictionary.sv" \
  "$source_dir/../compositor/gif_ci8_compose.sv" "$source_dir/gif_sc64_pipeline.sv" \
  "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vgif_sc64_pipeline" "$output_dir/fixtures.bin" "$output_dir" > "$output_dir/results.log"
cat "$output_dir/results.log"
