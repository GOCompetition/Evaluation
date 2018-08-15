#!/bin/sh

case_dir='./case2/'
raw=$case_dir'case.raw'
rop=$case_dir'case.rop'
con=$case_dir'case.con'
inl=$case_dir'case.inl'
sol1=$case_dir'sol1.txt'
sol2=$case_dir'sol2.txt'
det=$case_dir'detail.csv'

# run it
python ../run.py "$raw" "$rop" "$con" "$inl" "$sol1" "$sol2" "$det"
