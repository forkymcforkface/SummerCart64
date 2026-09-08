"""Apply strict ordered MachXO2 IOBUF ALLPORTS parsing to pinned nextpnr."""

import hashlib
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "machxo2/lpf.cc"
source = path.read_bytes()
expected = "8f32c0e24d35d448490d2447168a19f55662094067509d1c88362431cfa9dfa7"
if hashlib.sha256(source).hexdigest() != expected:
    raise SystemExit("lpf.cc differs from pinned source; no files written")
text = source.decode()
start = text.index("static const pool<std::string> iobuf_keys")
end = text.index("\nbool Arch::apply_lpf", start)
text = (
    text[:start]
    + r"""/* Values are present in the pinned MachXO2 PIO database. Pin direction,
   bank compatibility, and per-site capability remain backend checks. */
static const dict<std::string, pool<std::string>> iobuf_values = {
        {"PULLMODE", {"UP", "DOWN", "NONE", "KEEPER", "FAILSAFE"}},
        {"DRIVE", {"2", "4", "6", "8", "12", "16", "24"}},
        {"SLEWRATE", {"FAST", "SLOW"}},
        {"CLAMP", {"OFF", "ON", "PCI"}},
        {"OPENDRAIN", {"OFF", "ON"}},
        {"HYSTERESIS", {"SMALL", "LARGE"}},
};
"""
    + text[end:]
)
text = text.replace('#include "log.h"', '#include "log.h"\n#include "pio.h"')
start = text.index('                    } else if (verb == "IOBUF") {')
end = text.index("\n                    }\n                }", start)
text = (
    text[:start]
    + r"""                    } else if (verb == "IOBUF") {
                        if (words.size() < 3 || (words.at(1) != "PORT" && words.at(1) != "ALLPORTS"))
                            log_error("expected IOBUF PORT <name> or IOBUF ALLPORTS with attributes (on line %d)\n",
                                      lineno);
                        bool allports = words.at(1) == "ALLPORTS";
                        size_t first_attr = allports ? 2 : 3;
                        if (words.size() <= first_attr)
                            log_error("expected IOBUF attributes (on line %d)\n", lineno);
                        std::vector<std::pair<IdString, std::string>> attrs;
                        for (size_t i = first_attr; i < words.size(); ++i) {
                            const auto &setting = words.at(i);
                            size_t eqpos = setting.find('=');
                            if (eqpos == std::string::npos || eqpos == 0 || eqpos + 1 == setting.size() ||
                                setting.find('=', eqpos + 1) != std::string::npos)
                                log_error("expected IOBUF <attr>=<value> (on line %d)\n", lineno);
                            std::string key = setting.substr(0, eqpos);
                            std::string value = strip_quotes(setting.substr(eqpos + 1));
                            if (key == "IO_TYPE") {
                                auto type = ioType_from_str(value);
                                if (type == IOType::TYPE_UNKNOWN || type == IOType::TYPE_NONE)
                                    log_error("unsupported IOBUF IO_TYPE '%s' (on line %d)\n", value.c_str(), lineno);
                            } else {
                                auto allowed = iobuf_values.find(key);
                                if (allowed == iobuf_values.end())
                                    log_error("unsupported IOBUF attribute '%s' (on line %d)\n", key.c_str(), lineno);
                                if (!allowed->second.count(value))
                                    log_error("unsupported IOBUF %s value '%s' (on line %d)\n", key.c_str(),
                                              value.c_str(), lineno);
                            }
                            attrs.emplace_back(id(key), value);
                        }
                        auto apply_attrs = [&](CellInfo *cell) {
                            for (const auto &attr : attrs)
                                cell->attrs[attr.first] = attr.second;
                        };
                        if (allports) {
                            for (const auto &port : port_cells)
                                apply_attrs(port.second);
                        } else {
                            std::string name = strip_quotes(words.at(2));
                            if (name.empty())
                                log_error("empty IOBUF PORT name (on line %d)\n", lineno);
                            auto port = port_cells.find(id(name));
                            if (port == port_cells.end() && name.size() >= 3 && name.substr(name.size() - 3) == "[0]")
                                port = port_cells.find(id(name.substr(0, name.size() - 3)));
                            if (port != port_cells.end())
                                apply_attrs(port->second);
                        }"""
    + text[end:]
)
path.write_text(text)
print("MachXO2 IOBUF ALLPORTS patch applied")
