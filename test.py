'''
old syntax ??

syntax
python test.py <raw> <rop> <con> <inl> <sol1> <sol2> <det>

'''

import argparse
import evaluation
import csv
    
def run():

    parser = argparse.ArgumentParser(description='Evaluate a solution to a problem instance')
    
    parser.add_argument('raw', help='raw')
    parser.add_argument('rop', help='rop')
    parser.add_argument('con', help='con')
    parser.add_argument('inl', help='inl')
    parser.add_argument('sol1', help='sol1')
    parser.add_argument('sol2', help='sol2')
    parser.add_argument('det', help='detail')
    
    args = parser.parse_args()
    
    try:
        (obj, cost, penalty, max_obj_viol, max_nonobj_viol) = evaluation.run(
            args.raw,
            args.rop,
            args.con,
            args.inl,
            args.sol1,
            args.sol2,
            args.det,
        )
    except:
        print "exception in evaluation.run"
        raise
    else:
        """process obj, cost, penalty, max_obj_viol, max_nonobj_viol
        e.g. add info, e.g. run time or a scenario name, and append to a report file"""

if __name__ == '__main__':
    run()
