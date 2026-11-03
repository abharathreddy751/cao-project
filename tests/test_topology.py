import os
import struct
import sys

import pytest

from caosched.phase0 import topology as topo


def _pack_cpu_set_entry(lp_index: int, core_index: int, efficiency_class: int,
                         numa_node: int = 0, llc_index: int = 0) -> bytes:
    """Build one raw SYSTEM_CPU_SET_INFORMATION entry byte-for-byte, matching
    the real 32-byte layout confirmed empirically on this machine (see
    comment on caosched.phase0.topology._CpuSet): header (Size, Type) = 8
    bytes, then Id/Group/6 one-byte fields = 12 bytes, 4 bytes padding to
    reach 8-byte alignment, then one 8-byte union slot = 32 bytes total.
    """
    header = struct.pack("<II", 32, 0)  # Size=32, Type=0 (CpuSetInformation)
    body = struct.pack("<IHBBBBBB", 0, 0, lp_index, core_index, llc_index, numa_node, efficiency_class, 0)
    padding = b"\x00" * 4
    tail = struct.pack("<Q", 0)
    return header + body + padding + tail


def test_parse_cpu_set_buffer_matches_real_32_byte_entry_size():
    """Regression test for a real bug caught while validating this module on
    actual hardware (i5-1235U, 12 logical processors): an earlier struct
    definition declared the trailing SchedulingClass/AllocationTag as two
    separate sequential uint64 fields instead of the union they actually are,
    overcounting the per-entry size as 40 bytes instead of 32. That silently
    dropped the last logical processor from the enumeration (11 found instead
    of 12) without raising any error. This test pins the correct 32-byte
    layout so that regression can never return unnoticed.
    """
    raw = (
        _pack_cpu_set_entry(lp_index=0, core_index=0, efficiency_class=1)
        + _pack_cpu_set_entry(lp_index=1, core_index=0, efficiency_class=1)
        + _pack_cpu_set_entry(lp_index=2, core_index=1, efficiency_class=0)
    )
    infos = topo._parse_cpu_set_buffer(raw)
    assert len(infos) == 3
    assert [i.logical_processor_index for i in infos] == [0, 1, 2]
    assert [i.core_index for i in infos] == [0, 0, 1]
    assert [i.efficiency_class for i in infos] == [1, 1, 0]


def test_parse_cpu_set_buffer_empty_returns_empty_list():
    assert topo._parse_cpu_set_buffer(b"") == []


def test_parse_cpu_set_buffer_truncated_entry_is_skipped_not_crashed():
    """A buffer that ends mid-entry (shorter than one full header) must not
    raise -- the parser should simply stop, since a caller handling a real
    OS-supplied buffer should never crash on unexpected trailing bytes.
    """
    raw = _pack_cpu_set_entry(lp_index=0, core_index=0, efficiency_class=1) + b"\x00\x00\x00"
    infos = topo._parse_cpu_set_buffer(raw)
    assert len(infos) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="CPU Sets API is Windows-only")
def test_discover_topology_on_this_machine_is_internally_consistent():
    """Integration test against the real machine running this suite: the P/E
    partition must cover every discovered logical processor exactly once, and
    the total must match os.cpu_count().
    """
    result = topo.discover_topology()
    assert result.available, result.error
    assert result.raw_logical_processor_count == os.cpu_count()
    all_lps = set(result.p_core_logical_processors) | set(result.e_core_logical_processors)
    assert len(all_lps) == result.raw_logical_processor_count
    assert set(result.p_core_logical_processors).isdisjoint(result.e_core_logical_processors)
