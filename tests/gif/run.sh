#!/bin/sh
# Build only the experimental decoder, with generated products outside sources.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 ORIGINAL.gif BUILD_DIRECTORY" >&2
    exit 2
fi
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$2"
output_dir=$(CDPATH= cd -- "$2" && pwd)
python3 "$source_dir/fixtures.py" "$1" "$output_dir"
verilator --version > "$output_dir/tool-versions.txt"
verilator --cc --exe --build -j 4 --top-module gif_lzw --Mdir "$output_dir/obj" "$source_dir/gif_lzw.sv" "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vgif_lzw" "$output_dir/fixtures.bin" > "$output_dir/results.log"
if command -v yosys >/dev/null 2>&1; then
    yosys -V >> "$output_dir/tool-versions.txt"
    yosys -Q -T -p "read_verilog -sv \"$source_dir/gif_lzw.sv\"; hierarchy -top gif_lzw; proc; opt; memory_collect; stat; write_json \"$output_dir/synthesis-generic.json\"" > "$output_dir/synthesis-generic.log" 2>&1
    yosys -Q -T -p "read_verilog -sv \"$source_dir/gif_lzw.sv\"; synth_lattice -family xo2 -top gif_lzw; stat; write_json \"$output_dir/synthesis-xo2.json\"" > "$output_dir/synthesis-xo2.log" 2>&1
fi
cat "$output_dir/results.log"
