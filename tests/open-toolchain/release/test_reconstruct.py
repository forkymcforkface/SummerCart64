"""Reconstruction gates tested with synthetic chunks and the actual upstream packer.

Only built CPU file reads are substituted; no release artifact or hardware is
required. The packer's implementation is loaded from this SC64 checkout.
"""

import hashlib
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zlib

from cpu import COMPONENTS
from reconstruct import reconstruct


def container(parts):
    data = b"SC64 Update v2.0"
    for ident, payload in parts:
        size = (16 + len(payload) + 15) & ~15
        data += struct.pack("<4I", ident, size - 8, zlib.crc32(payload), len(payload))
        data += payload + bytes(size - 16 - len(payload))
    return data


class Reconstruction(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[3]
        self.parts = [
            (1, b"synthetic metadata"),
            (2, b"mcu\x00\x19"),
            (3, b"synthetic FPGA\xff"),
            (4, b"bootloader\x7f"),
            (5, b"primer\x80"),
        ]
        self.reference = container(self.parts)
        self.fpga = self.parts[2][1]
        payloads = dict(self.parts)
        self.built = {
            self.root / path: payloads[ident] for ident, path in COMPONENTS.values()
        }
        actual_read = Path.read_bytes
        self.read_patch = patch.object(
            Path,
            "read_bytes",
            lambda path: self.built[path] if path in self.built else actual_read(path),
        )
        self.read_patch.start()
        self.addCleanup(self.read_patch.stop)

    def test_actual_upstream_packer_exact_and_scoped_report(self):
        result, report = reconstruct(self.root, self.reference, self.fpga)
        self.assertEqual(result, self.reference)
        self.assertTrue(report["byte_identical"])
        self.assertEqual(report["sha256"], hashlib.sha256(result).hexdigest())
        self.assertFalse(report["all_components_rebuilt_from_source"])
        self.assertEqual(report["metadata_origin"], "release reference")
        self.assertTrue(all(c["identical"] for c in report["cpu_components"].values()))
        packer = self.root / "sw/tools/update.py"
        self.assertEqual(
            report["upstream_packer_sha256"],
            hashlib.sha256(packer.read_bytes()).hexdigest(),
        )

    def test_each_cpu_byte_mismatch_rejected(self):
        for name, (_, path) in COMPONENTS.items():
            with self.subTest(component=name):
                file = self.root / path
                original = self.built[file]
                self.built[file] = bytes([original[0] ^ 1]) + original[1:]
                try:
                    with self.assertRaisesRegex(ValueError, "CPU binaries differ"):
                        reconstruct(self.root, self.reference, self.fpga)
                finally:
                    self.built[file] = original

    def test_fpga_byte_and_length_mismatches_rejected(self):
        for candidate in (
            self.fpga[:-1],
            self.fpga + b"\0",
            bytes([self.fpga[0] ^ 1]) + self.fpga[1:],
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "serialized FPGA differs"):
                    reconstruct(self.root, self.reference, candidate)

    def test_each_missing_component_rejected(self):
        for missing in range(1, 6):
            with self.subTest(missing=missing):
                reference = container([p for p in self.parts if p[0] != missing])
                with self.assertRaisesRegex(ValueError, "complete five-component"):
                    reconstruct(self.root, reference, self.fpga)

    def test_valid_but_reordered_container_rejected_by_final_byte_gate(self):
        reference = container([self.parts[1], self.parts[0], *self.parts[2:]])
        with self.assertRaisesRegex(ValueError, "upstream packaging differs"):
            reconstruct(self.root, reference, self.fpga)

    def test_corrupt_reference_rejected_before_reconstruction(self):
        reference = bytearray(self.reference)
        reference[32] ^= 1
        with self.assertRaisesRegex(ValueError, "CRC or padding mismatch"):
            reconstruct(self.root, bytes(reference), self.fpga)


if __name__ == "__main__":
    unittest.main()
