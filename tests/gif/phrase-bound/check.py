"""Check the LZW phrase-length invariant for a bounded decoded image.

The abstract transition permits any positive phrase up to the previously
emitted maximum plus one. This overapproximates a valid fresh GIF dictionary;
it does not model corrupt external RAM or qualify RTL by itself.
"""
import ast
from pathlib import Path
import sys


def triangular(length):
    return length * (length + 1) // 2


def main():
    transitions = 0
    for maximum in range(4096):
        for length in range(1, min(maximum + 1, 4096) + 1):
            if triangular(maximum) + length < triangular(max(maximum, length)):
                raise AssertionError((maximum, length))
            transitions += 1
    if triangular(0) + 2 >= triangular(2):
        raise AssertionError('invalid two-level jump did not violate invariant')
    limit = 320 * 240
    maximum = max(n for n in range(4097) if triangular(n) <= limit)
    assert maximum == 391 and maximum + 1 < 512
    assert triangular(391) == 76636 and triangular(392) == 77028

    source = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(source))
    from gif_reference import decode
    tree = ast.parse((source / 'fixtures.py').read_text())
    pack_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == 'pack')
    scope = {}
    exec(compile(ast.Module(body=[pack_node], type_ignores=[]), '<pack>', 'exec'), scope)
    pack = scope['pack']
    for minimum in range(2, 9):
        clear = 1 << minimum
        codes = [clear, 0] + list(range(clear + 2, clear + 392))
        expected = bytes(triangular(391))
        pixels, stats = decode(pack(codes + [clear + 1], minimum), minimum, len(expected))
        assert pixels == expected and stats['max_phrase'] == 391
        padded = codes + [0] * (limit - len(expected)) + [clear + 1]
        pixels, stats = decode(pack(padded, minimum), minimum, limit)
        assert pixels == bytes(limit) and stats['max_phrase'] == 391
        too_long = codes + [clear + 392, clear + 1]
        raw = pack(too_long, minimum)
        pixels, stats = decode(raw, minimum, triangular(392))
        assert pixels == bytes(triangular(392)) and stats['max_phrase'] == 392
        try:
            decode(raw, minimum, limit)
        except AssertionError:
            pass
        else:
            raise AssertionError('accepted over-limit phrase')
    print(f'PASS abstract_transitions={transitions} invalid_jump_rejected=1 '
          'minimum_sizes=7 maximum_emitted=391 maximum_walk=392')


if __name__ == '__main__':
    main()
