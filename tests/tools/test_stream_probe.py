"""Unit tests for tools/stream_probe.py.

The fMP4 fragment parser, the NAL keyframe test, the rate and gap
arithmetic, the analytics latency clock, the health summary's shape on
an empty and an init-less capture, the reconnect count across stream
indexes, the H.264 crop units, and the media socket url round trip.
No browser, no network.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import stream_probe as sp  # noqa: E402

TIMESCALE = 90000
HEVC_IDR = b'\x26\x01'  # nal_unit_type 19 (IDR_W_RADL) in the two-byte HEVC header
HEVC_TRAIL = b'\x02\x01'  # nal_unit_type 1 (TRAIL_R)
H264_IDR = b'\x65\x88'  # nal_unit_type 5 (IDR slice)
H264_SLICE = b'\x41\x9a'  # nal_unit_type 1 (non-IDR slice)


def box(typ: bytes, body: bytes) -> bytes:
    return struct.pack('>I4s', 8 + len(body), typ) + body


def fragment(track: int, tfdt: int, nal_payload: bytes, flags: int = 0) -> bytes:
    """One moof+mdat holding a single length-prefixed NAL, with a version-1 tfdt."""
    tfhd = box(b'tfhd', struct.pack('>I', 0) + struct.pack('>I', track))
    tfdt_b = box(b'tfdt', struct.pack('>I', 1 << 24) + struct.pack('>Q', tfdt))
    trun = box(b'trun', struct.pack('>I', 0x400) + struct.pack('>I', 1) + struct.pack('>I', flags))
    moof = box(b'moof', box(b'traf', tfhd + tfdt_b + trun))
    nal = struct.pack('>I', len(nal_payload)) + nal_payload
    return moof + box(b'mdat', nal)


def nal_buf(payload: bytes) -> tuple[bytes, tuple[int, int]]:
    """A bare mdat body: one 4-byte length prefix and the NAL, plus its (start, end)."""
    buf = struct.pack('>I', len(payload)) + payload
    return buf, (0, len(buf))


def sock(frames: list[dict], stream: str = '1', t_open: float | None = 10.0,
         wall_open: float | None = None) -> dict:
    """A media socket bundle in the shape collect_sockets / direct_socket produce."""
    return {'url': sp.media_url(16, 5, int(stream), uid='u'),
            'name': {'site': '16', 'channel': '5', 'stream': stream},
            't_open': t_open, 'wall_open': wall_open, 'frames': frames,
            'close': None, 'error': None}


def video_frame(t: float, track: int = 1, tfdt: int = 0) -> dict:
    return {'opcode': 2, 't': t, 'data': fragment(track, tfdt, H264_IDR)}


class _Bits:
    """MSB-first bit writer, the inverse of stream_probe.Bits, enough to build an SPS."""

    def __init__(self):
        self.bits: list[int] = []

    def u(self, n: int, v: int) -> None:
        self.bits += [(v >> (n - 1 - i)) & 1 for i in range(n)]

    def ue(self, v: int) -> None:
        code = v + 1
        self.bits += [0] * (code.bit_length() - 1)
        self.u(code.bit_length(), code)

    def to_bytes(self) -> bytes:
        bits = [*self.bits, 1]  # rbsp stop bit
        bits += [0] * (-len(bits) % 8)
        return bytes(int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))


def h264_sps(chroma: int, crop_bottom: int = 0, crop_right: int = 0) -> bytes:
    """A High profile SPS for a 1920x1088 coded frame with the given chroma format and crop."""
    w = _Bits()
    w.u(8, 100)  # profile_idc: High, so chroma_format_idc is present
    w.u(8, 0)  # constraint flags
    w.u(8, 40)  # level_idc 4.0
    w.ue(0)  # seq_parameter_set_id
    w.ue(chroma)
    if chroma == 3:
        w.u(1, 0)  # separate_colour_plane_flag
    w.ue(0)  # bit_depth_luma_minus8
    w.ue(0)  # bit_depth_chroma_minus8
    w.u(1, 0)  # qpprime_y_zero_transform_bypass_flag
    w.u(1, 0)  # seq_scaling_matrix_present_flag
    w.ue(0)  # log2_max_frame_num_minus4
    w.ue(0)  # pic_order_cnt_type
    w.ue(0)  # log2_max_pic_order_cnt_lsb_minus4
    w.ue(0)  # max_num_ref_frames
    w.u(1, 0)  # gaps_in_frame_num_value_allowed_flag
    w.ue(119)  # pic_width_in_mbs_minus1 -> 1920
    w.ue(67)  # pic_height_in_map_units_minus1 -> 1088
    w.u(1, 1)  # frame_mbs_only_flag
    w.u(1, 0)  # direct_8x8_inference_flag
    w.u(1, 1)  # frame_cropping_flag
    w.ue(0)  # left
    w.ue(crop_right)
    w.ue(0)  # top
    w.ue(crop_bottom)
    return b'\x67' + w.to_bytes()


def test_keyframe_by_nal_hevc_idr_and_h264_idr():
    """An IRAP or IDR NAL reads as a keyframe, a trailing slice does not, and an empty NAL is unreadable."""
    buf, body = nal_buf(HEVC_IDR)
    assert sp.keyframe_by_nal(buf, body, 4, hevc=True) is True
    buf, body = nal_buf(HEVC_TRAIL)
    assert sp.keyframe_by_nal(buf, body, 4, hevc=True) is False
    buf, body = nal_buf(H264_IDR)
    assert sp.keyframe_by_nal(buf, body, 4, hevc=False) is True
    buf, body = nal_buf(H264_SLICE)
    assert sp.keyframe_by_nal(buf, body, 4, hevc=False) is False
    buf, body = nal_buf(b'')
    assert sp.keyframe_by_nal(buf, body, 4, hevc=True) is None


def test_parse_fragment_reads_tfdt_v1_samples_and_flags():
    """parse_fragment reads the track id, the 64-bit decode time, the sample count, the sample flags and the mdat span."""
    data = fragment(2, 5 * TIMESCALE, H264_IDR, flags=1 << 16)
    frag = sp.parse_fragment(data)
    assert frag is not None
    assert frag['track'] == 2
    assert frag['time'] == 5 * TIMESCALE
    assert frag['samples'] == 1
    assert frag['flags'] == 1 << 16
    assert frag['mdat'] == 4 + len(H264_IDR)
    start, end = frag['mdat_body']
    assert data[start:end] == struct.pack('>I', len(H264_IDR)) + H264_IDR
    assert sp.parse_fragment(box(b'mdat', b'')) is None


def test_video_rates_fps_bitrate_gaps_and_zero_guards():
    """Ten 25 fps samples with one 200 ms hole give the fps, the bitrate and one gap; a lone frame, a missing timescale or a single sample gives None, not a division error."""
    tick = TIMESCALE // 25
    times = [i * tick for i in range(5)] + [4 * tick + 18000 + i * tick for i in range(5)]
    video = [{'time': t, 'samples': 1, 'mdat': 1000} for t in times]
    out = sp.health_metrics([], [], None)
    sp._video_rates(out, video, TIMESCALE, {'fps': 25})
    span = (times[-1] - times[0]) / TIMESCALE
    assert out['span_s'] == round(span, 2)
    assert out['fps_measured'] == round(9 / span, 2)
    assert out['bitrate_kbps_measured'] == round(10 * 1000 * 8 / span / 1000)
    gaps = out['timestamp_gaps']
    assert gaps['count'] == 1
    assert gaps['examples_ms'] == [200]
    assert gaps['worst_delta_ms'] == 200
    assert gaps['nominal_ms'] == 40.0
    assert gaps['basis'] == '1000 / configured fps'
    assert gaps['backwards'] == 0

    lone = sp.health_metrics([], [], None)
    sp._video_rates(lone, video[:1], TIMESCALE, None)
    assert lone['fps_measured'] is None
    assert lone['span_s'] is None
    assert lone['timestamp_gaps']['basis'] == 'no tfdt deltas'
    assert lone['timestamp_gaps']['worst_delta_ms'] is None

    no_timescale = sp.health_metrics([], [], None)
    sp._video_rates(no_timescale, video, None, None)
    assert no_timescale['fps_measured'] is None
    assert no_timescale['bitrate_kbps_measured'] is None

    one_sample = sp.health_metrics([], [], None)
    sp._video_rates(one_sample, [{'time': 0, 'samples': 1, 'mdat': 10},
                                 {'time': tick, 'samples': 0, 'mdat': 10}], TIMESCALE, None)
    assert one_sample['fps_measured'] is None
    assert one_sample['span_s'] == round(tick / TIMESCALE, 2)


def test_analytics_latency_uses_wall_open_plus_monotonic_offset():
    """Latency is the handshake wall time plus the monotonic offset at receipt, minus the frame's epoch timeStamp; a non-epoch stamp gives no number and says why."""
    wall_open = 1_700_000_000.0
    text = [
        {'t': 100.0, 'text': json.dumps({'type': 'mse', 'value': 'video/mp4; codecs="hvc1"'})},
        {'t': 101.0, 'text': json.dumps({'timeStamp': 1_700_000_000_500,
                                         'vehicleCount': 3, 'peopleCount': 0})},
        {'t': 102.0, 'text': json.dumps([{'timeStamp': 1_700_000_001_800,
                                          'vehicleCount': 1, 'peopleCount': 2}])},
        {'t': 102.5, 'text': 'not json'},
    ]
    out = sp.health_metrics([], [], None)
    sp._analytics(out, text, {'wall_open': wall_open}, 100.0)
    assert out['mime'] == 'video/mp4; codecs="hvc1"'
    assert out['analytics_alive'] is True
    assert out['analytics_frames'] == 2
    assert out['counters_max'] == {'vehicleCount': 3, 'peopleCount': 2}
    lat = out['latency_ms']
    assert (lat['min'], lat['median'], lat['max'], lat['samples']) == (200, 350, 500, 2)
    assert lat['basis'].startswith('timeStamp is epoch ms')

    off = sp.health_metrics([], [], None)
    sp._analytics(off, [{'t': 101.0, 'text': json.dumps({'timeStamp': 12345})}],
                  {'wall_open': wall_open}, 100.0)
    assert off['latency_ms'] == {'median': None, 'basis': 'timeStamp 12345 is not epoch-based'}

    no_wall = sp.health_metrics([], [], None)
    sp._analytics(no_wall, text[1:2], {'wall_open': None}, 100.0)
    assert no_wall['latency_ms']['median'] is None
    assert no_wall['analytics_frames'] == 1


def test_health_metrics_empty_and_no_init_do_not_crash():
    """No socket reports offline with a stable key set; a fragment with no init segment reports online with its first-frame time, no rates and a note, on the same keys."""
    empty = sp.health_metrics([], [], None)
    assert empty['online'] is False
    assert empty['note'] == 'no media socket opened'
    for key in ('socket_error', 'span_s', 'counters_max', 'latency_ms', 'stream_index',
                'keyframe_nal_unreadable', 'fps_measured'):
        assert key in empty
        assert empty[key] is None
    assert empty['reconnects'] == 0
    assert empty['stream_indexes_seen'] == []
    assert empty['timeline'] == {'error': None}

    one = sp.health_metrics([sock([video_frame(10.5)])], [], None)
    assert one['online'] is True
    assert one['first_frame_ms'] == 500
    assert one['frames'] == 1
    assert one['binary_frames'] == 1
    assert one['fps_measured'] is None
    assert one['bitrate_kbps_measured'] is None
    assert one['keyframe_interval_s'] is None
    assert one['note'] == 'no init segment; track chosen by size'
    assert one['stream_index'] == 1
    assert one['stream_indexes_seen'] == [1]
    assert set(one) == set(empty)

    # two tracks and no init: the heavier track is the video
    frames = [{'opcode': 2, 't': 10.2 + i * 0.1, 'data': fragment(1, i * 1000, b'\x41' * 8)}
              for i in range(3)]
    frames += [{'opcode': 2, 't': 11.0 + i * 0.1, 'data': fragment(2, i * 1000, H264_IDR * 100)}
               for i in range(2)]
    two = sp.health_metrics([sock(frames)], [], None)
    assert two['binary_frames'] == 5
    assert two['frames'] == 2
    assert two['first_frame_ms'] == 1000


def test_health_metrics_reconnects_count_only_the_measured_stream():
    """Reconnects count the sockets on the primary socket's stream index; a full screen socket on another index is listed, not counted."""
    sockets = [sock([video_frame(10.5)], stream='1', t_open=10.0),
               sock([video_frame(12.5), video_frame(12.6, tfdt=3000)], stream='1', t_open=12.0),
               sock([video_frame(13.5)], stream='0', t_open=13.0)]
    out = sp.health_metrics(sockets, [], None)
    assert out['stream_index'] == 1
    assert out['reconnects'] == 1
    assert out['stream_indexes_seen'] == [0, 1]
    assert out['first_frame_ms'] == 500
    assert out['frames'] == 2


def test_parse_h264_sps_crop_units_follow_chroma_format():
    """The conformance crop uses a vertical unit of 2 for 4:2:0 only; 4:2:2 crops rows one at a time, and 4:4:4 and monochrome use 1 on both axes."""
    assert sp.parse_h264_sps(h264_sps(chroma=1, crop_bottom=4))['height'] == 1080
    assert sp.parse_h264_sps(h264_sps(chroma=2, crop_bottom=4))['height'] == 1084
    assert sp.parse_h264_sps(h264_sps(chroma=2, crop_right=4))['width'] == 1912
    full = sp.parse_h264_sps(h264_sps(chroma=3, crop_bottom=4, crop_right=4))
    assert (full['width'], full['height']) == (1916, 1084)
    mono = sp.parse_h264_sps(h264_sps(chroma=0, crop_bottom=4, crop_right=4))
    assert (mono['width'], mono['height']) == (1916, 1084)
    assert (full['profile_idc'], full['level']) == (100, 4.0)


def test_parse_ws_name_and_media_url_round_trip():
    """media_url builds the app's name=/src= query and parse_ws_name reads the seven path parts back; a url without name= parses to nothing."""
    url = sp.media_url(16, 121, 1, uid='abc')
    assert url.startswith(sp.STREAM_HOST + '/v3/api/ws?name=')
    assert 'src=' in url
    assert '/' not in url.split('?', 1)[1]  # every slash in the path is percent-encoded
    assert sp.parse_ws_name(url) == {'site': '16', 'channel': '121', 'app': '0', 'live': '1',
                                     'stream': '1', 'timestamp': '0', 'uuid': 'abc'}
    assert sp.parse_ws_name(sp.media_url(16, 121, 0, uid='abc', with_name=False)) == {}
    assert 'src=' not in sp.media_url(16, 121, 0, with_src=False)
    assert sp.UUID_RE.search(sp.media_url(16, 121, 0)) is not None
