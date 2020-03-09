#!/bin/sh

case_dir='./examples/case2/'
raw1=$case_dir'case.raw'
rop1=$case_dir'case.rop'
con1=$case_dir'case.con'
inl1=$case_dir'case.inl'
raw2=$case_dir'case_clean.raw'
rop2=$case_dir'case_clean.rop'
con2=$case_dir'case_clean.con'
inl2=$case_dir'case_clean.inl'

# run it
python convert_data.py "$raw1" "$rop1" "$con1" "$inl1" "$raw2" "$rop2" "$con2" "$inl2"
