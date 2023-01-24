import random
import os
cb = int(os.environ["CB"])
cc = int(os.environ["CC"])
cd = int(os.environ["CD"])
ce = int(os.environ["CE"])
cf = int(os.environ["CF"])
def generate():
  b = random.randint(0,9)
  c = random.randint(0,9)
  d = random.randint(0,9)
  e = random.randint(0,9)
  f = random.randint(0,9)
  x = b*cb + c*cc + d*cd + e*ce + f*cf
  astr = str(x%10)
  bstr = str(b)
  cstr = str(c)
  dstr = str(d)
  estr = str(e)
  fstr = str(f)
  code = astr + bstr + cstr + dstr + estr + fstr
  return code