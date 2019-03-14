#!/bin/sh

#case_dir='./examples/case2/'
#raw=$case_dir'case.raw'
#rop=$case_dir'case.rop'
#con=$case_dir'case.con'
#inl=$case_dir'case.inl'

# test6 - ieee14 from Carleton
case_dir='./examples/test6/'
raw1=$case_dir'case_test.raw'
rop1=$case_dir'case.rop'
con1=$case_dir'case.con'
inl1=$case_dir'case.inl'
raw2=$case_dir'case_test_fixed.raw'
rop2=$case_dir'case_fixed.rop'
con2=$case_dir'case_fixed.con'
inl2=$case_dir'case_fixed.inl'

#case_dir='./examples/test7/'
#raw=$case_dir'case.raw'
#rop=$case_dir'case.rop'
#con=$case_dir'case.con'
#inl=$case_dir'case.inl'

# run it
python read_write.py "$raw1" "$rop1" "$con1" "$inl1" "$raw2" "$rop2" "$con2" "$inl2"
