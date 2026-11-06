from pathlib import Path
import argparse,hashlib,json,sys
from collections import Counter
from PIL import Image
from integrity import GENERATOR_SHA, generator_hash, verify_fonts, verify
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--generator-src',type=Path,required=True)
args=parser.parse_args()
p=args.output.resolve()
verify_fonts(p)
if generator_hash(args.generator_src.resolve()) != GENERATOR_SHA:
 raise ValueError("generator tree hash differs from frozen experiment")
sys.path.insert(0,str(args.generator_src.resolve()))
from hocrsyngen.generator import _generate_manifest_and_documents,write_manifest
from hocrsyngen.line_annotations import write_line_annotations
specs=[('train',24,26110701,'alef'),('validation',8,26110702,'alef'),('test',12,26110703,'noto')]
all_rows={};stats={}
for split,count,seed,font in specs:
 out=p/'pages'/split
 manifest,docs=_generate_manifest_and_documents(count,seed,out,['printed_letter'],font_manifest_path=p/'inputs/fonts'/f'{font}.yaml',text_corpus_path=p/'inputs'/f'{split}.txt',record_line_geometry=True,plain_evaluation=True,emit_paired_render=True)
 manifest_path=write_manifest(manifest,out);write_line_annotations(manifest,docs,manifest_path)
 target=p/'lines'/split;target.mkdir(parents=True,exist_ok=True);rows=[];rejected=Counter()
 for doc in docs:
  if doc.truncated_segments:rejected['page_truncated']+=1;continue
  lines=doc.lines or ();image=Image.open(doc.path).convert('RGB')
  for i,line in enumerate(lines):
   if line.region!='body':continue
   if line.occluded or line.clipped:rejected['clipped_or_overlapping']+=1;continue
   xs=[t[0] for t in line.polygon];ys=[t[1] for t in line.polygon]; x0,x1=min(xs),max(xs);y0,y1=min(ys),max(ys)
   if x1-x0<10 or y1-y0<10:rejected['degenerate']+=1;continue
   if any(min(x1,max(t[0] for t in other.polygon))>max(x0,min(t[0] for t in other.polygon)) and min(y1,max(t[1] for t in other.polygon))>max(y0,min(t[1] for t in other.polygon)) for j,other in enumerate(lines) if i!=j):rejected['bbox_overlap']+=1;continue
   crop=image.crop((x0,y0,x1+1,y1+1)); scale=[0.8,1.0,1.2][(doc.sample_index+i)%3]
   if scale!=1.0:crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
   f=target/f'{doc.sample_id}-{i:03}.png';crop.save(f);f.with_suffix('.gt.txt').write_text(line.text,encoding='utf8');rows.append({'image':str(f.relative_to(p)),'label':str(f.with_suffix('.gt.txt').relative_to(p)),'image_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'label_sha256':hashlib.sha256(f.with_suffix('.gt.txt').read_bytes()).hexdigest(),'scale':scale,'page':doc.sample_id})
 (p/f'{split}.lst').write_text(''.join(str((p/r['image']).resolve())+'\n' for r in rows));all_rows[split]=rows;stats[split]={'pages':count,'lines':len(rows),'rejected':dict(rejected),'scales':dict(Counter(str(r['scale']) for r in rows))}
(p/'line-freeze.json').write_text(json.dumps({'splits':all_rows,'statistics':stats},ensure_ascii=False,indent=2)+'\n');(p/'line-freeze.sha256').write_text(hashlib.sha256((p/'line-freeze.json').read_bytes()).hexdigest()+'\n');verify(p);print(json.dumps(stats,indent=2))
