#!/bin/bash

tmpdir=$(mktemp -d) || exit 1

# check if python supports zipapp compression
zipapp="python3 -m zipapp"
if python3 -m zipapp --help | grep -q -- --compress; then
    zipapp="$zipapp --compress"
fi

if [ -z "$libs" ]; then
  if [ -d lib ]; then cp -a lib $tmpdir/; fi
else
  mkdir $tmpdir/lib
  for lib in $libs; do
    cp lib/$lib $tmpdir/lib/
  done
fi

if [ "$requirements" != "none" ]; then
  if [ -z "$requirements" ]; then
    if [ -f requirements.txt ]; then
      requirements="$(cat requirements.txt)"
      if python3 -c 'import requests' 2>/dev/null; then
        requirements="$(grep -iv requests requirements.txt)"
      fi
    fi
  fi
  if [ -n "$requirements" ]; then
    python3 -m pip install $requirements --target $tmpdir
  fi
fi

if [ $# -lt 1 ]; then
  scripts=*.py
else
  scripts="$@"
fi

for script in $scripts; do
  cp $script $tmpdir/__main__.py
  $zipapp --python "/usr/bin/env python3" --output ${script}z $tmpdir
done

rm -r $tmpdir
