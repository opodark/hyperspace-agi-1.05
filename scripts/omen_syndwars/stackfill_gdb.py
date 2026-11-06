import gdb, os
inf = gdb.selected_inferior()
fill = int(os.environ["FILL"]) if os.environ.get("FILL", "") != "" else None
tag = os.environ["TAG"]

class Fill(gdb.Breakpoint):
    def stop(self):
        esp = int(gdb.parse_and_eval("(unsigned long)$esp"))
        inf.write_memory(esp - 2048, bytes([fill]) * 2040)
        return False
if fill is not None:
    Fill("*person_move", internal=True)

class Fix(gdb.Breakpoint):
    def stop(self):
        gdb.execute("set var fifties_per_gameturn = 400", to_string=True)
        if int(gdb.parse_and_eval("gameturn")) == 400:
            tb = int(gdb.parse_and_eval("(unsigned long)things"))
            open("/tmp/fill_%s_t.bin" % tag, "wb").write(bytes(inf.read_memory(tb - 60 * 1500, 60 * 1500 + 168 * 1000)))
            mp = int(gdb.parse_and_eval("(unsigned long)game_my_big_map"))
            open("/tmp/fill_%s_m.bin" % tag, "wb").write(bytes(inf.read_memory(mp, 128 * 128 * int(gdb.parse_and_eval("sizeof(struct MyMapElement)")))))
            os._exit(0)
        return False
Fix("process_things", internal=True)
