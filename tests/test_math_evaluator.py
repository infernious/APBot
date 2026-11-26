import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from utils.math_worker import calculate, MathError
from utils.math_evaluator import Evaluator

@pytest.mark.parametrize('expression,expected',[
 ('1+1=2',2),('e^(pi*i)+3',2),('sum(k,k,1,4)',10),('prod(k,k,1,4)',24),
 ('sum(k^2,k,1,3)+prod(k,k,1,3)+5',25),('integral(2*x,x,0,3)',9),
 ('integral(7*x^6,x,0,1)+6',7),('int(cos(x),x,0,pi/2)',1),('diff(x^2,x,3)',6),
 ('5!',120),('binomial(5,2)',10),('log(8,2)',3),('sin(pi/2)+4',5),('√(9)',3),
 ('2³×2',16),('−2+5',3),('2^3^2',512),('-2^2',-4),('(-2)^2',4),('2^-2=0.25',None),
 ('0.1+0.2+0.7',1),('sum(sum(k+j,j,1,2),k,1,2)',12),('abs(-15)',15),('floor(3.8)',3),('ceil(2.1)',3),
 ('2pi/pi',2),('2π/π',2),('2(3+4)',14),('3sin(pi/2)',3),
 ('integral(2x,x,0,3)',9),('diff(3x^2,x,2)',12),('sum(2k,k,1,4)',20),
 ('(1+2)(3+4)',21),('2sqrt(9)',6),('2pi',None),('1/2(4)',2),
 ('`2*3`',6),('` integral(2x,x,0,3) `',9),('`1+1=2`',2),
 ('integral(2x,x,0,3)+diff(3x^2,x,2)+2sin(pi/2)+e^(π*i)',22),
 ('integral(2x,x,0,3)+diff(3x^2,x,2)+2sin(pi/2)+e^(πi)',22),
 ('e^(πi)',-1),('ℯ^(πⅈ)',-1),('2π/π',2),('π/π',1),('2√(9)',6),('π²/π^2',1),
 ('sqrt(2)',None),('sqrt(-1)',None),('1.000000000000001',None),('1000000000001',None),('0',0),
])
def test_values(expression,expected):
    r=calculate(expression)
    assert r['ok'] and r['integer']==expected

@pytest.mark.parametrize('expression',[
 '1+1=3','1/0','sqrt(1/0)','tan(pi/2)','x+1','sum(k,k,1,201)','1000!', '2^101','1=1=1',
 '__import__("os")','open(1)','(1).__class__','[1,2]','lambda x: x','2x','a'*251,'sum(k,e,1,4)',
 'pii','2π3','1 2','1.2.3','2unknown(3)','2pi3','`1+1','1+1`','``1+1``','`hello`','factorial(-1)','log(0)','integral(1/x,x,-1,1)','2^^2','sum(k,k,4,1)',
])
def test_reject(expression):
    with pytest.raises(MathError): calculate(expression)

def test_real_worker():
    async def run():
        e=Evaluator()
        assert (await e.evaluate('e^(pi*i)+3'))['integer']==2
        assert (await e.evaluate('integral(2*x,x,0,3)'))['integer']==9
        assert not (await e.evaluate('1+1=3'))['ok']
        assert (await e.evaluate('12'))['integer']==12
        assert not (await e.evaluate('__import__("os")'))['ok']
        assert (await e.evaluate('`2(3+4)`'))['integer']==14
        assert (await e.evaluate('diff(3x^2,x,2)'))['integer']==12
        assert not (await e.evaluate('1 2'))['ok']
        assert (await e.evaluate('integral(2x,x,0,3)+diff(3x^2,x,2)+2sin(pi/2)+e^(πi)'))['integer']==22
        assert (await e.evaluate('2³×2'))['integer']==16
        assert (await e.evaluate('√(9)'))['integer']==3
        assert e.active==0
    asyncio.run(run())


@pytest.mark.parametrize('encoding',['cp1252','ascii'])
def test_worker_utf8_pipe_with_non_utf8_default(encoding):
    # Without -I solely to simulate a Windows/non-UTF-8 default stdin encoding.
    # The real Evaluator still launches Python with -I and -B.
    path=Path(__file__).resolve().parents[1]/'src'/'utils'/'math_worker.py'
    env=dict(os.environ, PYTHONIOENCODING=encoding, PYTHONUTF8='0')
    result=subprocess.run([sys.executable,str(path)],input='e^(πi)+3'.encode('utf-8'),
                          capture_output=True,env=env,timeout=6,check=True)
    assert json.loads(result.stdout)['integer']==2


def test_worker_reject_invalid_utf8():
    path=Path(__file__).resolve().parents[1]/'src'/'utils'/'math_worker.py'
    result=subprocess.run([sys.executable,'-I','-B',str(path)],input=b'\xff',
                          capture_output=True,timeout=6,check=True)
    assert not json.loads(result.stdout)['ok']
