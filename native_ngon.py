"""Lossless read-only capture of live original native polygon graph data."""
import ctypes
import json
from native_preview import adapter, _verified_private_layout
from vsp_runtime import distribution


def snapshot(v, gid):
    if gid not in v.FindGeoms() or v.GetGeomTypeName(gid).upper() not in ('NGONMESH', 'NGON_MESH'):
        raise ValueError('Choose an existing native polygon mesh.')
    guard = v.FindParm(gid, 'Scale_From_Original', 'XForm')
    if not v.ValidParm(guard):
        raise ValueError('Native polygon scale parameter unavailable.')
    path = distribution()/'python/openvsp/openvsp/_vsp.so'
    stat = path.stat()
    _verified_private_layout(str(path), stat.st_size, stat.st_mtime_ns)
    _, engine, bridge = adapter(v)
    function = bridge.studio_ngon_snapshot
    function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    function.restype = ctypes.c_char_p
    result = json.loads(function(engine, gid.encode(), guard.encode()))
    if 'error' in result:
        raise ValueError(result['error'])
    return result
