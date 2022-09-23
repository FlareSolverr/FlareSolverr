#!/bin/sh -

export DISPLAY=99
#echo "Listening on :$DISPLAY"

xvfb-run -s "-screen 0 1920x1080x24" python -u /app/flaresolverr.py
