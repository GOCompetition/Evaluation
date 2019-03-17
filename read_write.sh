#!/bin/sh

case_dir='./examples/case2/'
raw=$case_dir'case.raw'
rop=$case_dir'case.rop'
con=$case_dir'case.con'
inl=$case_dir'case.inl'

# run it
python read_write.py "$raw1" "$rop1" "$con1" "$inl1" "$raw2" "$rop2" "$con2" "$inl2"
