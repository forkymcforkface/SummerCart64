"""Apply the bounded FIFO diagnostic patch to an isolated pinned nextpnr tree."""
from pathlib import Path
import sys

root = Path(sys.argv[1]) / 'machxo2'
pending = {}

def replace(name, old, new):
    path = root / name
    text = pending[path] if path in pending else path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f'{name}: patch anchor is not unique')
    pending[path] = text.replace(old, new)

replace('main.cc', '    specific.add_options()("disable-router-lutperm",',
'''    specific.add_options()("fifo-routing-diagnostic", "route FIFO8KB without characterized FIFO timing; not hardware-qualified");
    specific.add_options()("disable-router-lutperm",''')
replace('main.cc', '    if (vm.count("disable-router-lutperm"))',
'''    if (vm.count("fifo-routing-diagnostic"))
        ctx->settings[ctx->id("fifo.routing_diagnostic")] = 1;
    if (vm.count("disable-router-lutperm"))''')
replace('main.cc', 'void MachXO2CommandHandler::customAfterLoad(Context *ctx)\n{',
'''void MachXO2CommandHandler::customAfterLoad(Context *ctx)
{
    ctx->settings[ctx->id("fifo.routing_diagnostic")] = vm.count("fifo-routing-diagnostic") ? 1 : 0;''')
replace('pack.cc', '            // Convert 18-bit PDP RAMs to regular 9-bit DP ones that match the Bel',
'''            if (ci->type == id_FIFO8KB) {
                if (!ctx->setting<bool>("fifo.routing_diagnostic", false))
                    log_error("FIFO8KB timing is not characterized; --fifo-routing-diagnostic permits unqualified routing only\\n");
                if (int_or_default(ci->params, id_DATA_WIDTH_W, 18) != 9 ||
                    int_or_default(ci->params, id_DATA_WIDTH_R, 18) != 9 ||
                    str_or_default(ci->params, id_REGMODE, "NOREG") != "NOREG")
                    log_error("FIFO8KB diagnostic supports only SC64 9-bit/NOREG mode\\n");
                log_warning("FIFO8KB %s: diagnostic physical mapping; no FIFO timing qualification\\n", ci->name.c_str(ctx));
                ci->attrs[ctx->id("FIFO8KB_MODE")] = 1;
                rename_bus(ci, "DI", "DIA", 9, 0, 0);
                rename_bus(ci, "DI", "DIB", 9, 9, 0);
                rename_bus(ci, "DO", "DOB", 9, 0, 0);
                rename_bus(ci, "DO", "DOA", 9, 9, 0);
                rename_bus(ci, "CSW", "CSA", 2, 0, 0);
                rename_bus(ci, "CSR", "CSB", 2, 0, 0);
                for (auto pair : {std::make_pair("CLKW", "CLKA"), {"CLKR", "CLKB"},
                                  {"WE", "CEA"}, {"RE", "CEB"}, {"ORE", "OCEB"},
                                  {"RST", "RSTA"}, {"RPRST", "RSTB"},
                                  {"FULLI", "CSA2"}, {"EMPTYI", "CSB2"},
                                  {"AEF", "AE"}, {"AFF", "AF"}})
                    ci->renamePort(ctx->id(pair.first), ctx->id(pair.second));
                ci->params[id_DATA_WIDTH_A] = 9;
                ci->params[id_DATA_WIDTH_B] = 9;
                ci->type = id_DP8KC;
            }
            // Convert 18-bit PDP RAMs to regular 9-bit DP ones that match the Bel''')
replace('arch.cc', '''    } else if (cell->type == id_DP8KC) {
        if (port.in(id_CLKA, id_CLKB))''',
'''    } else if (cell->type == id_DP8KC) {
        if (bool_or_default(cell->attrs, id("FIFO8KB_MODE"), false)) {
            if (!bool_or_default(settings, id("fifo.routing_diagnostic"), false))
                log_error("FIFO8KB timing requires fresh --fifo-routing-diagnostic opt-in\\n");
            if (port.in(id_CLKA, id_CLKB))
                return TMG_CLOCK_INPUT;
            return cell->ports.at(port).type == PORT_OUT ? TMG_STARTPOINT : TMG_ENDPOINT;
        }
        if (port.in(id_CLKA, id_CLKB))''')
replace('bitstream.cc', '    void write_bram(CellInfo *ci)\n    {',
'''    void write_fifo(CellInfo *ci)
    {
        if (!bool_or_default(ctx->settings, ctx->id("fifo.routing_diagnostic"), false))
            log_error("FIFO8KB configuration requires fresh --fifo-routing-diagnostic opt-in\\n");
        TileGroup tg;
        tg.tiles = get_bram_tiles(ci->bel);
        tg.config.add_enum("EBR.MODE", "FIFO8KB");
        tg.config.add_enum("EBR.FIFO8KB.DATA_WIDTH_W", "9");
        tg.config.add_enum("EBR.FIFO8KB.DATA_WIDTH_R", "9");
        tg.config.add_enum("EBR.REGMODE_A", "NOREG");
        tg.config.add_enum("EBR.REGMODE_B", "NOREG");
        for (auto name : {"RESETMODE", "ASYNC_RESET_RELEASE", "GSR"})
            tg.config.add_enum(std::string("EBR.") + name,
                               str_or_default(ci->params, ctx->id(name), name == std::string("GSR") ? "DISABLED" : "SYNC"));
        tg.config.add_enum("EBR.FIFO8KB.FULLIMUX", "FULLI");
        tg.config.add_enum("EBR.FIFO8KB.EMPTYIMUX", "EMPTYI");
        for (auto name : {"CLKAMUX", "CLKBMUX", "CEAMUX", "CEBMUX", "OCEBMUX", "RSTAMUX", "RSTBMUX"}) {
            std::string sig(name);
            tg.config.add_enum("EBR." + sig, str_or_default(ci->params, ctx->id(name), sig.substr(0, sig.size() - 3)));
        }
        for (auto name : {"AEPOINTER", "AEPOINTER1", "AFPOINTER", "AFPOINTER1", "FULLPOINTER", "FULLPOINTER1"}) {
            auto value = str_or_default(ci->params, ctx->id(name), "");
            if (value.size() != 16 || value.substr(0, 2) != "0b" || value.find_first_not_of("01", 2) != std::string::npos)
                log_error("FIFO8KB %s requires explicit 14-bit %s\\n", ci->name.c_str(ctx), name);
            tg.config.add_word(std::string("EBR.FIFO8KB.") + name, str_to_bitvector(value, 14));
        }
        for (auto side : {"W", "R"}) {
            std::string name = std::string("CSDECODE_") + side;
            auto value = str_or_default(ci->params, ctx->id(name), "");
            if (value.size() != 4 || value.substr(0, 2) != "0b" || value.find_first_not_of("01", 2) != std::string::npos)
                log_error("FIFO8KB %s requires explicit 2-bit %s\\n", ci->name.c_str(ctx), name.c_str());
            auto bits = str_to_bitvector(value, 2);
            std::reverse(bits.begin(), bits.end());
            tg.config.add_word("EBR.FIFO8KB." + name, bits);
        }
        tg.config.add_word("EBR.WID", int_to_bitvector(int_or_default(ci->attrs, id_WID, 0), 9));
        cc.tilegroups.push_back(tg);
    }

    void write_bram(CellInfo *ci)
    {
        if (bool_or_default(ci->attrs, ctx->id("FIFO8KB_MODE"), false)) {
            write_fifo(ci);
            return;
        }''')
for path, text in pending.items():
    path.write_text(text)
print('Applied isolated FIFO routing/configuration diagnostic; default remains fail-closed')
