#!/usr/bin/env sh
# if you are using a flatpak IDE, you can use this script as 
# python interpreter to span your venv python
test -x .venv/bin/python && /usr/bin/env -- flatpak-spawn --host .venv/bin/python "$@"
