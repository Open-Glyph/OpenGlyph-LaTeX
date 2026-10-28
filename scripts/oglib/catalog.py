"""Read the licensed, pinned GlyphWiki program subset; no IDS guessing."""
from __future__ import annotations
import gzip
import hashlib
import json
import re

NAME=re.compile(r'[a-z0-9_][a-z0-9_.-]*(?:@[0-9]+)?\Z')

def hash_json(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=True,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()

def refs(data):
    for fragment in data.split('$'):
        fields=fragment.split(':')
        if fields[0]=='99':
            if len(fields)<8 or not fields[7]:raise ValueError('Incomplete component reference')
            yield fields[7]

class Catalog:
    def __init__(self,path):
        self.table={}
        with gzip.open(path,'rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line);name=row['name'];data=row['kage_data']
                if not NAME.fullmatch(name) or not isinstance(data,str):raise ValueError('Invalid catalogue entry')
                if name in self.table and self.table[name]!=data:raise ValueError('Conflicting component: '+name)
                self.table[name]=data
    def get(self,name):return self.table.get(name)
    def resolve(self,query):
        expected=None
        if not isinstance(query,str):raise ValueError('Glyph reference must be an ASCII string')
        if query.startswith('gwk:'):
            try:_,expected,query=query.split(':',2)
            except ValueError:raise ValueError('Invalid pinned reference') from None
            if not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('Invalid content hash')
        if query.startswith('ebag:'):query='ebag_'+query[5:]
        if not NAME.fullmatch(query):raise ValueError('Use a catalogue component name or ebag:sNNN-NNN')
        closure={};visiting=set();stack=[(query,False)]
        while stack:
            name,leaving=stack.pop()
            if leaving:visiting.remove(name);continue
            if name in visiting:raise ValueError('Component cycle: '+name)
            if name in closure:continue
            data=self.table.get(name)
            if not data:raise ValueError('Missing exact component: '+name)
            closure[name]=data;visiting.add(name);stack.append((name,True))
            stack.extend((child,False) for child in reversed(list(refs(data))))
        digest=hash_json(closure)
        if expected and digest!=expected:raise ValueError('Pinned component has changed')
        return dict(name=query,ref=f'gwk:{digest}:{query}',closure_sha256=digest,table=closure)
