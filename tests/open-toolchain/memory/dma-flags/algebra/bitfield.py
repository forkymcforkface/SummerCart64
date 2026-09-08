"""Bounded high-bit-zero alternative to wide unsigned range comparisons."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('dma_flag_algebra', Path(__file__).with_name('run.py'))
algebra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(algebra)


def transform(source):
    source = algebra.transform(source)
    replacements = [
        (1, 3, "((mem_bus_remaining_bytes[26:2] == 25'd0) && (mem_bus_remaining_bytes[1:0] != 2'd0))"),
        (2, 2, "((mem_bus_remaining_bytes[26:3] == 24'd0) && ((mem_bus_remaining_bytes[2:0] == 3'd2) || (mem_bus_remaining_bytes[2:0] == 3'd3) || (mem_bus_remaining_bytes[2:0] == 3'd4)))")]
    for decrement, count, replacement in replacements:
        original = f"((mem_bus_remaining_bytes >= 27'd{decrement}) && (mem_bus_remaining_bytes <= 27'd{decrement + 2}))"
        if source.count(original) != count:
            raise ValueError('unexpected bitfield predicate count')
        source = source.replace(original, replacement)
    return source


if __name__ == '__main__':
    algebra.baseline.transform = transform
    algebra.baseline.main()
