"""Summarize explicit native log messages without computing solver or mesh quality."""
import hashlib,re
from pathlib import Path
CACHE={}
PATTERNS=[(re.compile(r'^ERROR\s*:',re.I),'error'),(re.compile(r'^WARNING\s*:',re.I),'warning'),
          (re.compile(r'^NOT Water Tight\b',re.I),'review'),(re.compile(r'^Invalid reason\s+-?\d+\s*$'),'review'),
          (re.compile(r'^No Surfaces To Mesh\s*$',re.I),'review')]


def scan(path,max_groups=40,max_message=1000):
    path=Path(path)
    if path.is_symlink() or not path.is_file():return dict(available=False,messages=[],totalMessages=0)
    groups={};total=omitted=0;abbreviated=False
    with path.open(encoding='utf-8',errors='replace') as stream:
        for line_number,raw in enumerate(stream,1):
            text=raw.strip();severity=next((s for regex,s in PATTERNS if regex.search(text)),None)
            if severity is None:continue
            total+=1;key=hashlib.sha256(text.encode()).digest()
            if key in groups:groups[key]['count']+=1
            elif len(groups)<max_groups:
                groups[key]=dict(severity=severity,text=text[:max_message],count=1,firstLine=line_number)
                abbreviated|=len(text)>max_message
            else:omitted+=1
    return dict(available=True,messages=list(groups.values()),totalMessages=total,omittedOccurrences=omitted,abbreviated=abbreviated,source='engine.log')


def saved(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():return dict(available=False,messages=[],totalMessages=0)
    stat=path.stat();key=(str(path.resolve()),stat.st_size,stat.st_mtime_ns)
    if key not in CACHE:
        if len(CACHE)>=64:CACHE.pop(next(iter(CACHE)))
        CACHE[key]=scan(path)
    return CACHE[key]
