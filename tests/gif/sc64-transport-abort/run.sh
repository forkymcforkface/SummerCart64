#!/bin/sh
# Cancellation research; all generated fixtures, sources and logs use an explicit build directory.
set -eu
test "$#" -eq 2 || { echo "usage: $0 ORIGINAL.gif BUILD_DIRECTORY" >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
rtl_dir=$(CDPATH= cd -- "$source_dir/../../../fw/rtl" && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$source_dir/../compositor/fixtures.py" "$1" "$2"
output_dir=$(CDPATH= cd -- "$2" && pwd)
build_driver() {
    verilator --cc --exe --build -j 4 --top-module gif_transport_abort_pipeline --Mdir "$1" \
      "$rtl_dir/memory/mem_bus.sv" "$rtl_dir/memory/dma_scb.sv" "$rtl_dir/fifo/fifo_bus.sv" \
      "$rtl_dir/n64/n64_scb.sv" "$rtl_dir/memory/memory_dma.sv" \
      "$rtl_dir/memory/memory_arbiter.sv" "$rtl_dir/memory/memory_sdram.sv" \
      "$source_dir/../sc64-bus/gif_sc64_bus.sv" \
      "$source_dir/../cached/gif_lzw_cached.sv" "$source_dir/../cached/cached_dictionary.sv" \
      "$source_dir/../compositor/gif_ci8_compose.sv" \
      "$source_dir/gif_transport_mux.sv" "$source_dir/gif_transport_abort_pipeline.sv" "$2"
}
build_driver "$output_dir/obj" "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vgif_transport_abort_pipeline" "$output_dir/fixtures.bin" "$output_dir" > "$output_dir/results.log"
python3 -c 'from pathlib import Path; import sys; Path(sys.argv[2]).write_text(Path(sys.argv[1]).read_text().replace("Vgif_transport_pipeline", "Vgif_transport_abort_pipeline"))' \
  "$source_dir/../sc64-transport/driver.cpp" "$output_dir/normal.cpp"
build_driver "$output_dir/normal-obj" "$output_dir/normal.cpp" > "$output_dir/normal-compile.log" 2>&1
smoke_count=$(python3 -c 'import struct,sys; print(min(8,struct.unpack("<I",open(sys.argv[1],"rb").read(4))[0]))' "$output_dir/fixtures.bin")
"$output_dir/normal-obj/Vgif_transport_abort_pipeline" "$output_dir/fixtures.bin" "$output_dir" "$smoke_count" > "$output_dir/normal-results.log"
cat "$output_dir/results.log" "$output_dir/normal-results.log"
