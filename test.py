'''
syntax:

from a command prompt:
python test.py raw rop con inl sol1 sol2 summary detail

from a Python interpreter:
import sys
sys.argv = [raw, rop, con, inl, sol1, sol2, summary, detail]
execfile("test.py")
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
    parser.add_argument('summary', help='summary')
    parser.add_argument('detail', help='detail')
    
    args = parser.parse_args()
    
    try:
        (obj, cost, penalty, max_obj_viol, max_nonobj_viol, infeas) = evaluation.run(
            args.raw,
            args.rop,
            args.con,
            args.inl,
            args.sol1,
            args.sol2,
            args.summary,
            args.detail,
        )
    except:
        print("exception in evaluation.run")
        raise
    else:
        """process obj, cost, penalty, max_obj_viol, max_nonobj_viol, infeas
        e.g. add info, e.g. run time or a scenario name, and append to a report file"""

if __name__ == '__main__':
    run()
