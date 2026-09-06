#!/usr/bin/env python3
"""Add an explicitly untimed EFB routing diagnostic, with a bitstream barrier.

Trellis supplies the hard EFB BEL and interconnect. Its database does not supply
SC64's EFB/UFM configuration or timing, so normal builds and bitstream emission
remain errors. The diagnostic setting is deliberately unsuitable for firmware.
"""

from pathlib import Path
import sys


root = Path(sys.argv[1]) / "machxo2"
changes = {
    "pack.cc": (
        "    void pack_misc()\n    {\n",
        """    void pack_misc()
    {
        for (auto &cell : ctx->cells) {
            CellInfo *ci = cell.second.get();
            if (ci->type != id_EFB)
                continue;
            if (!ctx->setting<bool>("arch.sc64_efb_route_only", false))
                log_error("EFB configuration and timing are unqualified; firmware builds are disabled.\\n");
            log_warning("EFB routing diagnostic: no EFB timing or configuration qualification.\\n");
        }
"""),
    "arch.cc": (
        "    clockInfoCount = 0;\n    if (cell->type == id_TRELLIS_COMB)",
        """    clockInfoCount = 0;
    if (cell->type == id_EFB) {
        if (!getCtx()->setting<bool>("arch.sc64_efb_route_only"))
            log_error("EFB timing is unqualified; firmware builds are disabled.\\n");
        return cell->ports.at(port).type == PORT_OUT ? TMG_STARTPOINT : TMG_ENDPOINT;
    }
    if (cell->type == id_TRELLIS_COMB)"""),
    "bitstream.cc": (
        "    MachXO2Bitgen bitgen(ctx);",
        """    for (auto &cell : ctx->cells)
        if (cell.second->type == id_EFB)
            log_error("EFB/UFM configuration bits are unmapped; bitstream emission is disabled.\\n");
    MachXO2Bitgen bitgen(ctx);"""),
}
updated = {}
for name, (before, after) in changes.items():
    path = root / name
    text = path.read_text()
    if text.count(before) != 1:
        raise SystemExit(f"unexpected source at {path}; refusing partial patch")
    updated[path] = text.replace(before, after)
path = root / "main.cc"
text = path.read_text()
main_changes = [
    ('    specific.add_options()("device", po::value<std::string>(), "device name");',
     '    specific.add_options()("efb-routing-diagnostic", "untimed EFB routing only; no bitstream");\n'
     '    specific.add_options()("device", po::value<std::string>(), "device name");'),
    ('void MachXO2CommandHandler::customAfterLoad(Context *ctx)\n{',
     'void MachXO2CommandHandler::customAfterLoad(Context *ctx)\n{\n'
     '    ctx->settings[ctx->id("arch.sc64_efb_route_only")] = int(vm.count("efb-routing-diagnostic") != 0);'),
    ('    write_bitstream(ctx, textcfg);',
     '    if (vm.count("efb-routing-diagnostic") && textcfg.empty()) {\n'
     '        for (auto &cell : ctx->cells)\n'
     '            if (cell.second->type == id_EFB)\n'
     '                return;\n'
     '    }\n'
     '    write_bitstream(ctx, textcfg);'),
]
for before, after in main_changes:
    if text.count(before) != 1:
        raise SystemExit(f"unexpected source at {path}; refusing partial patch")
    text = text.replace(before, after)
updated[path] = text
for path, text in updated.items():
    path.write_text(text)
