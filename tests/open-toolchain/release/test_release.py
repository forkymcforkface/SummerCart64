"""In-memory update-format fixtures; no toolchain, network or hardware required."""
import struct
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from release_update import inspect
from compare import differences
from cpu import compare_cpu, COMPONENTS


def fixture(payload=b'abc',ident=3):
    size=(16+len(payload)+15)&~15
    return b'SC64 Update v2.0'+struct.pack('<4I',ident,size-8,zlib.crc32(payload),len(payload))+payload+bytes(size-16-len(payload))


class Release(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(inspect(fixture())[0]['length'],3)

    def test_crc(self):
        data=bytearray(fixture());data[32]^=1
        with self.assertRaises(ValueError):inspect(data)

    def test_padding(self):
        data=bytearray(fixture());data[-1]=1
        with self.assertRaises(ValueError):inspect(data)

    def test_truncated(self):
        with self.assertRaises(ValueError):inspect(fixture()[:-1])

    def test_duplicate(self):
        with self.assertRaises(ValueError):inspect(fixture()+fixture()[16:])

    def test_byte_ranges(self):
        self.assertEqual(differences(b'abcdef',b'aXXdeYz'),[[1,3],[5,7]])
        self.assertEqual(differences(b'same',b'same'),[])

    def test_cpu_one_byte_mismatch(self):
        source=b'SC64 Update v2.0'+b''.join(fixture(b'abcd',ident)[16:] for ident in (2,4,5))
        root=Path('synthetic-build')
        built={root/path:b'abcd' for _,path in COMPONENTS.values()}
        built[root/COMPONENTS['mcu'][1]]=b'abXd'
        with patch.object(Path,'read_bytes',lambda path:built[path]):
            result=compare_cpu(root,source)
        self.assertFalse(result['mcu']['identical'])
        self.assertEqual(result['mcu']['differing_intervals'],[[2,3]])
        self.assertTrue(result['bootloader']['identical'])
        self.assertTrue(result['primer']['identical'])


if __name__=='__main__':unittest.main()
