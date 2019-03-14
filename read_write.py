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
    
    parser.add_argument('raw_in', help='raw_in')
    parser.add_argument('rop_in', help='rop_in')
    parser.add_argument('con_in', help='con_in')
    parser.add_argument('inl_in', help='inl_in')
    parser.add_argument('raw_out', help='raw_out')
    parser.add_argument('rop_out', help='rop_out')
    parser.add_argument('con_out', help='con_out')
    parser.add_argument('inl_out', help='inl_out')
    
    args = parser.parse_args()

    start_time = time.time()
    p = data.Data()
    p.raw.read(args.raw_in)
    p.rop.read(args.rop_in)
    p.con.read(args.con_in)
    p.inl.read(args.inl_in)
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
    p.raw.write(args.raw_out)
    p.rop.write(args.rop_out)
    #p.con.write(args.con_out)
    p.inl.write(args.inl_out)
    time_elapsed = time.time() - start_time
    print("write data time: %f" % time_elapsed)

if __name__ == '__main__':
    main()
