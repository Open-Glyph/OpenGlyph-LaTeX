"""Black KAGE vectors -> a real CFF OpenType font, never raster tracing."""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

def svg_commands(svg):
    from fontTools.svgLib.path import parse_path
    from fontTools.pens.recordingPen import RecordingPen
    groups=[];root=ET.fromstring(svg)
    allowed={'svg':{'version','baseProfile','viewBox','width','height'},'g':{'fill'},'path':{'d','fill'},'polygon':{'points','fill'}}
    for el in root.iter():
        tag=el.tag.rsplit('}',1)[-1]
        if tag not in allowed or set(el.attrib)-allowed[tag]:raise ValueError('Unexpected KAGE SVG element')
        if el.get('fill','black') not in ('black','#000','#000000'):raise ValueError('Only opaque black fills are supported')
        pen=RecordingPen()
        if tag=='path':parse_path(el.get('d',''),pen)
        elif tag=='polygon':
            coords=[float(n) for n in el.get('points','').replace(',',' ').split()]
            if len(coords)%2 or len(coords)<6:raise ValueError('Incomplete polygon')
            points=list(zip(coords[::2],coords[1::2]));pen.moveTo(points[0])
            for point in points[1:]:pen.lineTo(point)
            pen.closePath()
        if pen.value:
            if any(name=='endPath' for name,_ in pen.value):raise ValueError('Open contour')
            if any(not math.isfinite(v) for _,pts in pen.value for pt in pts for v in pt):raise ValueError('Nonfinite outline')
            groups.append(pen.value)
    if not groups:raise ValueError('Empty glyph')
    return groups

def outline(svg):
    import pathops
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    groups=svg_commands(svg);bounds=BoundsPen(None)
    for group in groups:
        for name,points in group:getattr(bounds,name)(*points)
    if not bounds.bounds:raise ValueError('Empty glyph bounds')
    x0,y0,x1,y1=bounds.bounds
    if x1<=x0 or y1<=y0:raise ValueError('Zero-area glyph')
    scale=900/max(x1-x0,y1-y0);ox=(1000-(x1-x0)*scale)/2;oy=-120+(1000-(y1-y0)*scale)/2
    tx=ox-x0*scale;ty=oy+y1*scale;combined=None
    for group in groups:
        path=pathops.Path();path.fillType=pathops.FillType.WINDING;pen=path.getPen()
        for name,points in group:getattr(pen,name)(*tuple((x*scale+tx,-y*scale+ty) for x,y in points))
        combined=path if combined is None else pathops.op(combined,path,pathops.PathOp.UNION)
    recording=RecordingPen();combined.draw(recording)
    pen=T2CharStringPen(1000,None,roundTolerance=0)
    for name,points in recording.value:getattr(pen,name)(*points)
    charstring=pen.getCharString();charstring.compile()
    return dict(charstring=charstring,left_side_bearing=round(ox),outline_sha256=hashlib.sha256(charstring.bytecode).hexdigest(),
        source_bounds=list(bounds.bounds),transform_to_font=[scale,0,0,-scale,tx,ty])

def write_font(rows,path,family,*,license_text,license_url):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    order=['.notdef','space'];chars={n:T2CharStringPen(w,None).getCharString() for n,w in [('.notdef',1000),('space',250)]}
    cmap={32:'space'};metrics={'.notdef':(1000,0),'space':(250,0)}
    for i,(key,row) in enumerate(sorted(rows.items()),1):
        cp=row['codepoint'];name='g'+str(i)
        if cp in cmap:raise ValueError('Duplicate codepoint')
        order.append(name);chars[name]=row['charstring'];cmap[cp]=name;metrics[name]=(1000,row['left_side_bearing'])
    font=FontBuilder(1000,isTTF=False);font.setupGlyphOrder(order);font.setupCharacterMap(cmap)
    font.setupHorizontalMetrics(metrics);font.setupHorizontalHeader(ascent=880,descent=-120)
    font.setupNameTable(dict(familyName=family,styleName='Regular',uniqueFontIdentifier=family+'-Regular',fullName=family+' Regular',psName=family+'-Regular',
        copyright='Glyph outlines: GlyphWiki contributors; assembly: OpenGlyph contributors.',licenseDescription=license_text,licenseInfoURL=license_url))
    font.setupOS2(sTypoAscender=880,sTypoDescender=-120,usWinAscent=1000,usWinDescent=200,fsType=0)
    font.setupPost();font.setupCFF(family+'-Regular',dict(FullName=family+' Regular',FamilyName=family,Weight='Regular'),chars,{})
    font.font.recalcTimestamp=False;font.font['head'].created=font.font['head'].modified=2082844800
    font.save(path)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
