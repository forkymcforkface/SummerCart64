"""Bounded serializer fixtures; generated frames never read release binaries."""
import unittest

from serialize_reference import crc16, serialize


def fixture(usercode=0):
    initial = bytes.fromhex('e2000000012bd0432200000040000000')
    init = bytes.fromhex('46000000')
    dictionary = bytes.fromhex('0200000009033028500548ff')
    frames = bytes.fromhex('b8e00302') + bytes(770 * 32)
    user = bytes.fromhex('c2800000') + usercode.to_bytes(4, 'big')
    address = bytes.fromhex('f600000000001800')
    ebr = address + bytes.fromhex('b2d00080') + bytes(1152)
    packed = bytes.fromhex('ff00ffffbdb3ffff3b000000')
    packed += initial + b'\xff' * 4 + init + dictionary + frames
    packed += crc16(initial + init + dictionary + frames)
    packed += b'\xff' * 8 + user + crc16(user) + ebr + crc16(ebr)
    packed += bytes.fromhex('22000000400000005e000000ffffffff')
    expected = bytes.fromhex('ffffbdb3ffff3b000000')
    expected += dictionary + init + frames + crc16(dictionary + init + frames)
    expected += b'\xff' * 8 + user + crc16(user)
    expected += bytes.fromhex('22000000c0000000') + b'\xff' * 8
    expected += address + bytes.fromhex('b2100080') + bytes(1152)
    expected += bytes.fromhex('2200000040000000ffffffff5e000000')
    expected += b'\xff' * 16
    return packed, expected


class SerializeTests(unittest.TestCase):
    def test_observed_crc_vector(self):
        self.assertEqual(crc16(bytes.fromhex('c280000000000000')), bytes.fromhex('2aa7'))

    def test_synthetic_exact_and_input_dependence(self):
        outputs = []
        for usercode in (0, 0x12345678):
            packed, expected = fixture(usercode)
            actual, report = serialize(packed)
            self.assertEqual(actual, expected)
            self.assertEqual(report['ebr_addresses'], [6144])
            outputs.append(actual)
        self.assertNotEqual(*outputs)

    def test_corrupt_each_crc_region(self):
        packed, _ = fixture()
        for marker, offset, error in ((bytes.fromhex('02000000'), 4, 'frame CRC'),
                                      (bytes.fromhex('c2800000'), 4, 'USERCODE CRC'),
                                      (bytes.fromhex('b2d00080'), 4, 'EBR CRC')):
            damaged = bytearray(packed)
            damaged[packed.index(marker) + offset] ^= 1
            with self.assertRaisesRegex(ValueError, error):
                serialize(bytes(damaged))

    def test_wrong_device_truncation_and_trailing_bytes(self):
        packed, _ = fixture()
        damaged = packed.replace(bytes.fromhex('012bd043'), bytes.fromhex('012bb043'))
        for data in (damaged, packed[:100], packed[:-1], packed + b'\0'):
            with self.assertRaises(ValueError):
                serialize(data)

    def test_out_of_range_ebr_with_valid_crc(self):
        packed, _ = fixture()
        start = packed.index(bytes.fromhex('f6000000'))
        region = bytearray(packed[start:start + 1164])
        region[4:8] = (26 * 2048).to_bytes(4, 'big')
        damaged = packed[:start] + region + crc16(region) + packed[start + 1166:]
        with self.assertRaisesRegex(ValueError, 'invalid EBR order/address'):
            serialize(damaged)


if __name__ == '__main__':
    unittest.main()
