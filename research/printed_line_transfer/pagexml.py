from pathlib import Path
import argparse
import hashlib,json
from integrity import verify
from xml.etree import ElementTree as ET
from PIL import Image
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
p=parser.parse_args().output.resolve()
ns='http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15'; ET.register_namespace('',ns)
def tag(s):return '{%s}%s'%(ns,s)
groups=verify(p)
for split in ['train','validation','test']:
 imgs=[p / row['image'] for row in groups[split]]; xmls=[]
 for img in imgs:
  w,h=Image.open(img).size;root=ET.Element(tag('PcGts'));meta=ET.SubElement(root,tag('Metadata'));ET.SubElement(meta,tag('Creator')).text='synthetic-line-smoke';ET.SubElement(meta,tag('Created')).text='1970-01-01T00:00:00';ET.SubElement(meta,tag('LastChange')).text='1970-01-01T00:00:00'
  page=ET.SubElement(root,tag('Page'),imageFilename=img.name,imageWidth=str(w),imageHeight=str(h),readingDirection='right-to-left');region=ET.SubElement(page,tag('TextRegion'),id='r0',readingDirection='right-to-left');coords=f'0,0 {w-1},0 {w-1},{h-1} 0,{h-1}';ET.SubElement(region,tag('Coords'),points=coords);line=ET.SubElement(region,tag('TextLine'),id='l0',readingDirection='right-to-left');ET.SubElement(line,tag('Coords'),points=coords);ET.SubElement(line,tag('Baseline'),points=f'1,{round(h*.8)} {w-2},{round(h*.8)}');equiv=ET.SubElement(line,tag('TextEquiv'));ET.SubElement(equiv,tag('Unicode')).text=img.with_suffix('.gt.txt').read_text();dest=img.with_suffix('.xml');ET.ElementTree(root).write(dest,encoding='utf-8',xml_declaration=True);xmls.append(dest)
 (p/f'{split}-xml.lst').write_text(''.join(str(x)+'\n' for x in xmls))

xmls=sorted((p/'lines').rglob('*.xml'))
(p/'pagexml-hashes.json').write_text(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in xmls},indent=2)+'\n')
verify(p,require_xml=True)
