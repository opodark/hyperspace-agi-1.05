W=/mnt/c/Users/opoda/swbuild
X="--exclude=Makefile.am --exclude=configure.ac --exclude=*.m4"
tar -xmf $W/master_tree.tar $X -C /src; rm -f /src/src/drafts_link.h
cd /src/build; rm -f src/syndwarsfx; make -k -j7 > /tmp/m.log 2>&1; echo "master make $? errori $(grep -c ': error:' /tmp/m.log) nondef $(grep -c 'undefined reference' /tmp/m.log)"; cp src/syndwarsfx /opt/sw/game.m
tar -xmf $W/branch_files.tar -C /src
rm -f src/syndwarsfx; make -k -j7 > /tmp/h.log 2>&1; echo "ramo make $? errori $(grep -c ': error:' /tmp/h.log) nondef $(grep -c 'undefined reference' /tmp/h.log)"; grep -E ': error:' /tmp/h.log | head -5 | cut -c1-170; cp src/syndwarsfx /opt/sw/game.h
rm -rf /opt/sw4; mkdir /opt/sw4; cd /opt/sw; for f in *; do case "$f" in data|error.log|NONE|config.ini) ;; *) ln -s /opt/sw/$f /opt/sw4/$f;; esac; done
cp -r /opt/sw/data /opt/sw4/data; mkdir -p /opt/sw4/NONE/share; ln -s /opt/sw4 /opt/sw4/NONE/share/syndwarsfx
mkdir -p /tmp/hi && rm -f /tmp/hi/* && tar -xmf $W/hiout.tar -C /tmp/hi 2>/dev/null; cp /tmp/hi/* /opt/sw4/data/
(cat /opt/sw/config.ini; echo 'ResGameHi="1920x1080x8"') > /opt/sw4/config.ini
export SDL_AUDIODRIVER=dummy ALSOFT_DRIVERS=null
pkill Xvfb; setsid nohup Xvfb :9 -screen 0 2560x1440x24 >/dev/null 2>&1 & sleep 2; export DISPLAY=:9
rm -f /tmp/k_* $W/shots/k_*
run() { n=$1; dir=$2; bin=$3; cd $dir; cat > /tmp/g_k <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn % 400 == 0
commands
silent
eval "dump binary memory /tmp/k_${n}_%d_t.bin (char*)things-60*1500 (char*)things+168*1000", gameturn
eval "dump binary memory /tmp/k_${n}_%d_m.bin game_my_big_map (char*)game_my_big_map+128*128*sizeof(struct MyMapElement)", gameturn
printf "T %d ", gameturn
shell date +%s.%N
if gameturn == 400 || gameturn == 1200
  eval "shell import -window root $W/shots/k_${n}_%d.png", gameturn
end
if gameturn >= 3200
  kill
  quit
end
continue
end
run
G
timeout 550 gdb -q -batch -x /tmp/g_k --args ./$bin -q -W -H -m 0,1 -p 3 > /tmp/gdbk_$n.out 2>&1; echo "== $n uscita $?"; grep -E '^T [0-9]+' /tmp/gdbk_$n.out | awk 'NR==1{t=$3;a=$2} END{printf "turni %d-%d in %.1f s = %.1f turni/s\n",a,$2,$3-t,($2-a)/($3-t)}'; grep -E 'signal|SIG[A-Z]+,' /tmp/gdbk_$n.out | head -3 | cut -c1-120; }
run a /opt/sw game.m
run b /opt/sw game.h
run c /opt/sw4 game.h
pkill Xvfb
python3 - <<'P'
import glob,re
S,T=60,168
def ts(n): return sorted(int(re.search(r'_(\d+)_t',f).group(1)) for f in glob.glob(f'/tmp/k_{n}_*_t.bin'))
nd=lambda p,q,k:sum(p[i:i+k]!=q[i:i+k] for i in range(0,min(len(p),len(q)),k))
for x,y in (('a','b'),('a','c')):
    r=[]
    for t in sorted(set(ts(x))&set(ts(y))):
        A,B=open(f'/tmp/k_{x}_{t}_t.bin','rb').read(),open(f'/tmp/k_{y}_{t}_t.bin','rb').read()
        ma,mb=open(f'/tmp/k_{x}_{t}_m.bin','rb').read(),open(f'/tmp/k_{y}_{t}_m.bin','rb').read()
        r.append((t,nd(A[:S*1500],B[:S*1500],S),nd(A[S*1500:],B[S*1500:],T),sum(i!=j for i,j in zip(ma,mb))))
    print(x,y,r)
P
