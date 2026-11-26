"""Bounded symbolic calculator. Never interpret user input as Python code."""
import json
import re
import sys

MAX_LENGTH = 250
MAX_COUNT = 10**12
TOKEN = re.compile(r'\s*(?:(\d+(?:\.\d+)?|\.\d+)|([A-Za-z][A-Za-z0-9]*)|(\*\*|[+*/^(),!=\-]))', re.ASCII)
FUNCTIONS = {'sqrt','abs','sin','cos','tan','asin','acos','atan','log','ln','exp','floor','ceil','factorial','binomial','sum','prod','integral','int','diff'}
CONSTANTS = {'pi','e','i'}
VARIABLES = set('abcdefghjklmnopqrstuvwxyz') - CONSTANTS

class MathError(ValueError):
    pass


def normalize(text):
    text = text.strip()
    # Allow one matching pair of Discord inline-code backticks.
    if text.startswith('`') and text.endswith('`'):
        text = text[1:-1].strip()
    text = text.translate(str.maketrans({'π':' pi ','×':'*','÷':'/','−':'-','√':' sqrt ','ℯ':' e ','ⅈ':' i '}))
    supers = '⁰¹²³⁴⁵⁶⁷⁸⁹'
    text = re.sub(f'[{supers}]+', lambda m: '^'+m.group().translate(str.maketrans(supers,'0123456789')), text)
    return text.strip()


class Parser:
    def __init__(self, text):
        if len(text) > MAX_LENGTH:
            raise MathError('Expression exceeds 250 characters.')
        text = normalize(text)
        self.tokens = []
        pos = 0
        while pos < len(text):
            m = TOKEN.match(text, pos)
            if not m:
                raise MathError('Unsupported syntax. See /count help.')
            self.tokens.append(next(g for g in m.groups() if g is not None))
            pos = m.end()
        # Insert explicit multiplication tokens, never evaluate source code.
        # Known function names followed by '(' remain function calls.
        expanded = []
        for token in self.tokens:
            if expanded:
                prev = expanded[-1]
                prev_number = bool(re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)', prev))
                next_number = bool(re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)', token))
                prev_value = prev_number or prev in CONSTANTS or prev in VARIABLES or prev in (')', '!')
                next_name = token in CONSTANTS or token in VARIABLES or token in FUNCTIONS
                if prev_value and (next_name or token == '(' or (next_number and prev in (')', '!'))):
                    expanded.append('*')
            expanded.append(token)
        self.tokens = expanded
        if not self.tokens or len(self.tokens) > 120:
            raise MathError('Empty or overly complex expression.')
        self.tokens.append('')
        self.pos = 0

    def peek(self): return self.tokens[self.pos]
    def take(self):
        t = self.peek()
        if not t: raise MathError('Unexpected end of expression.')
        self.pos += 1
        return t
    def expect(self,t):
        if self.take()!=t: raise MathError(f'Expected {t}.')

    def expr(self, minimum=0, depth=0):
        if depth > 24: raise MathError('Expression nesting limit exceeded.')
        t = self.take()
        if t in ('+','-'):
            node = ('unary',t,self.expr(30,depth+1))
        elif t == '(':
            node = self.expr(0,depth+1); self.expect(')')
        elif re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)',t):
            if len(t)>20: raise MathError('Numeric literal too large.')
            node = ('number',t)
        elif t in FUNCTIONS and self.peek()=='(':
            self.take(); args=[]
            if self.peek()!=')':
                while True:
                    args.append(self.expr(0,depth+1))
                    if self.peek()!=',': break
                    self.take()
            self.expect(')'); node=('call',t,args)
        elif t in CONSTANTS or t in VARIABLES:
            node=('name',t)
        else:
            raise MathError('Unknown name or unsupported syntax.')
        while True:
            op=self.peek()
            if op=='!' and minimum<=50:
                self.take(); node=('call','factorial',[node]); continue
            prec={'+':10,'-':10,'*':20,'/':20,'^':40,'**':40}.get(op,-1)
            if prec<minimum: break
            self.take()
            node=('binary',op,node,self.expr(prec if prec==40 else prec+1,depth+1))
        return node

    def parse(self):
        left=self.expr(); right=None
        if self.peek()=='=':
            self.take(); right=self.expr()
        if self.peek(): raise MathError('Unexpected token. Check multiplication, parentheses and function arguments.')
        return left,right


def calculate(text):
    import sympy as s
    left,right=Parser(text).parse()
    constants={'pi':s.pi,'e':s.E,'i':s.I}
    calls={'sqrt':s.sqrt,'abs':s.Abs,'sin':s.sin,'cos':s.cos,'tan':s.tan,'asin':s.asin,'acos':s.acos,'atan':s.atan,'log':s.log,'ln':s.log,'exp':s.exp,'floor':s.floor,'ceil':s.ceiling}
    def guard(value):
        if value.has(s.zoo,s.nan,s.oo,-s.oo): raise MathError('Undefined or non-finite result.')
        if s.count_ops(value)>350: raise MathError('Intermediate expression too complex.')
        for atom in value.atoms(s.Rational):
            if int(atom.p).bit_length()>2048 or int(atom.q).bit_length()>2048: raise MathError('Intermediate number too large.')
        return value
    def bounded_int(value, limit):
        if value.is_Integer is not True or abs(value)>limit: raise MathError('Expected a bounded integer argument.')
        return int(value)
    def visit(node, env):
        kind=node[0]
        if kind=='number': return s.Rational(node[1])
        if kind=='name':
            if node[1] in constants: return constants[node[1]]
            if node[1] in env: return env[node[1]]
            raise MathError('Unbound variable. Use it inside sum, prod, integral or diff.')
        if kind=='unary':
            v=visit(node[2],env); return v if node[1]=='+' else -v
        if kind=='binary':
            op=node[1]; a=visit(node[2],env); b=visit(node[3],env)
            if op=='+': v=a+b
            elif op=='-': v=a-b
            elif op=='*': v=a*b
            elif op=='/':
                if b.is_zero is True: raise MathError('Division by zero.')
                v=a/b
            else:
                if b.is_number:
                    magnitude=s.Abs(b).evalf(12)
                    if magnitude.is_finite is not True or magnitude>100: raise MathError('Exponent magnitude exceeds 100.')
                v=a**b
            return guard(v)
        name,args=node[1:]
        if name in ('sum','prod','integral','int','diff'):
            count=3 if name=='diff' else 4
            if len(args)!=count or args[1][0]!='name' or args[1][1] not in VARIABLES:
                raise MathError(f'Use {name}(expression, variable, '+('point)' if count==3 else 'lower, upper)'))
            var=s.Dummy(args[1][1]); inner=dict(env); inner[args[1][1]]=var
            expr=visit(args[0],inner); lo=visit(args[2],env)
            if name=='diff': return guard(s.diff(expr,var).subs(var,lo))
            hi=visit(args[3],env)
            if name in ('sum','prod'):
                lo=bounded_int(lo,10000); hi=bounded_int(hi,10000)
                if hi<lo or hi-lo+1>200: raise MathError('Sum/product must contain 1–200 terms.')
                value=s.Integer(0 if name=='sum' else 1)
                for k in range(lo,hi+1):
                    term=guard(expr.subs(var,k)); value=guard(value+term if name=='sum' else value*term)
                return value
            if lo.is_real is not True or hi.is_real is not True or lo.is_finite is not True or hi.is_finite is not True:
                raise MathError('Integral bounds must be finite real numbers.')
            if lo.free_symbols or hi.free_symbols: raise MathError('Integral bounds must be numeric.')
            # Restrict to polynomials and elementary expressions that SymPy can solve within the worker limit.
            value=s.integrate(expr,(var,lo,hi))
            if value.has(s.Integral): raise MathError('Integral could not be evaluated exactly.')
            return guard(value)
        vals=[visit(x,env) for x in args]
        if name=='factorial':
            if len(vals)!=1: raise MathError('factorial takes one argument.')
            n=bounded_int(vals[0],200)
            if n<0: raise MathError('Factorial requires a nonnegative integer.')
            return guard(s.factorial(n))
        if name=='binomial':
            if len(vals)!=2: raise MathError('binomial takes two arguments.')
            n,k=(bounded_int(x,500) for x in vals)
            if not 0<=k<=n: raise MathError('Require 0 <= k <= n.')
            return guard(s.binomial(n,k))
        if len(vals) not in ((1,2) if name=='log' else (1,)):
            raise MathError('Incorrect number of function arguments.')
        return guard(calls[name](*vals))
    value=guard(s.simplify(visit(left,{})))
    if right is not None:
        rhs=guard(s.simplify(visit(right,{})))
        if guard(s.simplify(value-rhs)).is_zero is not True:
            raise MathError('Equation is false or could not be verified exactly.')
    if value.free_symbols or value.is_finite is not True or value.is_number is not True:
        raise MathError('Result is not a finite, resolved number.')
    integer=int(value) if value.is_Integer is True and abs(value)<=MAX_COUNT else None
    rendered=str(value)
    if len(rendered)>500: raise MathError('Result too large to display.')
    approximation=None
    if integer is None:
        approximation=str(value.evalf(12))[:150]
    return {'ok':True,'result':rendered,'integer':integer,'approximation':approximation}


def main():
    # Unix resource limits apply before importing SymPy. The parent enforces a wall timeout on all OSes.
    if sys.platform.startswith('linux'):
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(3,4))
        resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    try:
        # Parent sends UTF-8 bytes; Windows pipe encoding is not always UTF-8.
        text=sys.stdin.buffer.read(2049)
        if len(text)>2048: raise MathError('Expression input too large.')
        try:
            text=text.decode('utf-8',errors='strict')
        except UnicodeDecodeError:
            raise MathError('Invalid UTF-8 input.')
        result=calculate(text)
    except MathError as exc:
        result={'ok':False,'error':str(exc)}
    except ImportError:
        result={'ok':False,'error':'Math evaluator dependency unavailable.','unavailable':True}
    except Exception:
        result={'ok':False,'error':'Expression could not be evaluated within the supported domain.'}
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__': main()
