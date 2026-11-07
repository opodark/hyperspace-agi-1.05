#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Prova completa di un binario di Syndicate Wars, con i lavori in parallelo sulla stessa macchina (WSL su OMEN).
#   - una partita per missione registrata (stato di gioco ai turni 400 e 800, o fino all'orizzonte indicato)
#   - la partita lunga 0,1 fino al turno 3200
#   - le chiamate dirette alle funzioni, divise in N parti
# Ogni lavoro ha il suo display virtuale, la sua cartella HOME e file di uscita con il proprio tag: non si pestano.
# Uso: par_check.sh <binario in /opt/sw> <tag> [parti per le chiamate dirette, default 4]
# Richiede in $W: suite.txt, names.txt, dc_gdb.py; in /tmp i riferimenti su_o1_* e L_o_* del binario di riferimento.
BIN=$1; TAG=$2; PARTS=${3:-4}
W=/mnt/c/Users/opoda/swbuild
export SDL_AUDIODRIVER=dummy ALSOFT_DRIVERS=null
cd /opt/sw || exit 1
[ -x "./$BIN" ] || { echo "binario $BIN assente"; exit 1; }
pkill -9 Xvfb 2>/dev/null; sleep 1
START=$(date +%s)
LOGDIR=/tmp/par_$TAG; rm -rf $LOGDIR; mkdir -p $LOGDIR
rm -f /tmp/su_${TAG}_* /tmp/L_${TAG}_* /tmp/dc_${TAG}*.txt

# stesso dc_gdb.py ma con la lista di nomi presa da un file e senza i dump per chiamata
sed -e 's#open("/mnt/c/Users/opoda/swbuild/names.txt")#open(os.environ["NAMES_FILE"])#' \
    -e 's#if ONLY:#if False:#' $W/dc_gdb.py > /tmp/dcp_gdb.py
grep -q NAMES_FILE /tmp/dcp_gdb.py || { echo "dc_gdb.py non adattabile"; exit 1; }
# ripristino della memoria: accetta qualunque binario di /opt/sw
sed -i -e 's#(path.endswith("game.fixbase") or path.endswith("game.ev") or path == "\[heap\]")#("/opt/sw/game." in path or path == "[heap]")#' /tmp/dcp_gdb.py

new_job_env() {  # $1 = numero del lavoro: display e HOME dedicati
  D=$((30 + $1)); export DISPLAY=:$D
  HOME_J=/tmp/home_${TAG}_$1; rm -rf $HOME_J; mkdir -p $HOME_J/.config
  cp -r /root/.config/syndwarsfx $HOME_J/.config/
  export HOME=$HOME_J
  (setsid Xvfb :$D -screen 0 1024x768x24 >/dev/null 2>&1 &)
  sleep 1
}

mission_job() {  # indice, missione, numero registrazione, orizzonte
  ( new_job_env $1; t=$(echo $2 | tr , _)
    cat > /tmp/g_${TAG}_m$1 <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn % 400 == 0
commands
silent
eval "dump binary memory /tmp/su_${TAG}_${t}_%d_t.bin (char*)things-60*1500 (char*)things+168*1000", gameturn
eval "dump binary memory /tmp/su_${TAG}_${t}_%d_m.bin game_my_big_map (char*)game_my_big_map+128*128*sizeof(struct MyMapElement)", gameturn
if gameturn >= $4
  kill
  quit
end
continue
end
run
G
    timeout 600 gdb -q -batch -x /tmp/g_${TAG}_m$1 --args ./$BIN -q -W -H -m $2 -p $3 > $LOGDIR/m$1.out 2>&1
    echo "missione $2 rc=$?" > $LOGDIR/m$1.done )
}

long_job() {
  ( new_job_env 9
    cat > /tmp/g_${TAG}_L <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn % 400 == 0
commands
silent
eval "dump binary memory /tmp/L_${TAG}_%d_t.bin (char*)things-60*1500 (char*)things+168*1000", gameturn
eval "dump binary memory /tmp/L_${TAG}_%d_m.bin game_my_big_map (char*)game_my_big_map+128*128*sizeof(struct MyMapElement)", gameturn
if gameturn >= 3200
  kill
  quit
end
continue
end
run
G
    timeout 900 gdb -q -batch -x /tmp/g_${TAG}_L --args ./$BIN -q -W -H -m 0,1 -p 3 > $LOGDIR/L.out 2>&1
    echo "lunga rc=$?" > $LOGDIR/L.done )
}

dc_job() {  # indice parte
  ( new_job_env $((10 + $1))
    awk -v k=$1 -v n=$PARTS 'NR % n == k' $W/names.txt > $LOGDIR/names_$1.txt
    cat > /tmp/g_${TAG}_dc$1 <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn == 400
run
set var fifties_per_gameturn = 400
source /tmp/dcp_gdb.py
G
    NAMES_FILE=$LOGDIR/names_$1.txt TAG=${TAG}_$1 timeout 1500 gdb -q -batch -x /tmp/g_${TAG}_dc$1 --args ./$BIN -q -W -H -m 0,1 -p 3 > $LOGDIR/dc$1.out 2>&1
    echo "chiamate parte $1 rc=$? righe $(wc -l < /tmp/dc_${TAG}_$1.txt 2>/dev/null)" > $LOGDIR/dc$1.done )
}

i=0
while read m num; do
  H=800; [ "$m" = "0,1" ] && H=800
  mission_job $i $m $num $H &
  i=$((i+1))
done < $W/suite.txt
long_job &
for k in $(seq 0 $((PARTS-1))); do dc_job $k & done
wait
pkill -9 Xvfb 2>/dev/null
END=$(date +%s)
echo "durata totale $((END-START)) s con $((i+1+PARTS)) lavori"
cat $LOGDIR/*.done

# chiamate dirette: un file unico, come quello della prova in serie
cat /tmp/dc_${TAG}_[0-9]*.txt > /tmp/dc_${TAG}.txt
cp /tmp/dc_${TAG}.txt $W/dc_${TAG}.txt
echo "chiamate dirette: $(grep -vc '^#' /tmp/dc_${TAG}.txt) righe"

echo "--- missioni contro il riferimento o1"
python3 - <<P
import glob,re
S,T=60,168
nd=lambda p,q,k:sum(p[i:i+k]!=q[i:i+k] for i in range(0,min(len(p),len(q)),k))
for line in open('$W/suite.txt'):
    m,_=line.split(); t=m.replace(',','_'); r=[]
    for f in sorted(glob.glob(f'/tmp/su_o1_{t}_*_t.bin')):
        tn=re.search(r'_(\d+)_t\.bin',f).group(1); g=f.replace('su_o1','su_$TAG')
        try:
            a,b=open(f,'rb').read(),open(g,'rb').read(); ma=open(f.replace('_t.bin','_m.bin'),'rb').read(); mb=open(g.replace('_t.bin','_m.bin'),'rb').read()
        except OSError: r.append((tn,'manca')); continue
        r.append((tn,nd(a[:S*1500],b[:S*1500],S),nd(a[S*1500:],b[S*1500:],T),sum(i!=j for i,j in zip(ma,mb))))
    print(m,r)
P
echo "--- partita lunga contro il riferimento"
for t in 400 800 1200 1600 2000 2400 2800 3200; do
  cmp -s /tmp/L_o_${t}_t.bin /tmp/L_${TAG}_${t}_t.bin && cmp -s /tmp/L_o_${t}_m.bin /tmp/L_${TAG}_${t}_m.bin && echo -n "$t=uguale " || echo -n "$t=DIVERSO "
done; echo
echo FINE
