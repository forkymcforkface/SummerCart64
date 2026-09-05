#!/bin/sh
# Compare the external-dictionary variant against unchanged original GIF bytes.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 ORIGINAL.gif BUILD_DIRECTORY" >&2
    exit 2
fi
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$2"
output_dir=$(CDPATH= cd -- "$2" && pwd)
python3 "$source_dir/../fixtures.py" "$1" "$output_dir"
verilator --version > "$output_dir/tool-versions.txt"
verilator --cc --exe --build -j 4 --top-module gif_lzw_cached --Mdir "$output_dir/obj" "$source_dir/gif_lzw_cached.sv" "$source_dir/cached_dictionary.sv" "$source_dir/driver.cpp" > "$output_dir/compile.log" 2>&1
"$output_dir/obj/Vgif_lzw_cached" "$output_dir/fixtures.bin" > "$output_dir/results.log"
if command -v yosys >/dev/null 2>&1; then
    yosys -V >> "$output_dir/tool-versions.txt"
    yosys -Q -T -p "read_verilog -sv \"$source_dir/gif_lzw_cached.sv\" \"$source_dir/cached_dictionary.sv\"; synth_lattice -family xo2 -top gif_lzw_cached; stat; write_json \"$output_dir/synthesis-xo2.json\"" > "$output_dir/synthesis-xo2.log" 2>&1
fi
cat "$output_dir/results.log"
