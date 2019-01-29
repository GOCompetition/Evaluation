#!/bin/sh

#case_dir='./examples/case2/'
#raw=$case_dir'case.raw'
#rop=$case_dir'case.rop'
#con=$case_dir'case.con'
#inl=$case_dir'case.inl'

case_dir='./examples/test7/'
raw=$case_dir'case.raw'
rop=$case_dir'case.rop'
con=$case_dir'case.con'
inl=$case_dir'case.inl'

# run it
python read_write.py "$raw" "$rop" "$con" "$inl"
