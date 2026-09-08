"""Exercise the coverage guard using caller-supplied public export data."""
import argparse
import pathlib
import subprocess
import sys
import tempfile
sys.dont_write_bytecode = True
from audit import audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=pathlib.Path)
    args = parser.parse_args()
    net = (args.directory / 'active7000.v').read_text()
    sdf = (args.directory / 'active7000.sdf').read_text()
    minimum = (args.directory / 'active7000-min.sdf').read_text()
    for text in (sdf, minimum):
        rows = audit(net, text, True)
        assert len(rows) == 26
        assert sum(len(r['unresolved_wrapper_pins']) for r in rows) == 2
        assert sum(r['primitive'] == 'DP8KC' for r in rows) == 24
    cases = [
        ('strict orphan', net, sdf, False, 'unmatched PDP'),
        ('reset', net.replace('RESETMODE = "SYNC"', 'RESETMODE = "ASYNC"'), sdf, True, 'reset mode'),
        ('register', net.replace('REGMODE_A = "NOREG"', 'REGMODE_A = "OUTREG"'), sdf, True, 'register mode'),
        ('write', net.replace('WRITEMODE_A = "NORMAL"', 'WRITEMODE_A = "WRITETHROUGH"'), sdf, True, 'write mode'),
        ('width', net.replace('DATA_WIDTH_A = 9', 'DATA_WIDTH_A = 18'), sdf, True, 'DP width'),
        ('scale', net, sdf.replace('(TIMESCALE 1ps)', '(TIMESCALE 1ns)'), True, 'timescale'),
        ('path', net, sdf.replace('(IOPATH CLKB DOB0', '(IOPATH CLKA DOB0', 1), True, 'coverage mismatch'),
        ('pin', net, sdf.replace('(SETUPHOLD DIA4 ', '(SETUPHOLD UNKNOWN ', 1), True, 'coverage mismatch'),
        ('clock edge', net, sdf.replace('(SETUPHOLD DIA4 (posedge', '(SETUPHOLD DIA4 (negedge', 1), True, 'coverage mismatch'),
        ('connection', net.replace('.DIA4(DIA4_dly)', '.DIA4(UNKNOWN_dly)', 1), sdf, True, 'primitive pin'),
        ('instance', net, sdf.replace('(INSTANCE lm32_inst\\/platform_u\\/ebr\\/genblk1', '(INSTANCE BAD\\/platform_u\\/ebr\\/genblk1'), True, 'instance path'),
        ('new check', net, sdf.replace('(SETUPHOLD DIA4 ', '(RECOVERY DIA4 ', 1), True, 'unsupported SDF'),
        ('no colon path', net, sdf.replace('(4248:4248:4248)', '(123)', 1), True, 'invalid triple'),
        ('minus path', net, sdf.replace('(4248:4248:4248)', '(-)', 1), True, 'invalid triple'),
        ('no colon check', net, sdf.replace('(-40:-40:-40)', '(123)', 1), True, 'invalid triple'),
        ('minus check', net, sdf.replace('(-40:-40:-40)', '(-)', 1), True, 'invalid triple'),
        ('no colon width', net, sdf.replace('(2735:2735:2735)', '(123)', 1), True, 'invalid triple'),
        ('minus width', net, sdf.replace('(2735:2735:2735)', '(-)', 1), True, 'invalid triple'),
    ]
    for label, n, s, inventory, expected in cases:
        try:
            audit(n, s, inventory)
        except ValueError as exc:
            assert expected in str(exc), (label, str(exc))
        else:
            raise AssertionError('accepted ' + label)
    command = [sys.executable, '-B', str(pathlib.Path(__file__).with_name('audit.py')),
               '--netlist', str(args.directory / 'active7000.v'),
               '--grade6', str(args.directory / 'active7000.sdf'),
               '--minimum', str(args.directory / 'active7000-min.sdf'),
               '--inventory-unmatched', '--output']
    with tempfile.TemporaryDirectory(dir=args.directory) as folder:
        target = pathlib.Path(folder) / 'existing.json'
        target.write_text('preserve')
        for path, reason in [(target, 'output must be fresh'),
                             (pathlib.Path(__file__).with_name('forbidden.json'),
                              'output must be outside tests')]:
            result = subprocess.run(command + [str(path)], capture_output=True, text=True)
            assert result.returncode == 1 and reason in result.stderr
        assert target.read_text() == 'preserve'
        assert not pathlib.Path(__file__).with_name('forbidden.json').exists()
    print('PASS two corner inventories and %d exact rejection checks' % (len(cases) + 2))


if __name__ == '__main__':
    main()
