#!/bin/sh

#case_dir='./examples/case2/'
#raw=$case_dir'case.raw'
#rop=$case_dir'case.rop'
#con=$case_dir'case.con'
#inl=$case_dir'case.inl'
#sol1=$case_dir'sol1.txt'
#sol2=$case_dir'sol2.txt'
#det=$case_dir'detail.csv'

case_dir='./examples/sdet2000/'
raw=$case_dir'S2000O_s1_case.raw'
#raw=$case_dir'S2000O_s2_case.raw'
rop=$case_dir'case.rop'
con=$case_dir'case.con'
inl=$case_dir'case.inl'
#inl=$case_dir'case_mod.inl'
sol1=$case_dir'S2000O_s1_case_scopf__solution1.txt'
#sol1=$case_dir'S2000O_s2_case_scopf__solution1.txt'
sol2=$case_dir'S2000O_s1_case_scopf__solution2.txt'
#sol2=$case_dir'S2000O_s2_case_scopf__solution2.txt'
det=$case_dir'detail.csv'

# run it
python test.py "$raw" "$rop" "$con" "$inl" "$sol1" "$sol2" "$det"
