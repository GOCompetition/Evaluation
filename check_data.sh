#!/bin/sh

#case_dir='./examples/case2/'
#raw=$case_dir'case.raw'
#rop=$case_dir'case.rop'
#con=$case_dir'case.con'
#inl=$case_dir'case.inl'

# uw case
case_dir='./examples/test11/'
raw=$case_dir'case.raw'
#rop=$case_dir'case.rop'
rop=$case_dir'casev2.rop'
con=$case_dir'case.con'
inl=$case_dir'case.inl'

# run it
python check_data.py "$raw" "$rop" "$con" "$inl"
