"""Derive a canvas-bounded decoder without changing canonical research RTL.

The accepted output limit is at most 76800 bytes; a guarded 512-byte stack
contains every valid phrase for that domain. Dictionary corruption still
fails before a stack write can exceed the physical memory.
"""
from pathlib import Path
import hashlib


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Source anchor changed: '+old)
    return text.replace(old, new)


def generate(source, output):
    core = (source/'cached/gif_lzw_cached.sv').read_text()
    core = replace(core, 'logic [7:0] stack [0:4095];',
                   '(* ram_style = "block" *) logic [7:0] stack [0:511];')
    core = replace(core, 'minimum < 2 || minimum > 8',
                   'minimum < 2 || minimum > 8 || output_limit > 76800', 3)
    core = replace(core, 'stack_size >= 4096', 'stack_size >= 512')
    core = replace(core, 'stack_size[11:0]', 'stack_size[8:0]', 2)
    core = replace(core, "stack[12'(stack_size", "stack[9'(stack_size")
    (output/'gif_lzw_cached.sv').write_text(core)
    (output/'cached_dictionary.sv').write_bytes((source/'cached/cached_dictionary.sv').read_bytes())
    return {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [source/'cached/gif_lzw_cached.sv', source/'cached/cached_dictionary.sv', Path(__file__)]}
