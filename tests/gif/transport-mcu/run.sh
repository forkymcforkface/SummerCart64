#!/bin/sh
# Isolated stock-MCU memory owner test; all generated artifacts stay outside tests.
set -eu
test "$#" -eq 1
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 -B "$here/generate.py" "$1"
out=$(CDPATH= cd -- "$1" && pwd)
verilator --cc --exe --build -j 4 --top-module top --Mdir "$out/obj" \
 "$here/../../../fw/rtl/memory/mem_bus.sv" "$out/gif_transport_mcu_mux.sv" \
 "$out/stock_memory_slice.sv" "$here/top.sv" "$here/driver.cpp" > "$out/compile.log" 2>&1
"$out/obj/Vtop" > "$out/results.log"
cat "$out/results.log"
python3 -B "$here/synth.py" "$out"
python3 -B "$here/negative.py" "$out"
