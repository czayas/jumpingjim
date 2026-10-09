#!/bin/sh
# Headless VICE run + screenshot (testing helper)
# usage: shot.sh prg cycles out.png [extra vice args]
PRG=$1; CYC=$2; OUT=$3; shift 3
timeout 120 xvfb-run -a x64sc -default -silent -sounddev dummy -autostartprgmode 1 -autostart-warp +autostart-handle-tde -warp -limitcycles $CYC -exitscreenshot "$OUT" "$@" "$PRG" >/tmp/vice.log 2>&1
echo "exit $?"
