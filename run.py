'''
Arun, please copy or revise this file as you need
Jesse will continue to use test.py and test.sh for further development of the evaluation script
'''

import argparse
import evaluation
import csv
    
def run():

    raw = './examples/case2/case.raw'
    rop = './examples/case2/case.rop'
    con = './examples/case2/case.con'
    inl = './examples/case2/case.inl'
    sol1 = './examples/case2/sol1.txt'
    sol2 = './examples/case2/sol2.txt'
    summary = './summary.csv'
    detail = './detail.csv'
    
    try:
        (obj, cost, penalty, max_obj_viol, max_nonobj_viol, infeas) = evaluation.run(
            raw, rop, con, inl, sol1, sol2, summary, detail)
    except:
        print("exception in evaluation.run")
        raise
    else:
        """process obj, cost, penalty, max_obj_viol, max_nonobj_viol, infeas
        e.g. add info, e.g. run time or a scenario name, and append to a report file"""

if __name__ == '__main__':
    run()
