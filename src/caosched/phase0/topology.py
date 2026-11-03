"""P/E-core and SMT-topology discovery for Windows.

Windows does not guarantee that logical processor IDs are grouped or ordered by
core type. This module discovers the real mapping at runtime using the
``GetSystemCpuSetInformation`` Win32 API (CPU Sets, available since Windows 10
version 2004+), which is the same mechanism Windows' own scheduler and Task
Manager use to distinguish Performance cores from Efficiency cores on hybrid
CPUs such as Alder Lake and later.

If the API is unavailable or its result cannot be parsed, this module reports
the failure explicitly (``available=False`` + ``error``) rather than guessing --
callers must handle that case. This is a deliberate research-integrity choice:
an unmeasurable property is documented as a limitation, never silently assumed.
"""
from __future__ import annotations

import ctypes
import dataclasses
import json
import platform
import subprocess
from ctypes import wintypes


@dataclasses.dataclass(frozen=True)
class LogicalProcessorInfo:
    logical_processor_index: int
    core_index: int
    efficiency_class: int
    numa_node_index: int
    last_level_cache_index: int


@dataclasses.dataclass(frozen=True)
class TopologyResult:
    available: bool
    error: str | None
    processors: tuple[LogicalProcessorInfo, ...]
    core_groups: dict[int, tuple[int, ...]]
    efficiency_classes: tuple[int, ...]
    p_core_logical_processors: tuple[int, ...]
    e_core_logical_processors: tuple[int, ...]
    raw_logical_processor_count: int


class _InfoHeader(ctypes.Structure):
    """First 8 bytes common to every SYSTEM_CPU_SET_INFORMATION entry.

    Used to read ``Size``/``Type`` safely even for an entry type this module
    does not otherwise parse, so the walk can skip it without reading past the
    buffer.
    """

    _fields_ = [("Size", ctypes.c_uint32), ("Type", ctypes.c_int32)]


class _CpuSet(ctypes.Structure):
    # The real Win32 struct's trailing 8 bytes are a *union* of DWORD64
    # SchedulingClass and DWORD AllocationTag (verified empirically against
    # this machine's raw GetSystemCpuSetInformation buffer: the OS reports
    # Size=32 per entry, not 40 -- an earlier version of this struct declared
    # them as two sequential uint64 fields, which overcounted the per-entry
    # size by 8 bytes and silently dropped the last logical processor from
    # the enumeration). Neither field is used here, so one 8-byte slot
    # suffices to reproduce the correct total struct size.
    _fields_ = [
        ("Id", ctypes.c_uint32),
        ("Group", ctypes.c_uint16),
        ("LogicalProcessorIndex", ctypes.c_ubyte),
        ("CoreIndex", ctypes.c_ubyte),
        ("LastLevelCacheIndex", ctypes.c_ubyte),
        ("NumaNodeIndex", ctypes.c_ubyte),
        ("EfficiencyClass", ctypes.c_ubyte),
        ("AllFlags", ctypes.c_ubyte),
        ("SchedulingClassOrAllocationTag", ctypes.c_uint64),
    ]


class _CpuSetUnion(ctypes.Union):
    _fields_ = [("CpuSet", _CpuSet)]


class _SystemCpuSetInformation(ctypes.Structure):
    _fields_ = [
        ("Size", ctypes.c_uint32),
        ("Type", ctypes.c_int32),
        ("u", _CpuSetUnion),
    ]


_CPU_SET_INFORMATION_TYPE_CPU_SET = 0


def _call_get_system_cpu_set_information() -> bytes:
    """Return the raw buffer from GetSystemCpuSetInformation, or raise OSError."""
    kernel32 = ctypes.windll.kernel32
    func = kernel32.GetSystemCpuSetInformation
    func.argtypes = [
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.HANDLE,
        wintypes.ULONG,
    ]
    func.restype = wintypes.BOOL

    returned_length = wintypes.ULONG(0)
    func(None, 0, ctypes.byref(returned_length), None, 0)
    if returned_length.value == 0:
        raise OSError("GetSystemCpuSetInformation returned zero required length")

    buf = ctypes.create_string_buffer(returned_length.value)
    ok = func(buf, returned_length.value, ctypes.byref(returned_length), None, 0)
    if not ok:
        raise OSError(f"GetSystemCpuSetInformation failed: GetLastError={ctypes.get_last_error()}")
    return buf.raw[: returned_length.value]


def _parse_cpu_set_buffer(raw: bytes) -> list[LogicalProcessorInfo]:
    infos: list[LogicalProcessorInfo] = []
    offset = 0
    header_size = ctypes.sizeof(_InfoHeader)
    entry_size = ctypes.sizeof(_SystemCpuSetInformation)
    while offset < len(raw):
        if offset + header_size > len(raw):
            break
        header = _InfoHeader.from_buffer_copy(raw, offset)
        size = header.Size
        if size <= 0:
            break
        if header.Type == _CPU_SET_INFORMATION_TYPE_CPU_SET and offset + entry_size <= len(raw):
            entry = _SystemCpuSetInformation.from_buffer_copy(raw, offset)
            cpu_set = entry.u.CpuSet
            infos.append(
                LogicalProcessorInfo(
                    logical_processor_index=cpu_set.LogicalProcessorIndex,
                    core_index=cpu_set.CoreIndex,
                    efficiency_class=cpu_set.EfficiencyClass,
                    numa_node_index=cpu_set.NumaNodeIndex,
                    last_level_cache_index=cpu_set.LastLevelCacheIndex,
                )
            )
        offset += size
    return infos


def _unavailable(error: str) -> TopologyResult:
    return TopologyResult(
        available=False,
        error=error,
        processors=(),
        core_groups={},
        efficiency_classes=(),
        p_core_logical_processors=(),
        e_core_logical_processors=(),
        raw_logical_processor_count=0,
    )


def discover_topology() -> TopologyResult:
    """Discover P/E core + SMT topology. Never raises; failures are reported in the result."""
    if platform.system() != "Windows":
        return _unavailable(
            f"CPU Set topology discovery is Windows-only; platform.system()={platform.system()!r}"
        )

    try:
        raw = _call_get_system_cpu_set_information()
        infos = _parse_cpu_set_buffer(raw)
    except Exception as exc:  # noqa: BLE001 - must report, never raise
        return _unavailable(f"{type(exc).__name__}: {exc}")

    if not infos:
        return _unavailable("GetSystemCpuSetInformation returned zero CPU Set entries")

    infos.sort(key=lambda i: i.logical_processor_index)

    core_groups_lists: dict[int, list[int]] = {}
    for info in infos:
        core_groups_lists.setdefault(info.core_index, []).append(info.logical_processor_index)
    core_groups = {k: tuple(sorted(v)) for k, v in core_groups_lists.items()}

    efficiency_classes = tuple(sorted({i.efficiency_class for i in infos}))
    max_eff = max(efficiency_classes)

    p_core_lps = tuple(sorted(i.logical_processor_index for i in infos if i.efficiency_class == max_eff))
    e_core_lps = tuple(sorted(i.logical_processor_index for i in infos if i.efficiency_class != max_eff))

    return TopologyResult(
        available=True,
        error=None,
        processors=tuple(infos),
        core_groups=core_groups,
        efficiency_classes=efficiency_classes,
        p_core_logical_processors=p_core_lps,
        e_core_logical_processors=e_core_lps,
        raw_logical_processor_count=len(infos),
    )


def get_wmi_processor_summary() -> dict:
    """Cross-check via WMI: CPU name, physical core count, logical processor count.

    Shells out to PowerShell's ``Get-CimInstance`` (built into Windows 10+)
    rather than depending on the optional ``wmi`` PyPI package, keeping Phase 0
    dependency-free for this cross-check.
    """
    try:
        ps_cmd = (
            "Get-CimInstance Win32_Processor | "
            "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | "
            "ConvertTo-Json -Compress"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        data = json.loads(proc.stdout)
        if isinstance(data, list):
            data = data[0]
        return {
            "available": True,
            "error": None,
            "name": data.get("Name"),
            "number_of_cores": data.get("NumberOfCores"),
            "number_of_logical_processors": data.get("NumberOfLogicalProcessors"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "name": None,
            "number_of_cores": None,
            "number_of_logical_processors": None,
        }


def topology_to_dict(result: TopologyResult) -> dict:
    return {
        "available": result.available,
        "error": result.error,
        "raw_logical_processor_count": result.raw_logical_processor_count,
        "efficiency_classes_observed": list(result.efficiency_classes),
        "p_core_logical_processors": list(result.p_core_logical_processors),
        "e_core_logical_processors": list(result.e_core_logical_processors),
        "core_groups": {str(k): list(v) for k, v in result.core_groups.items()},
        "processors": [
            {
                "logical_processor_index": p.logical_processor_index,
                "core_index": p.core_index,
                "efficiency_class": p.efficiency_class,
                "numa_node_index": p.numa_node_index,
                "last_level_cache_index": p.last_level_cache_index,
            }
            for p in result.processors
        ],
    }


if __name__ == "__main__":
    print(json.dumps(topology_to_dict(discover_topology()), indent=2))
    print(json.dumps(get_wmi_processor_summary(), indent=2))
