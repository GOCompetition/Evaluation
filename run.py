'''
old syntax ??
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
    #parser.add_argument('summary', help='summary')
    #parser.add_argument('detail', help='detail')
    
    args = parser.parse_args()
    
    try:
        (obj, cost, penalty, max_hard_viol, max_soft_viol) = evaluation.run(
            args.raw,
            args.rop,
            args.con,
            args.inl,
            args.sol1,
            args.sol2,
            #args.summary,
            #args.detail,
            #0,
            #0,
)
    except:
        print "exception in evaluation.run"
        raise

if __name__ == '__main__':
    run()
