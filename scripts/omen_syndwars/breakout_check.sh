#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Prova del minigioco Breakout (bat.c, bat_s.sx) forzando lo stato in una partita registrata.
# Il Breakout parte solo con un agente col Persuadertron in un punto preciso della mappa: nelle partite registrate non
# parte mai. Qui, al turno 400, si da' al gioco lo stato di una nuova partita (come BAT_start_new_game) e si lascia
# girare fino al turno 1200: BAT_play gira a ogni fotogramma. Si salvano i dati del Breakout e lo schermo.
# Uso: breakout_check.sh <binario in /opt/sw> <tag>   -> /tmp/bo_<tag>_* ; con tag "ref" il binario di riferimento.
BIN=$1; TAG=$2
export SDL_AUDIODRIVER=dummy ALSOFT_DRIVERS=null
W=/mnt/c/Users/opoda/swbuild
cd /opt/sw || exit 1
pkill -9 Xvfb 2>/dev/null; sleep 1
(setsid Xvfb :60 -screen 0 1024x768x24 >/dev/null 2>&1 &)
for _ in $(seq 1 30); do xwd -root -silent -display :60 >/dev/null 2>&1 && break; sleep 1; done
export DISPLAY=:60 HOME=/root
rm -f /tmp/bo_${TAG}_*
cat > /tmp/g_bo_$TAG <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
set \$done = 0
break process_things if gameturn == 400 && \$done == 0
commands
silent
set \$done = 1
set var BAT_screen = (unsigned char *) mmap(0x20000000, 65536, 3, 0x32, -1, 0)
set var bat_unknvalA_min = 0
set var bat_unknvalA_max = 127
set var bat_unknvalB_min = 0
set var bat_unknvalB_max = 127
python
import gdb
for i in range(1, 1000):
    th = gdb.parse_and_eval("things[%d]" % i)
    if int(th["Type"]) == 3 and (int(th["Flag"]) & 0x2000) and not (int(th["Flag"]) & 0x2):
        gdb.execute("set var things[%d].U.UPerson.CurrentWeapon = 7" % i)
        print("agente %d con il Persuadertron" % i)
        break
end
set var BAT_state = 1
set var BAT_levelno = 1
set var BAT_score = 0
set var BAT_num_lives = 2
set var BAT_level_intro_timer = 90
continue
end
G
cat >> /tmp/g_bo_$TAG <<'G'
break process_things if gameturn == 440
commands
silent
python
import gdb, struct
inf = gdb.selected_inferior()
def rd(a):
    return struct.unpack("<i", bytes(inf.read_memory(a, 4)))[0]
def wr(a, v):
    inf.write_memory(a, struct.pack("<i", v))
def addr(sym):
    return int(gdb.parse_and_eval("(long)&" + sym)) & 0xFFFFFFFF
free_a, head_a = addr("BAT_free_bonuses"), addr("BAT_bonuses_head")
paddle = int(gdb.parse_and_eval("BAT_paddle_x"))
made = 0
for kind in range(7):
    cur = rd(free_a)
    if cur == 0:
        break
    nxt = rd(cur + 16)
    wr(free_a, nxt)
    if nxt:
        wr(nxt + 20, free_a)
    head = rd(head_a)
    if head:
        wr(cur + 16, head)
        wr(head + 20, cur + 16)
    else:
        wr(cur + 16, 0)
    wr(head_a, cur)
    wr(cur + 20, head_a)
    wr(cur + 0, kind)
    wr(cur + 4, (paddle << 8) + (kind - 3) * 0x40)
    wr(cur + 8, 0x2800 + kind * 0x180)
    wr(cur + 12, 0x40)
    made += 1
print("bonus inseriti: %d" % made)
end
continue
end
G
for T in 410 430 450 480 520 600 700 900; do
cat >> /tmp/g_bo_$TAG <<G
break process_things if gameturn == $T
commands
silent
printf "turno %d: state=%d timer=%d remain=%d lives=%d score=%d balls=%p bonus=%p\\n", gameturn, BAT_state, BAT_level_intro_timer, BAT_bricks_remain, BAT_num_lives, BAT_score, BAT_balls_head, BAT_bonuses_head
dump binary memory /tmp/bo_${TAG}_${T}_screen.bin 0x20000000 0x20004000
dump binary memory /tmp/bo_${TAG}_${T}_balls.bin &BAT_balls_store (char*)&BAT_balls_store+sizeof(BAT_balls_store)
dump binary memory /tmp/bo_${TAG}_${T}_bonus.bin &BAT_bonus_store (char*)&BAT_bonus_store+sizeof(BAT_bonus_store)
dump binary memory /tmp/bo_${TAG}_${T}_bricks.bin &BAT_bricks (char*)&BAT_bricks+sizeof(BAT_bricks)
continue
end
G
done
if [ -n "$FOLLOW" ]; then
# La racchetta segue la prima palla: BAT_input_paddle legge lbDisplay.MMouseX a ogni fotogramma.
cat >> /tmp/g_bo_$TAG <<'G'
break process_things if gameturn >= 460 && gameturn <= 900
commands
silent
python
import gdb, struct
inf = gdb.selected_inferior()
head = int(gdb.parse_and_eval("(long)BAT_balls_head")) & 0xFFFFFFFF
if head:
    x = struct.unpack("<i", bytes(inf.read_memory(head, 4)))[0] >> 8
    scr = int(gdb.parse_and_eval("lbDisplay.GraphicsScreenWidth"))
    gdb.execute("set var lbDisplay.MMouseX = %d" % (scr // 2 + ((x - 48) * (scr // 2)) // 96))
end
continue
end
G
fi
if [ -n "$TRACE" ]; then
cat >> /tmp/g_bo_$TAG <<G
break process_things if gameturn >= 441 && gameturn <= 520
commands
silent
printf "t%d lives=%d state=%d remain=%d\\n", gameturn, BAT_num_lives, BAT_state, BAT_bricks_remain
continue
end
G
fi
cat >> /tmp/g_bo_$TAG <<G
break process_things if gameturn == 901
commands
kill
quit
end
run
G
timeout 400 gdb -q -batch -x /tmp/g_bo_$TAG --args ./$BIN -q -W -H -m 0,1 -p 3 > /tmp/bo_${TAG}.out 2>&1
echo "gdb rc=$?"
pkill -9 Xvfb 2>/dev/null
grep -a -E '^(turno|agente|bonus|t[0-9])' /tmp/bo_${TAG}.out
tail -3 /tmp/bo_${TAG}.out | cut -c1-160
