'''
syntax:

from a command prompt:
python read_write.py raw rop con inl

from a Python interpreter:
import sys
sys.argv = [raw, rop, con, inl]
execfile("read_write.py")
'''

import argparse
import time

# gocomp imports
import data
    
def main():

    parser = argparse.ArgumentParser(description='Evaluate a solution to a problem instance')
    
    parser.add_argument('raw', help='raw')
    parser.add_argument('rop', help='rop')
    parser.add_argument('con', help='con')
    parser.add_argument('inl', help='inl')
    
    args = parser.parse_args()

    raw_in = args.raw
    rop_in = args.rop
    con_in = args.con
    inl_in = args.inl

    raw_out = raw_in + '.out'
    rop_out = rop_in + '.out'
    con_out = con_in + '.out'
    inl_out = inl_in + '.out'

    start_time = time.time()
    p = data.Data()
    p.raw.read(raw_in)
    p.rop.read(rop_in)
    p.con.read(con_in)
    p.inl.read(inl_in)
    time_elapsed = time.time() - start_time
    print("read data time: %f" % time_elapsed)
    
    # show data stats
    print("buses: %u" % len(p.raw.buses))
    print("loads: %u" % len(p.raw.loads))
    print("fixed_shunts: %u" % len(p.raw.fixed_shunts))
    print("generators: %u" % len(p.raw.generators))
    print("nontransformer_branches: %u" % len(p.raw.nontransformer_branches))
    print("transformers: %u" % len(p.raw.transformers))
    print("areas: %u" % len(p.raw.areas))
    print("switched_shunts: %u" % len(p.raw.switched_shunts))
    print("generator inl records: %u" % len(p.inl.generator_inl_records))
    print("generator dispatch records: %u" % len(p.rop.generator_dispatch_records))
    print("active power dispatch records: %u" % len(p.rop.active_power_dispatch_records))
    print("piecewise linear cost functions: %u" % len(p.rop.piecewise_linear_cost_functions))
    print('contingencies: %u' % len(p.con.contingencies))

    start_time = time.time()
    p.raw.set_operating_point_to_offline_solution()
    p.raw.switched_shunts_combine_blocks_steps()
    end_time = time.time()
    print("convert data time: %f" % (end_time - start_time))

    start_time = time.time()
    p.raw.write(raw_out)
    #p.rop.write(rop_out)
    #p.con.write(con_out)
    #p.inl.write(inl_out)
    time_elapsed = time.time() - start_time
    print("write data time: %f" % time_elapsed)

if __name__ == '__main__':
    main()
