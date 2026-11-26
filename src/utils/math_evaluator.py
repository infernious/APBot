"""Async interface shared by /test and the counting channel."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys

MAX_COUNT=10**12
WORKER=Path(__file__).with_name('math_worker.py').resolve()

class Evaluator:
    def __init__(self):
        self.active=0

    async def evaluate(self, expression):
        text=expression.strip()
        if not text or len(text)>250:
            return {'ok':False,'error':'Use 1–250 characters.'}
        # Exact decimal integer fast path; same bound as symbolic evaluation.
        if re.fullmatch(r'[0-9]{1,20}',text):
            n=int(text)
            return {'ok':True,'result':str(n),'integer':n if n<=MAX_COUNT else None,'approximation':None}
        if self.active>=2:
            return {'ok':False,'error':'Calculator busy. Try again shortly.','unavailable':True}
        self.active+=1
        proc=None
        try:
            # Do not pass bot tokens or database credentials from the environment.
            env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','LANG','LC_ALL') if k in os.environ}
            env.update({'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
            proc=await asyncio.create_subprocess_exec(sys.executable,'-I','-B',str(WORKER),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,env=env,cwd=str(WORKER.parent))
            out,_=await asyncio.wait_for(proc.communicate(text.encode('utf-8')),timeout=6)
            if proc.returncode!=0 or len(out)>4096:
                return {'ok':False,'error':'Expression exceeded the evaluation limit or worker unavailable.','unavailable':True}
            result=json.loads(out)
            if not isinstance(result,dict) or 'ok' not in result: raise ValueError('Invalid worker response')
            return result
        except asyncio.TimeoutError:
            return {'ok':False,'error':'Expression took too long to evaluate.','unavailable':True}
        except (OSError,ValueError,NotImplementedError):
            return {'ok':False,'error':'Calculator unavailable. Try again later.','unavailable':True}
        finally:
            try:
                if proc is not None and proc.returncode is None:
                    try: proc.kill()
                    except ProcessLookupError: pass
                    await proc.wait()
            finally:
                self.active-=1
