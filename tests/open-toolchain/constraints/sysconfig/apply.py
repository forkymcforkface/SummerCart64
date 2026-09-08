"""Add two database-backed MachXO2 SYSCONFIG keys after the ALLPORTS patch.

Only the pinned parser is changed. Existing bitstream emission and Trellis
configuration encoders own the bits; unsupported profiles fail before writing.
"""
import hashlib
from pathlib import Path
import sys


def apply(root):
    path = Path(root) / 'machxo2/lpf.cc'
    source = path.read_bytes()
    expected = '38da7963795c7e1ad44633c1e302904046dc467c1e4a8a698d91f17cc19ee827'
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError('lpf.cc differs from pinned ALLPORTS source; no files written')
    text = source.decode()
    replacements = [
        ('        "COMPRESS_CONFIG",     "CONFIG_MODE",     "INBUF",',
         '        "COMPRESS_CONFIG",     "CONFIG_MODE",     "INBUF",\n'
         '        "SDM_PORT",            "I2C_PORT",'),
        ('                            if (eqpos == std::string::npos)\n',
         '                            if (eqpos == std::string::npos || eqpos == 0 || eqpos + 1 == setting.size() ||\n'
         "                                setting.find('=', eqpos + 1) != std::string::npos)\n"),
        ('                            settings[id("arch.sysconfig." + key)] = value;',
         '''                            if (key == "SDM_PORT" || key == "I2C_PORT") {
                                value = strip_quotes(value);
                                static const pool<std::string> sdm_values = {
                                        "DISABLE", "DONE", "INITN", "PROGRAMN", "PROGRAMN_DONE", "PROGRAMN_DONE_INITN"};
                                if ((key == "SDM_PORT" && !sdm_values.count(value)) ||
                                    (key == "I2C_PORT" && value != "DISABLE" && value != "ENABLE"))
                                    log_error("unsupported SYSCONFIG %s value '%s' (on line %d)\\n", key.c_str(),
                                              value.c_str(), lineno);
                            }
                            settings[id("arch.sysconfig." + key)] = value;'''),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise ValueError('patch anchor is not unique; no files written')
        text = text.replace(old, new)
    path.write_bytes(text.encode())


if __name__ == '__main__':
    apply(sys.argv[1])
    print('MachXO2 SDM_PORT/I2C_PORT parser patch applied')
