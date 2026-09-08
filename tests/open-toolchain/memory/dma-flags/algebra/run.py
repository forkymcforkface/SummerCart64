"""Algebraic follow-up using the existing actual-DMA equivalence harness.

Predecode old counter values instead of subtracting before comparison. Lower
bounds preserve unsigned 27-bit wraparound for zero and one-byte counters.
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('dma_flag_baseline', Path(__file__).resolve().parents[1] / 'run.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
registered = baseline.transform


def transform(source):
    source = registered(source)
    for decrement, count in [(1, 3), (2, 2)]:
        expression = f"((mem_bus_remaining_bytes - 27'd{decrement}))"
        for name, old, new in [
            ('last', f"({expression} == 27'd0)", f"(mem_bus_remaining_bytes == 27'd{decrement})"),
            ('almost_last', f"({expression} <= 27'd2)",
             f"((mem_bus_remaining_bytes >= 27'd{decrement}) && (mem_bus_remaining_bytes <= 27'd{decrement + 2}))")]:
            anchor = f'mem_bus_{name}_transfer <= {old};'
            if source.count(anchor) != count:
                raise ValueError('unexpected algebraic predicate count')
            source = source.replace(anchor, f'mem_bus_{name}_transfer <= {new};')
    return source


if __name__ == '__main__':
    baseline.transform = transform
    baseline.main()
