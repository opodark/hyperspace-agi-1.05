# uso: evalset.sh NOME   (il tar sta in $W/sets/NOME.tar)
NAME=__NAME__
W=/mnt/c/Users/opoda/swbuild
cp /tmp/fill_fb_n_t.bin /tmp/ref_400_t.bin; cp /tmp/fill_fb_n_m.bin /tmp/ref_400_m.bin
cd /src && tar -xmf $W/pristine.tar -C /src && tar -xmf $W/sets/$NAME.tar -C /src
cp $W/drafts_link.h /src/src/drafts_link.h
cp $W/swars_repo.sx /src/src/swars.sx; cat $W/drafts_link_tail.sx >> /src/src/swars.sx; touch /src/src/swars.sx
perl -0pi -e 's/(ThingIdx check_for_other_people_on_tile\(.*?k = 0;)/$1\n    found = 0;/s' /src/src/people.c 2>/dev/null
cd /src/build; rm -f src/syndwarsfx
make -k -j6 > /tmp/ev_$NAME.log 2>&1
if [ ! -f src/syndwarsfx ]; then echo "RISULTATO $NAME BUILD_FALLITA"; grep -E 'error|undefined' /tmp/ev_$NAME.log | head -3 | cut -c1-150; exit 0; fi
cp src/syndwarsfx /opt/sw/game.ev
Xvfb :9 -screen 0 1024x768x24 >/dev/null 2>&1 & sleep 1
export DISPLAY=:9 SDL_AUDIODRIVER=dummy ALSOFT_DRIVERS=null
cd /opt/sw; rm -f /tmp/ev_t.bin /tmp/ev_m.bin
cat > /tmp/g_ev <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn == 400
commands
silent
dump binary memory /tmp/ev_t.bin (char*)things-60*1500 (char*)things+168*1000
dump binary memory /tmp/ev_m.bin game_my_big_map (char*)game_my_big_map+128*128*sizeof(struct MyMapElement)
kill
quit
end
run
G
timeout 240 gdb -q -batch -x /tmp/g_ev --args ./game.ev -q -W -H -m 0,1 -p 3 > /tmp/gdb_ev.out 2>&1; rc=$?
pkill Xvfb
if [ ! -f /tmp/ev_t.bin ]; then echo "RISULTATO $NAME NESSUN_DUMP uscita=$rc"; grep -iE 'signal|SIG|rror' /tmp/gdb_ev.out | head -3 | cut -c1-150; exit 0; fi
python3 - $NAME <<'P'
import sys
S,T=60,168
a,b=open('/tmp/ref_400_t.bin','rb').read(),open('/tmp/ev_t.bin','rb').read()
nd=lambda x,y,n:sum(x[i:i+n]!=y[i:i+n] for i in range(0,min(len(x),len(y)),n))
ma,mb=open('/tmp/ref_400_m.bin','rb').read(),open('/tmp/ev_m.bin','rb').read()
sd,td,md=nd(a[:S*1500],b[:S*1500],S),nd(a[S*1500:],b[S*1500:],T),sum(p!=q for p,q in zip(ma,mb))
print('RISULTATO',sys.argv[1],'IDENTICO' if sd==td==md==0 else 'DIVERSO',f'sthings={sd} things={td} mappa={md}')
P
