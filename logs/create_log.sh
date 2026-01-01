#!/bin/bash

name=_$1

if [[ $name == "_" ]] ; then name=""; fi
count=$(ls *.log | wc -l)
d="$(date +%Y_%m_%d)"
touch log"$count""$name"_"$d".log
vim log"$count""$name"_"$d".log

