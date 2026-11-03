from pathlib import Path
import argparse,subprocess,os,time,json,signal,hashlib
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--base-model',type=Path,required=True)
parser.add_argument('--ketos',type=Path,required=True)
args=parser.parse_args()
p=args.output.resolve();out=p/'run-page';out.mkdir(exist_ok=False)
base=args.base_model.resolve()
cmd=[str(args.ketos.resolve()),'-d','cpu','--threads','4','--workers','0','--seed','42','--deterministic','train','-f','page','-t',str(p/'train-xml.lst'),'-e',str(p/'validation-xml.lst'),'-i',str(base),'-o',str(out),'--weights-format','safetensors','--reorder','--base-dir','R','--resize','fail','-B','4','-r','0.0001','-q','fixed','-N','2','--no-augment']
(p/'train-page-command.json').write_text(json.dumps({'argv':cmd,'timeout_seconds':900,'max_output_bytes':1073741824},indent=2)+'\n')
env=dict(os.environ,OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4',PYTHONUNBUFFERED='1');start=time.monotonic();reason='completed'
with (p/'train-page.log').open('w') as log:
 proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
 while proc.poll() is None:
  total=sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
  if time.monotonic()-start>900 or total>1073741824:
   reason='timeout' if total<=1073741824 else 'output_limit';os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   break
  time.sleep(1)
rc=proc.wait();elapsed=time.monotonic()-start
files=[{'path':str(f.relative_to(p)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in out.rglob('*') if f.is_file() and f.suffix in ('.safetensors','.ckpt')]
result={'exit_code':rc,'reason':reason,'elapsed_seconds':round(elapsed,2),'files':files,'total_output_bytes':sum(f.stat().st_size for f in out.rglob('*') if f.is_file())};(p/'train-page-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
