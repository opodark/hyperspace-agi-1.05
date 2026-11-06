NAME=__NAME__
H=__H__
W=/mnt/c/Users/opoda/swbuild
tar -xmf $W/sets/$NAME.tar -C /src 2>/dev/null
cd /src/build; rm -f src/syndwarsfx; make -k -j7 > /tmp/ev_$NAME.log 2>&1
if [ ! -f src/syndwarsfx ]; then echo "RISULTATO $NAME BUILD_FALLITA"; grep -E ': error:|undefined reference' /tmp/ev_$NAME.log | head -3 | cut -c1-150; exit 0; fi
cp src/syndwarsfx /opt/sw/game.ev
export SDL_AUDIODRIVER=dummy ALSOFT_DRIVERS=null
pkill Xvfb; setsid nohup Xvfb :9 -screen 0 1024x768x24 >/dev/null 2>&1 & sleep 1; export DISPLAY=:9
cd /opt/sw; rm -f /tmp/e_*; cat > /tmp/g_e <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn % 400 == 0
commands
silent
eval "dump binary memory /tmp/e_%d_t.bin (char*)things-60*1500 (char*)things+168*1000", gameturn
eval "dump binary memory /tmp/e_%d_m.bin game_my_big_map (char*)game_my_big_map+128*128*sizeof(struct MyMapElement)", gameturn
if gameturn >= $H
  kill
  quit
end
continue
end
run
G
timeout 450 gdb -q -batch -x /tmp/g_e --args ./game.ev -q -W -H -m 0,1 -p 3 > /tmp/gdb_ev.out 2>&1
pkill -f 'game.ev -q'; pkill Xvfb
res=IDENTICO; first=""; t=400
while [ $t -le $H ]; do
  if [ ! -f /tmp/e_${t}_t.bin ]; then res=NESSUN_DUMP; first="turno=$t"; break; fi
  if ! cmp -s /tmp/k_a_${t}_t.bin /tmp/e_${t}_t.bin || ! cmp -s /tmp/k_a_${t}_m.bin /tmp/e_${t}_m.bin; then res=DIVERSO; first="turno=$t"; break; fi
  t=$((t+400))
done
echo "RISULTATO $NAME $res $first"
