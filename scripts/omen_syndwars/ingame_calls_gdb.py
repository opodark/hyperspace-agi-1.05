import gdb, os, signal, threading, hashlib
inf = gdb.selected_inferior()
import ctypes
libc = ctypes.CDLL("libc.so.6")
gdb.execute("set unwindonsignal on")
gdb.execute("set scheduler-locking on")
gdb.execute("set unwind-on-terminating-exception on")
TAG = os.environ["TAG"]
names = [l.strip() for l in open("/mnt/c/Users/opoda/swbuild/names.txt") if l.strip()]
out = open("/tmp/dc_%s.txt" % TAG, "w")
tb = int(gdb.parse_and_eval("(unsigned long)things"))
mp = int(gdb.parse_and_eval("(unsigned long)game_my_big_map"))
msz = 128 * 128 * int(gdb.parse_and_eval("sizeof(struct MyMapElement)"))
def rd(a, n): return bytes(inf.read_memory(a, n))
def state():
    t = rd(tb - 60 * 1500, 60 * 1500 + 168 * 1000)
    return hashlib.sha1(t).hexdigest()[:10], hashlib.sha1(rd(mp, msz)).hexdigest()[:10]
persons = [i for i in range(1, 1000) if rd(tb + 168 * i + 9, 1)[0] == 3 and int.from_bytes(rd(tb + 168 * i + 58, 2), "little", signed=True) > 0]
sth = [k for k in range(1, 1500) if rd(tb - 60 * k + 9, 1)[0] != 0]
A, B = persons[0], persons[1]
S = [sth[0], sth[1]]
long_t = gdb.lookup_type("long")
scratch = int(gdb.parse_and_eval("(unsigned long)malloc(8192)"))
inf.write_memory(scratch, b"\0" * 8192)
import re, time
def regions():
    res = []
    for line in open("/proc/%d/maps" % inf.pid):
        m = re.match(r"([0-9a-f]+)-([0-9a-f]+) (\S+) \S+ \S+ \S+\s*(.*)", line)
        a, b, perm, path = int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4).strip()
        size = b - a
        if "rw" not in perm or "stack" in path or size in (8388608, 8392704, 8384512, 8388608 + 4096): continue
        if path and not (path.endswith("game.fixbase") or path.endswith("game.ev") or path == "[heap]"): continue
        res.append((a, size))
    return res
REG = regions()
SNAP = [(a, rd(a, n)) for a, n in REG]
out.write("# regioni %d, %.1f MB\n" % (len(REG), sum(n for _, n in REG) / 1e6))
def restore():
    for a, data in SNAP:
        inf.write_memory(a, data)
base_state = state()
out.write("# persons %d %d sthings %d %d\n" % (A, B, S[0], S[1]))

def args_for(ptypes, t):
    vals = []
    for i, pt in enumerate(ptypes):
        pt = pt.strip_typedefs()
        if pt.code == gdb.TYPE_CODE_PTR:
            tgt = pt.target().strip_typedefs()
            nm = str(tgt)
            if "struct Thing" == nm:
                a = tb + 168 * (A if t % 2 == 0 else B)
            elif "struct SimpleThing" == nm:
                a = tb - 60 * S[t % 2]
            else:
                a = scratch
            vals.append(gdb.Value(a).cast(pt))
        else:
            v = [0, A, 1 + i, 100 * (i + 1)][t]
            vals.append(gdb.Value(v).cast(pt))
    return vals

def guarded_call(fn, args):
    pid = inf.pid
    timer = threading.Timer(12.0, lambda: libc.syscall(234, pid, pid, 2))
    timer.start()
    try:
        return fn(*args)
    finally:
        timer.cancel()

for name in names:
    try:
        fn = gdb.parse_and_eval(name)
        ptypes = [f.type for f in fn.type.fields()]
        rtype = fn.type.target().strip_typedefs()
    except Exception as e:
        out.write("%s\t-\tSENZA_SIMBOLO\t-\t-\t-\n" % name); out.flush(); continue
    for t in range(4):
        try:
            sp = int(gdb.parse_and_eval("$sp"))
            inf.write_memory(sp - 8192, b"\0" * 8000)
            args = args_for(ptypes, t)
            res = guarded_call(fn, args)
            if rtype.code == gdb.TYPE_CODE_VOID: r = "void"
            elif rtype.code == gdb.TYPE_CODE_PTR: r = "null" if int(res) == 0 else "ptr"
            else: r = str(int(res))
            status = "ok"
        except Exception as e:
            r, status = "-", "ERR:" + str(e).split("\n")[0][:50].replace("0x", "").replace("\t", " ")
        try:
            th, mh = state()
        except Exception:
            th = mh = "?"
        out.write("%s\t%d\t%s\t%s\t%s\t%s\n" % (name, t, status, r, th, mh)); out.flush()
        try:
            restore()
            if state() != base_state:
                out.write("# ATTENZIONE: stato non ripristinato dopo %s t%d\n" % (name, t)); out.flush()
        except Exception as e:
            out.write("# ripristino fallito %s: %s\n" % (name, e)); out.flush(); os._exit(2)
out.write("# FINE\n"); out.flush()
os._exit(0)
