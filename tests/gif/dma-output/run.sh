#!/bin/sh
# Existing DMA reuse probe; source packets and build outputs remain outside source.
set -eu
test "$#" -ge 2 || { echo "usage: $0 BUILD_DIRECTORY RTL_PACKET..." >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
rtl_dir="$source_dir/../../../fw/rtl"
output_dir=$(python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]).resolve(); s=pathlib.Path(sys.argv[2]).resolve(); assert p != s and s not in p.parents, "build directory must be outside test sources"; print(p)' "$1" "$source_dir/..")
shift
mkdir -p "$output_dir"
output_dir=$(CDPATH= cd -- "$output_dir" && pwd)
verilator --cc --exe --build -j 4 --top-module dma_output --Mdir "$output_dir/obj" \
  "$rtl_dir/memory/mem_bus.sv" "$rtl_dir/memory/dma_scb.sv" \
  "$rtl_dir/fifo/fifo_bus.sv" "$rtl_dir/memory/memory_dma.sv" \
  "$source_dir/dma_output.sv" "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vdma_output" "$@" > "$output_dir/results.log"
cat "$output_dir/results.log"
