from pathlib import Path
import argparse,json,subprocess,os,time,xml.etree.ElementTree as ET,hashlib,sys
from integrity import BASE_SHA,sha,verify,tool_info
def read_line(f):
 root=ET.parse(f).getroot();nodes=[x for x in root.iter() if x.tag.endswith('}TextLine')]
 if len(nodes)!=1: raise ValueError('expected one line')
 eq=[x for x in nodes[0] if x.tag.endswith('}TextEquiv')]
 if len(eq)!=1: raise ValueError('expected one text equivalent')
 v=[x.text or '' for x in eq[0] if x.tag.endswith('}Unicode')]
 if len(v)!=1: raise ValueError('expected one Unicode value')
 return v[0]
def dist(a,b):
 d=list(range(len(b)+1))
 for i,x in enumerate(a,1):
  new=[i]
  for j,y in enumerate(b,1):new.append(min(new[-1]+1,d[j]+1,d[j-1]+(x!=y)))
  d=new
 return d[-1]

def aggregate(rows, exit_code, expected):
 ok=[x for x in rows if x['status']=='ok']
 result={'exit_code':exit_code,'expected':expected,'valid':len(ok)}
 if exit_code == 0 and len(rows) == expected and len(ok) == expected:
  result.update({'word_edits':sum(x['word_edits'] for x in ok),'reference_words':sum(x['reference_words'] for x in ok),'char_edits':sum(x['char_edits'] for x in ok),'reference_chars':sum(x['reference_chars'] for x in ok)})
 return result

def finalize(results):
 incomplete=any(x.get('exit_code') != 0 or x.get('valid') != x.get('expected') for x in results.values())
 if incomplete:
  for result in results.values():
   for key in ('word_edits','reference_words','char_edits','reference_chars'):
    result.pop(key,None)
 return incomplete

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--base-model',type=Path,required=True)
 parser.add_argument('--kraken',type=Path,required=True)
 args=parser.parse_args()
 p=args.output.resolve()
 verify(p,require_xml=True)
 if sha(args.base_model)!=BASE_SHA: raise ValueError("base model hash mismatch")
 tool=tool_info(args.kraken,"kraken")
 r=json.loads((p/'train-page-result.json').read_text());selected=[f for f in r['files'] if Path(f['path']).name.startswith('best_') and f['path'].endswith('.safetensors')]
 if r['exit_code']!=0 or r['reason']!='completed' or len(selected)!=1: raise ValueError('expected completed training and one best model')
 weights=[p/selected[0]['path']]
 if not weights[0].resolve().is_relative_to(p/'run-page') or sha(weights[0])!=selected[0]['sha256']: raise ValueError('trained model hash mismatch')
 base=args.base_model.resolve();src=[Path(x) for x in (p/'test-xml.lst').read_text().splitlines()];env=dict(os.environ,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4');results={};predroot=p/'raw-predictions';predroot.mkdir(exist_ok=True)
 for label,model in [('base',base),('fine_tuned',weights[0])]:
  out=predroot/label;out.mkdir(exist_ok=False);pairs=[]
  for f in src:pairs.extend(['-i',str(f),str(out/f.name)])
  cmd=[str(args.kraken.resolve()),'-d','cpu','-x','-f','page',*pairs,'ocr','-m',str(model),'--reorder','--base-dir','R','--num-line-workers','0'];start=time.monotonic()
  try:
   result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180,env=env);(p/f'{label}-raw.log').write_text(result.stdout)
   rows=[]
   for f in src:
    target=out/f.name
    if not target.exists():rows.append({'id':f.stem,'status':'missing'});continue
    try:
     a=read_line(f);b=read_line(target);rows.append({'id':f.stem,'status':'ok','reference':a,'prediction':b,'word_edits':dist(a.split(),b.split()),'reference_words':len(a.split()),'char_edits':dist(a,b),'reference_chars':len(a)})
    except (ValueError,ET.ParseError):rows.append({'id':f.stem,'status':'invalid'})
   (out/'rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
   results[label]=aggregate(rows,result.returncode,len(src))
   results[label].update({'elapsed_seconds':round(time.monotonic()-start,2),'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest()})
  except subprocess.TimeoutExpired:results[label]={'error':'timeout','expected':len(src),'valid':0}
 incomplete=finalize(results)
 (p/'kraken-tool.json').write_text(json.dumps(tool,indent=2)+'\n')
 (predroot/'summary.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
 if incomplete:
  sys.exit('incomplete evaluation: aggregate scores are not valid')

if __name__ == "__main__":
 main()
