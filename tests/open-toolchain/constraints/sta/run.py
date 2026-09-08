"""Run bounded synthetic OpenSTA constraints and fail-closed annotation fixtures.

The deliberately invented Liberty/SDF values are never MachXO2 timing models.
Every experiment gets a fresh directory and retains the engine's complete log.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--sta', required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    out = args.output.resolve()
    tests = here.parents[2]
    if out == tests or tests in out.parents:
        parser.error('output must be outside tests')
    out.mkdir(parents=True, exist_ok=False)
    files = {ext: (here / ('synthetic.' + ext)).read_text() for ext in ('lib', 'v', 'sdf', 'sdc')}
    base_metrics = {'min:capture/D': 1.75, 'min:q': 7.0, 'max:capture/D': 4.5, 'max:q': -1.5}
    cases = {'base': (dict(files), base_metrics, None)}

    def changed(ext, old, new):
        if old not in files[ext]:
            raise RuntimeError('fixture mutation anchor missing')
        result = dict(files)
        result[ext] = result[ext].replace(old, new)
        return result

    cases['phase0'] = (changed('sdc', '{7.5 7.5 7.5}', '{0 0 0}'),
                       {'min:capture/D': -0.75, 'min:q': -0.5, 'max:capture/D': 7.0, 'max:q': 6.0}, None)
    cases['input_min_zero'] = (changed('sdc', '-min -0.5', '-min 0.0'),
                               dict(base_metrics, **{'min:capture/D': 2.25}), None)
    cases['output_min_zero'] = (changed('sdc', '-min -1.0', '-min 0.0'),
                                dict(base_metrics, **{'min:q': 8.0}), None)
    cases['negative_sdf_hold'] = (changed('sdf', '(0.25:0.25:0.25)', '(-0.25:-0.25:-0.25)'),
                                  dict(base_metrics, **{'min:capture/D': 2.25}), None)
    delayed = dict(files)
    delayed['sdc'] += 'set_clock_latency 1.0 [get_clocks phase270]\n'
    cases['clock_latency'] = (delayed, {'min:capture/D': 0.75, 'min:q': 8.0,
                                      'max:capture/D': 5.5, 'max:q': -2.5}, None)
    cases['falling_input'] = (changed('sdc', 'set_input_delay -clock root',
                                      'set_input_delay -clock root -clock_fall'),
                              dict(base_metrics, **{'min:capture/D': 6.75, 'max:capture/D': -0.5}), None)
    excepted = dict(files)
    excepted['sdc'] += 'set_false_path -from [get_ports d] -to [get_pins capture/D]\n'
    cases['one_false_path'] = (excepted, {k: v for k, v in base_metrics.items() if k.endswith(':q')}, None)
    cases['missing_output_min'] = (changed('sdc', 'set_output_delay -clock root -min -1.0 [get_ports q]', ''),
                                   None, 'explicit I/O constraint coverage')
    cases['missing_input_delays'] = (changed('sdc', 'set_input_delay', '#set_input_delay'),
                                     None, 'explicit I/O constraint coverage')
    cases['wrong_instance'] = (changed('sdf', '(INSTANCE capture)', '(INSTANCE absent)'),
                               None, 'SDF instance coverage')
    cases['missing_sdf_arc'] = (changed('sdf', '(IOPATH (posedge CLK) Q (0.5:0.75:1.0) (0.5:0.75:1.0))', ''),
                                None, 'cell arc coverage')
    hold = '''      timing() {
        related_pin : "CLK"; timing_type : hold_rising;
        rise_constraint(check) { values("0.25"); }
        fall_constraint(check) { values("0.25"); }
      }
'''
    cases['missing_liberty_hold'] = (changed('lib', hold, ''), None, 'check arc coverage')
    results = []
    for name, (data, expected, rejection) in cases.items():
        case = out / name
        case.mkdir()
        for ext, content in data.items():
            (case / ('input.' + ext)).write_text(content)
        cells = dict(re.findall(r'^\s*(CLOCK_BUFFER|REG)\s+(\w+)\(', data['v'], re.M))
        annotated = re.findall(r'\(CELLTYPE "([^"]+)"\)\s*\(INSTANCE (\w+)\)', data['sdf'])
        if len(annotated) != 2 or dict(annotated) != cells:
            if rejection != 'SDF instance coverage':
                raise RuntimeError(name + ': unexpected SDF instance mismatch')
            results.append({'case': name, 'engine_exit': None, 'engine_run': False,
                            'expected_rejection': rejection, 'gate_failures': [rejection],
                            'test_passed': True})
            continue
        script = '''# Synthetic diagnostic only; ideal generated clock, explicit annotation checks.
read_liberty input.lib
read_verilog input.v
link_design top
read_sdc input.sdc
read_sdf input.sdf
report_clock_properties
check_setup -verbose
report_annotated_delay -cell -report_unannotated
report_annotated_check -setup -hold -report_unannotated
report_checks -path_delay min_max -format full_clock_expanded -digits 4
foreach kind {min max} {
    foreach endpoint {capture/D q} {
        set paths [find_timing_paths -to $endpoint -path_delay $kind]
        puts "PATHCOUNT $kind $endpoint [llength $paths]"
        if {[llength $paths] == 1} {
            puts "METRIC $kind $endpoint [get_property [lindex $paths 0] slack]"
        }
    }
}
write_sdc observed.sdc
exit
'''
        (case / 'run.tcl').write_text(script)
        proc = subprocess.run([args.sta, '-no_init', '-exit', 'run.tcl'], cwd=case,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
        (case / 'engine.log').write_text(proc.stdout)
        if proc.returncode < 0:
            raise RuntimeError(name + ': engine crashed; this is not a negative-test pass')
        if 'OpenSTA 3.1.0 a9a3f30ca9 ' not in proc.stdout:
            raise RuntimeError('engine banner differs from pinned build')
        metrics = {kind + ':' + endpoint: float(value) for kind, endpoint, value in
                   re.findall(r'METRIC (min|max) (\S+) (\S+)', proc.stdout)}
        failures = []
        if proc.returncode or re.search(r'(?mi)^\s*(?:warning|error)[: ]', proc.stdout):
            failures.append('engine diagnostic')
        cell = re.search(r'^cell arcs\s+(\d+)\s+(\d+)\s+(\d+)$', proc.stdout, re.M)
        if not cell or tuple(map(int, cell.groups())) != (2, 2, 0):
            failures.append('cell arc coverage')
        for check in ('setup', 'hold'):
            row = re.search(r'^cell ' + check + r' arcs\s+(\d+)\s+(\d+)\s+(\d+)$', proc.stdout, re.M)
            if not row or tuple(map(int, row.groups())) != (1, 1, 0):
                failures.append('check arc coverage')
        required = [('input', 'min', 'd'), ('input', 'max', 'd'),
                    ('output', 'min', 'q'), ('output', 'max', 'q')]
        if any(not re.search(r'^set_' + kind + r'_delay\b[^\n]*-' + bound +
                             r'\s+[-\d.]+\s+\[get_ports ' + port + r'\]', data['sdc'], re.M)
               for kind, bound, port in required):
            failures.append('explicit I/O constraint coverage')
        if rejection:
            if rejection not in failures:
                raise RuntimeError(name + ': incomplete model/constraints were not rejected: ' + str(failures))
        else:
            if failures:
                raise RuntimeError(name + ': unexpected qualification failures: ' + str(failures))
            if metrics.keys() != expected.keys() or any(abs(metrics[k] - v) > 0.0001 for k, v in expected.items()):
                raise RuntimeError(name + ': analytical slack mismatch: ' + str(metrics))
            waveform = (0.0, 5.0) if name == 'phase0' else (7.5, 12.5)
            row = re.search(r'^phase270\s+([\d.]+)\s+([\d.]+)\s+([\d.]+) \(generated\)', proc.stdout, re.M)
            if not row or tuple(map(float, row.groups())) != (10.0, *waveform):
                raise RuntimeError(name + ': generated clock waveform mismatch')
        results.append({'case': name, 'engine_exit': proc.returncode, 'metrics_ns': metrics,
                        'expected_rejection': rejection, 'gate_failures': failures, 'test_passed': True})
    report = {'opensta_source_pin': 'a9a3f30ca97dc13f9ef911cae1a82c42c67379e1',
              'binary_sha256': hashlib.sha256(Path(args.sta).read_bytes()).hexdigest(),
              'fixture_only': True, 'machxo2_timing_qualified': False, 'cases': results}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
