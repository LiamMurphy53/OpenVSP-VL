"""Validate file records before unsafe native readers; geometry stays in OpenVSP."""
import math
import re
import struct
import xml.etree.ElementTree as ET


NUMBER=r'[+-]?(?:0[xX](?:[0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?|\.[0-9a-fA-F]+)(?:[pP][+-]?[0-9]+)?|(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)'
SPACE=' \t\r\n\v\f'


def fail(fmt,message):
    raise ValueError(f'{fmt}: {message}')


def text(raw,fmt):
    try:return raw.decode('utf-8')
    except UnicodeDecodeError:fail(fmt,'expected a text file in this native format.')


def number(value,fmt):
    if not re.fullmatch(NUMBER,value):fail(fmt,'expected finite numeric records.')
    try:result=float.fromhex(value) if '0x' in value.lower() else float(value)
    except (ValueError,OverflowError):fail(fmt,'expected finite numeric records.')
    if not math.isfinite(result):fail(fmt,'expected finite numeric records.')
    return result


def count(value,fmt):
    if not re.fullmatch(r'\+?[0-9]+',value):fail(fmt,'expected a positive integer count.')
    digits=value.lstrip('+').lstrip('0') or '0'
    if len(digits)>10:fail(fmt,'a count exceeds the native integer range.')
    result=int(digits)
    if result<=0:fail(fmt,'counts must be positive.')
    if result>2147483647:fail(fmt,'a count exceeds the native integer range.')
    return result


def points(raw):
    fmt='POINTS';data=text(raw,fmt);pattern=re.compile(rf'\s*({NUMBER})[, ]+({NUMBER})[, ]+({NUMBER})\s*',re.ASCII)
    position=0;rows=0
    while position<len(data):
        match=pattern.match(data,position)
        if not match:fail(fmt,'use three finite coordinates per point, separated by spaces or commas.')
        for value in match.groups():number(value,fmt)
        position=match.end();rows+=1
    if not rows:fail(fmt,'the file contains no points.')
    if rows>1_000_000:fail(fmt,'the native display supports at most one million points.')


def nascart(raw):
    fmt='NASCART';tokens=re.split(r'\s+',text(raw,fmt).strip(SPACE),flags=re.ASCII)
    if len(tokens)<2:fail(fmt,'missing node and triangle counts.')
    nodes,tris=(count(value,fmt) for value in tokens[:2])
    expected=2+3*nodes+4*tris
    if len(tokens)<expected:fail(fmt,'node/triangle counts exceed the available complete file records.')
    for value in tokens[2:2+3*nodes]:
        if abs(number(value,fmt))>3.4028234663852886e38:fail(fmt,'a coordinate exceeds the native float range.')
    for i in range(2+3*nodes,expected,4):
        for value in tokens[i:i+3]:
            if not 1<=count(value,fmt)<=nodes:fail(fmt,'a triangle references a node outside this file.')
        if abs(number(tokens[i+3],fmt))>3.4028234663852886e38:fail(fmt,'a triangle tag exceeds the native float range.')


def bem(raw):
    fmt='BEM';original=text(raw,fmt).split('\n')
    # The native reader consumes one fixed-buffer line, then immediately scans
    # the first header. Do not silently discard leading lines before validation.
    if len(original)<2 or len(original[0].encode())>253 or not original[1].startswith('Num_Sections:'):
        fail(fmt,'expected the native title followed by Num_Sections.')
    lines=[original[0]]+[line.strip(SPACE) for line in original[1:] if line.strip(SPACE)]
    labels=['Num_Sections','Num_Blade','Diameter','Beta 3/4 (deg)','Feather (deg)','Pre_Cone (deg)','Center','Normal']
    if len(lines)<10:fail(fmt,'missing propeller header and section records.')
    values={}
    for i,label in enumerate(labels,1):
        head,separator,value=lines[i].partition(':')
        if not separator or head!=label:fail(fmt,f'expected the native {label} header.')
        values[label]=value.strip(SPACE)
    sections=count(values['Num_Sections'],fmt);count(values['Num_Blade'],fmt)
    if sections<2 or len(lines)<10+sections:fail(fmt,'provide at least two complete propeller section records.')
    if len(lines[9].encode())>253:fail(fmt,'the section column header exceeds the native reader buffer.')
    for label in labels[2:6]:number(values[label],fmt)
    for label in labels[6:]:
        coordinates=[v.strip(SPACE) for v in values[label].split(',')]
        if len(coordinates)!=3:fail(fmt,f'{label} needs three coordinates.')
        for value in coordinates:number(value,fmt)
    radii=[]
    for line in lines[10:10+sections]:
        row=[v.strip(SPACE) for v in line.split(',')]
        if len(row)!=10:fail(fmt,'each section needs the ten native BEM values.')
        parsed=[number(value,fmt) for value in row];radii.append(parsed[0])
    if any(a>=b for a,b in zip(radii,radii[1:])):fail(fmt,'section radii must increase for the native curve reader.')


def legacy(raw):
    fmt='VSP_V2'
    if b'<!DOCTYPE' in raw.upper():fail(fmt,'use an OpenVSP v2 geometry document without a document type declaration.')
    try:root=ET.fromstring(raw)
    except (ET.ParseError,ValueError):fail(fmt,'the file is not a complete OpenVSP v2 XML document.')
    if root.tag not in ('Vsp_Geometry','Ram_Geometry'):fail(fmt,'expected an OpenVSP v2 geometry document.')
    if not root.findall('./Component_List/Component'):fail(fmt,'the legacy document contains no components.')


class Scanner:
    """ASCII scanf-style record scanning, without changing any coordinates."""
    def __init__(self,raw,fmt):self.data=text(raw,fmt);self.fmt=fmt;self.position=0
    def take(self,pattern):
        match=re.compile(r'\s*(?:'+pattern+r')',re.ASCII).match(self.data,self.position)
        if not match:fail(self.fmt,'missing or malformed native file records.')
        self.position=match.end();return match
    def integer(self,positive=False):
        token=self.take(r'([+-]?[0-9]+)').group(1)
        if positive:return count(token,self.fmt)
        digits=token.lstrip('+-').lstrip('0') or '0'
        if len(digits)>10:fail(self.fmt,'an integer record exceeds the native range.')
        value=int(('-' if token.startswith('-') else '')+digits)
        if not -2147483648<=value<=2147483647:fail(self.fmt,'an integer record exceeds the native range.')
        return value
    def scalar(self,single=False):
        value=number(self.take('('+NUMBER+')').group(1),self.fmt)
        if single and abs(value)>3.4028234663852886e38:fail(self.fmt,'a coordinate exceeds the native float range.')
        return value
    def line(self):
        self.position+=len(self.data[self.position:])-len(self.data[self.position:].lstrip(SPACE))
        end=self.data.find('\n',self.position)
        if end<0:fail(self.fmt,'missing component name and grid records.')
        row=self.data[self.position:end];self.position=end+1
        if not row or len(row.encode())>255:fail(self.fmt,'a component name exceeds the native reader buffer.')
        return row


class Records:
    """Four-byte native Fortran markers; required record boundaries are checked."""
    def __init__(self,raw,fmt,endian):self.raw=raw;self.fmt=fmt;self.endian=endian;self.position=0
    def read(self):
        start=self.position
        if start+8>len(self.raw):fail(self.fmt,'a required binary record is truncated.')
        size=struct.unpack_from(self.endian+'i',self.raw,start)[0]
        if size<0 or start+8+size>len(self.raw):fail(self.fmt,'a binary record length exceeds the available file data.')
        if struct.unpack_from(self.endian+'i',self.raw,start+4+size)[0]!=size:fail(self.fmt,'binary record markers do not match.')
        self.position=start+8+size;return memoryview(self.raw)[start+4:start+4+size]


def binary_records(raw,fmt,header):
    if len(raw)>=4:
        for endian in ['<','>']:
            if struct.unpack_from(endian+'i',raw)[0]==header:return Records(raw,fmt,endian)
    return None


def finite_binary(data,fmt,endian,precision):
    width=struct.calcsize(precision)
    if len(data)%width:fail(fmt,'a coordinate record is incomplete.')
    if any(not math.isfinite(value[0]) for value in struct.iter_unpack(endian+precision,data)):
        fail(fmt,'expected finite binary coordinates and normals.')


def hermite(raw,fmt):
    scan=Scanner(raw,fmt)
    header=scan.take(r'HERMITE\s+INPUT\s+FILE\s+NUMBER\s+OF\s+COMPONENTS\s*=\s*([+-]?[0-9]+)')
    components=count(header.group(1),fmt)
    if components>len(raw)//20:fail(fmt,'component count exceeds the available grid records.')
    for _ in range(components):
        scan.line()
        scan.take(r'GROUP\s+NUMBER\s*=');scan.integer()
        scan.take(r'TYPE\s*=');scan.integer()
        scan.take(r'CROSS\s+SECTIONS\s*=');rows=scan.integer(True)
        scan.take(r'PTS/CROSS\s+SECTION\s*=');cols=scan.integer(True)
        if 3*rows*cols>len(scan.data)-scan.position:fail(fmt,'grid dimensions exceed the available coordinate records.')
        for _ in range(3*rows*cols):scan.scalar(True)


def cart3d(raw):
    fmt='CART3D';records=binary_records(raw,fmt,8)
    if records:
        header=records.read();nodes,tris=struct.unpack(records.endian+'2i',header)
        if nodes<3 or tris<1:fail(fmt,'provide at least three nodes and one triangle.')
        coords=records.read()
        if len(coords) not in (12*nodes,24*nodes):fail(fmt,'node count does not match the binary coordinates.')
        finite_binary(coords,fmt,records.endian,'f' if len(coords)==12*nodes else 'd')
        triangles=records.read()
        if len(triangles)!=12*tris:fail(fmt,'triangle count does not match binary connectivity.')
        for value, in struct.iter_unpack(records.endian+'i',triangles):
            if not 1<=value<=nodes:fail(fmt,'a triangle references a node outside this file.')
        # Native optional tags may be absent, partial or malformed; in that
        # case the reader intentionally discards them, retaining the geometry.
    else:
        scan=Scanner(raw,fmt);nodes=scan.integer(True);tris=scan.integer(True)
        if nodes<3:fail(fmt,'provide at least three nodes and one triangle.')
        if 3*nodes+3*tris>len(scan.data)-scan.position:fail(fmt,'counts exceed the available coordinate and connectivity records.')
        for _ in range(3*nodes):scan.scalar(True)
        for _ in range(3*tris):
            if not 1<=scan.integer()<=nodes:fail(fmt,'a triangle references a node outside this file.')
        # Preserve native optional-tag parsing and ignored trailing records.


def plot3d(raw):
    fmt='PLOT3D_WIRE';records=binary_records(raw,fmt,4)
    if records:
        header=records.read();blocks=struct.unpack(records.endian+'i',header)[0]
        if blocks<1:fail(fmt,'the file needs a positive block count.')
        dims=records.read()
        if len(dims) not in (8*blocks,12*blocks):fail(fmt,'block count does not match the binary dimension record.')
        if 16*blocks>len(raw)-records.position:fail(fmt,'block count exceeds the available complete binary coordinate records.')
        ndim=len(dims)//(4*blocks);dimensions=list(struct.iter_unpack(records.endian+str(ndim)+'i',dims))
        if any(n<1 for d in dimensions for n in d):fail(fmt,'all grid dimensions must be positive.')
        sizes=[d[0]*d[1]*(d[2] if ndim==3 else 1) for d in dimensions]
        first=records.read()
        if len(first)%sizes[0]:fail(fmt,'the first block has an incomplete coordinate layout.')
        width=len(first)//sizes[0]
        layouts={8:(2,'f'),12:(3,'f'),24:(3,'d'),28:(3,'d')}
        if width==16:
            tags=[n[0] for n in struct.iter_unpack(records.endian+'i',first[12*sizes[0]:])]
            coords,precision=(3,'f') if any(n>0 for n in tags) and all(0<=n<=blocks for n in tags) else (2,'d')
        elif width in layouts:coords,precision=layouts[width]
        else:fail(fmt,'unsupported native binary coordinate layout.')
        for i,size in enumerate(sizes):
            data=first if i==0 else records.read()
            if len(data)!=width*size:fail(fmt,'a block dimension does not match its complete binary record.')
            finite_binary(data[:coords*struct.calcsize(precision)*size],fmt,records.endian,precision)
    else:
        scan=Scanner(raw,fmt);blocks=scan.integer(True)
        if 3*blocks>len(scan.data)-scan.position:fail(fmt,'block count exceeds the available grid dimensions.')
        dimensions=[tuple(scan.integer(True) for _ in range(3)) for _ in range(blocks)]
        total=sum(a*b*c for a,b,c in dimensions)
        if 2*total>len(scan.data)-scan.position:fail(fmt,'grid dimensions exceed the available coordinates.')
        values=0
        while True:
            match=re.compile(r'\s*('+NUMBER+')',re.ASCII).match(scan.data,scan.position)
            if not match:
                if re.match(r'\s*[+-]?(?:nan|inf)',scan.data[scan.position:],re.ASCII|re.IGNORECASE):fail(fmt,'expected finite coordinate records.')
                break
            number(match.group(1),fmt);scan.position=match.end();values+=1
        arrays=values//total if values%total==0 and 2<=values//total<=4 else 3
        if values<arrays*total:fail(fmt,'a grid coordinate block is truncated.')


def stl(raw):
    fmt='STL'
    binary=len(raw)>=84 and (b'\0' in raw[:84] or 0<struct.unpack_from('<i',raw,80)[0]<=(len(raw)-84)//50)
    if binary:
        triangles=struct.unpack_from('<i',raw,80)[0]
        if triangles<1 or 84+50*triangles>len(raw):fail(fmt,'triangle count exceeds the available complete binary facets.')
        for i in range(triangles):finite_binary(memoryview(raw)[84+50*i:132+50*i],fmt,'<','f')
        # The native detector stops at a NUL in fgets/strlen. A high-bit byte
        # at the start of its ignored 80-byte header reliably selects binary;
        # every normal, vertex, attribute and trailing byte stays untouched.
        return b'\x80'+raw[1:]
    data=text(raw,fmt)
    if '\0' in data:fail(fmt,'unexpected NUL in ASCII facet records.')
    lines=[line.strip(SPACE) for line in data.split('\n') if line.strip(SPACE)]
    output=[];i=0;facets=0
    while i<len(lines):
        if re.fullmatch(r'(?:solid|endsolid)(?:[ \t].*)?',lines[i]):
            output.append(lines[i].split()[0]);i+=1;continue
        if i+7>len(lines):fail(fmt,'an ASCII facet is truncated.')
        for offset,prefix in [(0,r'facet\s+normal'),(2,'vertex'),(3,'vertex'),(4,'vertex')]:
            match=re.fullmatch(prefix+r'\s+('+NUMBER+r')\s+('+NUMBER+r')\s+('+NUMBER+r')',lines[i+offset],re.ASCII)
            if not match:fail(fmt,'each ASCII facet needs a normal and three finite vertex records.')
            for value in match.groups():
                if abs(number(value,fmt))>3.4028234663852886e38:fail(fmt,'a facet value exceeds the native float range.')
            row=('facet normal' if offset==0 else 'vertex')+' '+' '.join(match.groups())
            if len(row.encode())>253:fail(fmt,'a facet record exceeds the native reader buffer; use shorter numeric records or binary STL.')
            output.append(row)
            if offset==0:
                if not re.fullmatch(r'outer\s+loop',lines[i+1],re.ASCII):fail(fmt,'missing outer loop in an ASCII facet.')
                output.append('outer loop')
        if lines[i+5]!='endloop' or lines[i+6]!='endfacet':fail(fmt,'missing facet closing records.')
        output.extend(['endloop','endfacet']);i+=7;facets+=1
    if not facets:fail(fmt,'the file contains no complete facets.')
    # Canonical record separators avoid the native fixed-line reader's blank
    # line and missing-final-newline defects. Coordinate lexemes are retained.
    return ('\n'.join(output)+'\n').encode()


def validate(raw,fmt):
    validators={'POINTS':points,'NASCART':nascart,'BEM':bem,'VSP_V2':legacy,'STL':stl,'CART3D':cart3d,'PLOT3D_WIRE':plot3d}
    if fmt in ('XSEC_MESH','XSEC_WIRE'):hermite(raw,fmt);return raw
    prepared=validators[fmt](raw) if fmt in validators else None
    return raw if prepared is None else prepared
