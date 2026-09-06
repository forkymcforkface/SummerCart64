#!/bin/sh
# Runtime exact payload comparison against original GIF stimuli.
set -eu
[ "$#" -eq 2 ] || { echo "usage: $0 ORIGINAL.gif BUILD_DIRECTORY" >&2; exit 2; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
python3 "$source_dir/fixtures.py" "$1" "$2"
output_dir=$(CDPATH= cd -- "$2" && pwd)
verilator --cc --exe --build -j 4 --top-module reuse_test --Mdir "$output_dir/obj" \
 "$source_dir/../../../fw/rtl/memory/mem_bus.sv" "$source_dir/gif_payload_reuse.sv" \
 "$source_dir/reuse_test.sv" "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vreuse_test" "$output_dir/payloads.bin" > "$output_dir/results.log"
cat "$output_dir/results.log"
