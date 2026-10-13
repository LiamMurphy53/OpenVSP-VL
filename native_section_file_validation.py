"""Validate native file-section reader preconditions without changing geometry."""

def validate_profile_file(path):
    """Check original file-section reader preconditions without altering points."""
    import math
    import struct
    data=path.read_bytes()
    if b'OPENVSP_XSEC_FILE_V1' not in data.split(b'\n',1)[0]:return
    from native_bor_points import validate_section_rows
    rows=[]
    for line in data.splitlines()[1:]:
        if len(line)>253:raise ValueError('Cross-section coordinate lines must fit the native reader buffer.')
        try:
            fields=line.split()
            if len(fields)<2:raise ValueError()
            # The original reader uses float coordinates before storing doubles.
            x,y=[struct.unpack('f',struct.pack('f',float(a)))[0] for a in fields[:2]]
        except (ValueError,OverflowError,struct.error):raise ValueError('Use two finite coordinates on each cross-section line.')
        if not all(math.isfinite(a) and abs(a)<1e12 for a in (x,y)):raise ValueError('Cross-section coordinates exceed native reader limits.')
        rows.append([x,y,0])
    if len(rows)<4 or len({tuple(row) for row in rows})<4:raise ValueError('Use at least four distinct cross-section points.')
    if max(p[0] for p in rows)==min(p[0] for p in rows) or max(p[1] for p in rows)==min(p[1] for p in rows):raise ValueError('File cross-sections need nonzero width and height.')
    if math.dist(rows[0],rows[-1])>1e-8:rows.append(rows[0])
    else:rows[-1]=rows[0]
    validate_section_rows(rows)


