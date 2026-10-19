"""Frame protocol - no Home Assistant needed."""

from custom_components.rockcore_local.protocol import FrameBuffer, decode, frame_ok

from .conftest import FRAMES


def test_frames_valid_and_decoded() -> None:
    assert all(frame_ok(f) for f in FRAMES.values())
    ch = decode(FRAMES["channels"]).values
    assert (ch["pv1_power"], ch["pv2_power"], ch["pv1_voltage"]) == (21, 17, 33.0)
    assert (ch["grid_voltage"], ch["grid_frequency"], ch["temperature"]) == (235, 50.04, 26)
    assert decode(FRAMES["power"]).values == {"power": 683.0}
    assert decode(FRAMES["energy"]).values["energy_wh"] == 636156
    assert decode(FRAMES["typ6"]) is None


def test_corrupt_frame_rejected() -> None:
    bad = bytearray(FRAMES["energy"])
    bad[44] ^= 0x01                       # one bit in the energy counter
    assert not frame_ok(bytes(bad))
    assert FrameBuffer().feed(bytes(bad)) == []


def test_stream_split_merged_and_junk() -> None:
    stream = b"AT+\r" + FRAMES["channels"] + b"\x00\x68\x01" + FRAMES["power"] + FRAMES["energy"]
    buf = FrameBuffer()
    frames = []
    for i in range(0, len(stream), 7):
        frames += buf.feed(stream[i:i + 7])
    assert frames == [FRAMES["channels"], FRAMES["power"], FRAMES["energy"]]
    assert buf.dropped == 7               # "AT+\r" and the three junk bytes
