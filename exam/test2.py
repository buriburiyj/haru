import importlib.util, sys
spec=importlib.util.spec_from_file_location("s","/tmp/exam_sol/solution2.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ok=0;tot=0
def t(c):
    global ok,tot;tot+=1
    try: ok+=bool(c())
    except Exception: pass
mi=m.merge_intervals
t(lambda:[list(x) for x in mi([[1,2],[2,3]])]==[[1,3]])
t(lambda:[list(x) for x in mi([[1,2],[3,4]])]==[[1,2],[3,4]])
t(lambda:[list(x) for x in mi([[5,6],[1,9],[2,3]])]==[[1,9]])
t(lambda:mi([])==[])
l=m.lru_cache_sim
t(lambda:l(2,[("put",1,1),("put",2,2),("get",1),("put",3,3),("get",2),("get",3)])==[1,-1,3])
t(lambda:l(0,[("put",1,1),("get",1)])==[-1])
t(lambda:l(2,[("put",1,1),("put",2,2),("put",1,9),("put",3,3),("get",1),("get",2)])==[9,-1])
e=m.eval_expr
t(lambda:e("1 + 2 * 3")==7)
t(lambda:e("( 1 + 2 ) * 3")==9)
t(lambda:e("- 3 + 5")==2)
t(lambda:e("7 / 2")==3.5)
t(lambda:e("2 * - ( 1 + 1 )")==-4)
def bad():
    for s in ["1 +","( 1","","a + 1","1 / 0"]:
        try: e(s)
        except (ValueError,ZeroDivisionError): continue
        return False
    return True
t(bad)
print("PASS",ok,"/",tot)
