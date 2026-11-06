cd /opt/sw; export SDL_AUDIODRIVER=dummy ALSOFT_DRIVERS=null
pkill Xvfb; setsid nohup Xvfb :9 -screen 0 1024x768x24 >/dev/null 2>&1 & sleep 2; export DISPLAY=:9
run() { tag=$1; bin=$2
  cat > /tmp/g_dc <<G
set pagination off
handle SIG32 SIG33 SIGPIPE nostop noprint pass
break process_things if gameturn == 400
run
set var fifties_per_gameturn = 400
source /mnt/c/Users/opoda/swbuild/dc_gdb.py
G
  TAG=$tag timeout 900 gdb -q -batch -x /tmp/g_dc --args ./$bin -q -W -H -m 0,1 -p 3 > /tmp/gdbdc_$tag.out 2>&1
  echo "$tag uscita $? righe $(wc -l < /tmp/dc_$tag.txt 2>/dev/null)"; tail -2 /tmp/dc_$tag.txt | cut -c1-120; pkill -f "$bin -q"
}
run ev game.ev
