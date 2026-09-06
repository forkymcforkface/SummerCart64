#!/usr/bin/env python3
"""Apply fail-closed diagnostic ODDRXE packing/config support to pinned nextpnr."""
from pathlib import Path
import sys
root=Path(sys.argv[1])/'machxo2'
def edit(name,old,new):
    path=root/name
    text=path.read_text()
    assert text.count(old)==1,(name,text.count(old),old[:60])
    path.write_text(text.replace(old,new))
edit('main.cc','    specific.add_options()("disable-router-lutperm",',
     '    specific.add_options()("oddr-diagnostic", "allow untimed ODDRXE diagnostic routing; NOT hardware qualified");\n\n    specific.add_options()("disable-router-lutperm",')
edit('main.cc','    return ctx;','    if (vm.count("oddr-diagnostic"))\n        ctx->settings[ctx->id("arch.oddr_diagnostic")] = 1;\n    return ctx;')
pack=r'''
    /* MachXO2 timing data has no ODDRXE arcs. This path explicitly requires
       diagnostic opt-in rather than supplying invented zero-delay timing. */
    void pack_oddr()
    {
        for (auto &entry : ctx->cells) {
            CellInfo *ci = entry.second.get();
            if (ci->type != ctx->id("ODDRXE"))
                continue;
            if (!bool_or_default(ctx->settings, ctx->id("arch.oddr_diagnostic")))
                log_error("ODDRXE has no characterized MachXO2 timing model; --oddr-diagnostic is research only.\n");
            NetInfo *q = ci->getPort(id_Q);
            if (q == nullptr || q->users.entries() != 1)
                log_error("ODDRXE %s requires one exclusive output PIO.\n", ctx->nameOf(ci));
            auto user = *q->users.begin();
            CellInfo *pio = user.cell;
            if (pio->type != id_TRELLIS_IO || user.port != id_I || !pio->attrs.count(id_BEL))
                log_error("ODDRXE %s requires an explicitly pin-constrained output PIO.\n", ctx->nameOf(ci));
            BelId pb = ctx->getBelByNameStr(pio->attrs.at(id_BEL).as_string());
            Loc pl = ctx->getBelLocation(pb);
            BelId ib = ctx->getBelByLocation(Loc(pl.x, pl.y, pl.z + 4));
            if (ib == BelId() || !ctx->getBelType(ib).in(id_IOLOGIC, id_BIOLOGIC, id_BSIOLOGIC,
                                                       id_TIOLOGIC, id_TSIOLOGIC, id_RIOLOGIC))
                log_error("No ODDRXE-capable IOLOGIC beside %s.\n", ctx->nameOfBel(pb));
            log_warning("DIAGNOSTIC ONLY: ODDRXE %s at %s has uncharacterized timing.\n",
                        ctx->nameOf(ci), ctx->nameOfBel(ib));
            ci->type = ctx->getBelType(ib);
            ci->attrs[id_BEL] = ctx->getBelName(ib).str(ctx);
            ci->attrs[ctx->id("ODDR_DIAGNOSTIC")] = 1;
            ci->renamePort(id_D0, id_OPOS);
            ci->renamePort(id_D1, id_ONEG);
            ci->renamePort(ctx->id("SCLK"), id_CLK);
            ci->renamePort(id_RST, id_LSR);
            ci->renamePort(id_Q, id_IOLDO);
            pio->disconnectPort(id_I);
            if (!pio->ports.count(id_IOLDO))
                pio->addInput(id_IOLDO);
            pio->connectPort(id_IOLDO, q);
            pio->params[id_DATAMUX_ODDR] = std::string("IOLDO");
        }
    }

'''
edit('pack.cc','    // Create a feed in to the carry chain',pack+'    // Create a feed in to the carry chain')
edit('pack.cc','        pack_io();','        pack_io();\n        pack_oddr();')
edit('arch.cc','    } else if (cell->type == id_EHXPLLJ) {\n        return TMG_IGNORE;',
'''    } else if (cell->type.in(id_IOLOGIC, id_BIOLOGIC, id_BSIOLOGIC, id_TIOLOGIC, id_TSIOLOGIC, id_RIOLOGIC)) {
        if (!bool_or_default(settings, id("arch.oddr_diagnostic")) ||
            !cell->attrs.count(id("ODDR_DIAGNOSTIC")))
            log_error("Unqualified IOLOGIC timing requested.\\n");
        if (port == id_CLK)
            return TMG_CLOCK_INPUT;
        return cell->ports.at(port).type == PORT_OUT ? TMG_STARTPOINT : TMG_ENDPOINT;
    } else if (cell->type == id_EHXPLLJ) {
        return TMG_IGNORE;''')
edit('bitstream.cc','        std::string pic_tile = get_pic_tile(bel);',
'''        std::string pic_tile = get_pic_tile(bel);
        if (str_or_default(ci->params, id_DATAMUX_ODDR, "PADDO") == "IOLDO")
            cc.tiles[pic_tile].add_enum(pio + ".DATAMUX_ODDR", "IOLDO");''')
writer=r'''
    void write_oddr(CellInfo *ci)
    {
        if (!bool_or_default(ctx->settings, ctx->id("arch.oddr_diagnostic")) ||
            !ci->attrs.count(ctx->id("ODDR_DIAGNOSTIC")))
            log_error("Refusing unqualified IOLOGIC configuration.\n");
        Loc loc = ctx->getBelLocation(ci->bel);
        std::string prefix = std::string("IOLOGIC") + "ABCD"[loc.z - 4];
        std::string tile = get_pic_tile(ci->bel);
        cc.tiles[tile].add_enum(prefix + ".MODE", "IDDR_ODDR");
        cc.tiles[tile].add_enum(prefix + ".CLKOMUX", "CLK");
        cc.tiles[tile].add_enum(prefix + ".CLKIMUX", "0");
        cc.tiles[tile].add_enum(prefix + ".LSROMUX", "LSRMUX");
        cc.tiles[tile].add_enum(prefix + ".LSRIMUX", "0");
        cc.tiles[tile].add_enum(prefix + ".LSRMUX", "LSR");
        cc.tiles[tile].add_enum(prefix + ".GSR", str_or_default(ci->params, id_GSR, "ENABLED"));
    }

'''
edit('bitstream.cc','    void write_dcc(CellInfo *ci)',writer+'    void write_dcc(CellInfo *ci)')
edit('bitstream.cc','            } else if (ci->type == id_OSCH) {',
'''            } else if (ci->type.in(id_IOLOGIC, id_BIOLOGIC, id_BSIOLOGIC, id_TIOLOGIC, id_TSIOLOGIC, id_RIOLOGIC)) {
                write_oddr(ci);
            } else if (ci->type == id_OSCH) {''')
print('Applied diagnostic ODDRXE pack, route endpoint, and configuration support')

# Generated SC64 wrappers expose disabled hard Wishbone pins as constant lows.
# Those pins have fixed EFB wiring, not fabric routing; guard every removal.
pll=r'''
    void pack_disabled_pll_wb()
    {
        if (!bool_or_default(ctx->settings, ctx->id("arch.oddr_diagnostic")))
            return;
        for (auto &entry : ctx->cells) {
            CellInfo *ci = entry.second.get();
            if (ci->type != id_EHXPLLJ)
                continue;
            if (str_or_default(ci->params, id_PLL_USE_WB, "DISABLED") != "DISABLED")
                log_error("ODDR diagnostic requires PLL_USE_WB=DISABLED.\n");
            if (str_or_default(ci->params, id_PLLRST_ENA, "DISABLED") != "DISABLED")
                log_error("ODDR diagnostic requires PLLRST_ENA=DISABLED.\n");
            std::vector<std::string> ports = {"PLLCLK", "PLLRST", "PLLSTB", "PLLWE"};
            for (int i=0; i<5; ++i) ports.push_back("PLLADDR" + std::to_string(i));
            for (int i=0; i<8; ++i) ports.push_back("PLLDATI" + std::to_string(i));
            for (const auto &p : ports) {
                IdString port = ctx->id(p);
                NetInfo *net = ci->getPort(port);
                if (net == nullptr)
                    continue;
                if (net->driver.cell == nullptr || !net->driver.cell->type.in(id_GND, ctx->id("VLO")))
                    log_error("Disabled PLL WB input %s must be unconnected or constant zero.\n", p.c_str());
                ci->disconnectPort(port);
            }
        }
    }

'''
edit('pack.cc','    // Miscellaneous packer tasks',pll+'    // Miscellaneous packer tasks')
edit('pack.cc','        pack_misc();','        pack_misc();\n        pack_disabled_pll_wb();')

edit('bitstream.cc','    void write_pll(CellInfo *ci)\n    {',
'''    void write_pll(CellInfo *ci)
    {
        if (bool_or_default(ctx->settings, ctx->id("arch.oddr_diagnostic")) &&
            (!ci->attrs.count(id_ICP_CURRENT) || !ci->attrs.count(id_LPF_RESISTOR)))
            log_error("Diagnostic PLL configuration requires preserved ICP_CURRENT and LPF_RESISTOR source attributes.\\n");''')

# Reloaded routed JSON carries settings; require fresh command-line opt-in.
edit('main.cc','void MachXO2CommandHandler::customAfterLoad(Context *ctx)\n{',
'''void MachXO2CommandHandler::customAfterLoad(Context *ctx)
{
    ctx->settings[ctx->id("arch.oddr_diagnostic")] = vm.count("oddr-diagnostic") ? 1 : 0;''')
