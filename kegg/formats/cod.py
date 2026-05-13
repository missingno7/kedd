from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodDecodeResult:
    data: bytes
    codec: str | None
    stored_checksum: int | None
    computed_residual: int | None
    key_seed_word: int | None

    @property
    def checksum_ok(self) -> bool:
        return self.computed_residual in (None, 0)


def rol16(value: int, bits: int) -> int:
    value &= 0xFFFF
    return ((value << bits) | (value >> (16 - bits))) & 0xFFFF


def ror16(value: int, bits: int) -> int:
    value &= 0xFFFF
    return ((value >> bits) | (value << (16 - bits))) & 0xFFFF


def rol32(value: int, bits: int) -> int:
    value &= 0xFFFFFFFF
    return ((value << bits) | (value >> (32 - bits))) & 0xFFFFFFFF


def ror32(value: int, bits: int) -> int:
    value &= 0xFFFFFFFF
    return ((value >> bits) | (value << (32 - bits))) & 0xFFFFFFFF


def decode_cod(data: bytes) -> CodDecodeResult:
    """Decode the game's COD0/COD1/COD2 trailing wrapper.

    This implementation is based on the disassembly around the decoder in
    KE.EXE. COD2 is the format used by the bundled asset files in the uploaded
    copy. COD0/COD1 are included because the executable checks for them too.

    COD2 layout at EOF:
        uint16 checksum
        uint16 key_seed_word
        char[4] marker = "COD2"

    Only the first min(payload_len, 0x400) bytes are XOR-decoded. This is why
    a decoded GIF immediately recovers its `GIF87a` header while the rest of
    the file remains untouched.
    """
    if len(data) < 8:
        return CodDecodeResult(data, None, None, None, None)

    marker = data[-4:]
    if marker == b"COD2":
        payload_len = len(data) - 8
        stored_checksum = int.from_bytes(data[payload_len : payload_len + 2], "little")
        key_seed = int.from_bytes(data[payload_len + 2 : payload_len + 4], "little")
        key = (ror16(key_seed, 7) << 16) | rol16(key_seed, 3)
        out = bytearray(data[:payload_len])
        limit = (min(payload_len, 0x400) // 4) * 4
        rolling_xor = 0

        for offset in range(0, limit, 4):
            value = int.from_bytes(out[offset : offset + 4], "little") ^ key
            out[offset : offset + 4] = value.to_bytes(4, "little")
            rolling_xor ^= value
            key = rol32(key, 1)

        residual = stored_checksum ^ (rolling_xor & 0xFFFF) ^ ((rolling_xor >> 16) & 0xFFFF)
        return CodDecodeResult(bytes(out), "COD2", stored_checksum, residual, key_seed)

    if marker in (b"COD0", b"COD1") and len(data) >= 10:
        payload_len = len(data) - 10
        stored_checksum = int.from_bytes(data[payload_len : payload_len + 2], "little")
        key = int.from_bytes(data[payload_len + 2 : payload_len + 6], "little")
        key = ror32(key, 7)
        out = bytearray(data[:payload_len])
        limit = (payload_len // 4) * 4
        rolling_xor = 0x1234

        for offset in range(0, limit, 4):
            value = int.from_bytes(out[offset : offset + 4], "little") ^ key
            out[offset : offset + 4] = value.to_bytes(4, "little")
            rolling_xor ^= value
            key = rol32(key, 1)

        residual = stored_checksum ^ (rolling_xor & 0xFFFF) ^ ((rolling_xor >> 16) & 0xFFFF)
        return CodDecodeResult(bytes(out), marker.decode("ascii"), stored_checksum, residual, key)

    return CodDecodeResult(data, None, None, None, None)


def decode_file(path: Path) -> CodDecodeResult:
    return decode_cod(path.read_bytes())


def encode_cod2(decoded_payload: bytes, key_seed_word: int) -> bytes:
    """Encode a decoded payload back into the game's COD2 wrapper.

    COD2 is symmetric XOR for the first min(len(payload), 0x400) bytes. The
    checksum stored in the trailer is computed from the decoded dwords, exactly
    as the game decoder verifies it.
    """
    key_seed_word &= 0xFFFF
    key = (ror16(key_seed_word, 7) << 16) | rol16(key_seed_word, 3)
    out = bytearray(decoded_payload)
    limit = (min(len(out), 0x400) // 4) * 4
    rolling_xor = 0

    for offset in range(0, limit, 4):
        decoded_value = int.from_bytes(out[offset : offset + 4], "little")
        rolling_xor ^= decoded_value
        encoded_value = decoded_value ^ key
        out[offset : offset + 4] = encoded_value.to_bytes(4, "little")
        key = rol32(key, 1)

    checksum = (rolling_xor & 0xFFFF) ^ ((rolling_xor >> 16) & 0xFFFF)
    out.extend(checksum.to_bytes(2, "little"))
    out.extend(key_seed_word.to_bytes(2, "little"))
    out.extend(b"COD2")
    return bytes(out)


def encode_file_cod2(path: Path, decoded_payload: bytes, key_seed_word: int) -> None:
    path.write_bytes(encode_cod2(decoded_payload, key_seed_word))
