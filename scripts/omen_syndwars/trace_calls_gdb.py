import gdb
LIMIT = 4000
state = {"n": 0}
out = open("/tmp/trace_out.txt", "w")
inf = gdb.selected_inferior()
def rd(addr, n): return bytes(inf.read_memory(addr, n))

class After(gdb.FinishBreakpoint):
    def __init__(self, frame, n, idx, arg, before):
        super().__init__(frame, internal=True)
        self.n, self.idx, self.arg, self.before = n, idx, arg, before
    def stop(self):
        after = rd(self.arg, 168)
        out.write("%d %d %s %s\n" % (self.n, self.idx, self.before.hex(), after.hex())); out.flush()
        return False
    def out_of_scope(self):
        out.write("%d %d FUORI\n" % (self.n, self.idx)); out.flush()

class Entry(gdb.Breakpoint):
    def stop(self):
        if state["n"] >= LIMIT:
            return False
        state["n"] += 1
        esp = int(gdb.parse_and_eval("(unsigned long)$esp"))
        arg = int.from_bytes(rd(esp + 4, 4), "little")
        base = int(gdb.parse_and_eval("(unsigned long)things"))
        After(gdb.newest_frame(), state["n"], (arg - base) // 168, arg, rd(arg, 168))
        return False

Entry("*person_goto_point")

class Fix(gdb.Breakpoint):
    def stop(self):
        gdb.execute("set var fifties_per_gameturn = 400", to_string=True)
        return False
Fix("process_things", internal=True)
