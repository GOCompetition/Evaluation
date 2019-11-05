"""
version 3
WIP
use numpy arrays for all the main quantities in
data and solutions for base case and each contingency.
use lists and dictionaries to keep track of bus number, etc.
in a contingency, evaluate full set of flows, then zero out
entries corresponding to outaged elements.
use scipy sparse matrices to store bus-branch incidence info
and matrix-vector product to compute bus power imbalance.
"""

import csv
import math
import data
import time
#from collections import OrderedDict
from itertools import islice
import numpy as np
import pandas as pd
import traceback
from scipy import sparse as sp
#from io import open
#import StringIO
#import cStringIO
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
from operator import itemgetter

"""
TODO
write output in data units, not p.u.
write summary with only worst contingency for each category
numpy
process scenarios in parallel
"""

# how long in between ctg eval log entries
log_time = 10

# when used for evaluation, should have debug=False
debug = False

# soft constraint penalty parameters
penalty_block_pow_real_max = [2.0, 50.0] # MW. when converted to p.u., this is overline_sigma_p in the formulation
penalty_block_pow_real_coeff = [1000.0, 5000.0, 1000000.0] # USD/MW-h. when converted USD/p.u.-h this is lambda_p in the formulation
penalty_block_pow_imag_max = [2.0, 50.0] # MVar. when converted to p.u., this is overline_sigma_q in the formulation
penalty_block_pow_imag_coeff = [1000.0, 5000.0, 1000000.0] # USD/MVar-h. when converted USD/p.u.-h this is lambda_q in the formulation
penalty_block_pow_abs_max = [2.0, 50.0] # MVA. when converted to p.u., this is overline_sigma_s in the formulation
penalty_block_pow_abs_coeff = [1000.0, 5000.0, 1000000.0] # USD/MWA-h. when converted USD/p.u.-h this is lambda_s in the formulation

# weight on base case in objective
base_case_penalty_weight = 0.5 # dimensionless. corresponds to delta in the formulation

# tolerance on hard constraints
#hard_constr_tol = 0.0
#hard_constr_tol = 1e-12
hard_constr_tol = 1e-4

# pandas float precision for reading from solution files
# None: ordinary converter, 'high', 'round_trip'
pandas_float_precision=None
#pandas_float_precision='round_trip'

def eval_piecewise_linear_penalty(residual, penalty_block_max, penalty_block_coeff):
    '''residual, penaltyblock_max, penalty_block_coeff are 1-dimensional numpy arrays'''

    r = residual
    num_block = len(penalty_block_coeff)
    num_block_bounded = len(penalty_block_max)
    assert(num_block_bounded + 1 == num_block)
    num_resid = r.size
    abs_resid = np.abs(r)
    #penalty_block_max_extended = np.concatenate((penalty_block_max, np.inf))
    remaining_resid = abs_resid
    penalty = np.zeros(num_resid)
    for i in range(num_block):
        #block_min = penalty_block_cumul_min[i]
        #block_max = penalty_block_cumul_max[i]
        block_coeff = penalty_block_coeff[i]
        if i < num_block - 1:
            block_max = penalty_block_max[i]
            penalized_resid = np.minimum(block_max, remaining_resid)
            penalty += block_coeff * penalized_resid
            remaining_resid -= penalized_resid
        else:
            penalty += block_coeff * remaining_resid
    return penalty

def extra_max(keys, values):
    '''values is a numpy array, keys is a list with len=values.size.
    returns (k,v) where v is the maximum of values and k is the
    corresponding key'''

    if values.size == 0:
        return (None, 0.0)
    else:
        index = np.argmax(values)
        key = keys[index]
        value = values[index]
        return (key, value)

def clean_string(s):
    t = s.replace("'","").replace('"','').replace(' ','')
    #t = str(s).replace("'","").replace('"','').replace(' ','')
    return t

def count_lines(file_name):

    #return simplecount(file_name)
    #return file_len(file_name)
    return rawgencount(file_name)

def simplecount(filename):
    lines = 0
    with open(filename) as f:
        for line in f:
            lines += 1
    return lines

def file_len(fname):
    start_time = time.time()
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    end_time = time.time()
    print('file_len time: %f' % (end_time - start_time))
    return i + 1

def _make_gen(reader):
    b = reader(1024 * 1024)
    while b:
        yield b
        b = reader(1024*1024)

def rawgencount(filename):
    start_time = time.time()
    f = open(filename, 'rb')
    f_gen = _make_gen(f.read) # py2
    #f_gen = _make_gen(f.raw.read) # py3
    count = sum( buf.count(b'\n') for buf in f_gen )
    f.close()
    end_time = time.time()
    print('rawgencount time: %f' % (end_time - start_time))
    return count

def get_ctg_block_size(num_bus, num_gen):
        
    return(num_bus + num_gen + 10)

def get_sol2_num_lines_expected(num_bus, num_gen, num_ctg):

    return(num_ctg * get_ctg_block_size(num_bus, num_gen))

def check_sol2_num_lines(sol2_name, num_bus, num_gen, num_ctg):

    expected = get_sol2_num_lines_expected(num_bus, num_gen, num_ctg)
    found = count_lines(sol2_name)
    print('sol2 num lines expected: %u' % expected)
    print('sol2 num lines found: %u' % found)
    if found < expected:
        print('sol2 num lines error')
        raise Exception('sol2 num lines error. expected: %u, found: %u' % (expected, found))
    else:
        print('sol2 num lines ok')

def get_sol2_ctg_labels(sol2_name, num_bus, num_gen, num_ctg):

    start_time = time.time()
    ctg_labels = []
    if num_ctg > 0:
        ctg_block_size = get_ctg_block_size(num_bus, num_gen)
        line_nums_to_find = [ctg_block_size * k + 2 for k in range(num_ctg)]
        num_ctgs_found = 0
        line_num_to_find = line_nums_to_find[num_ctgs_found]
        line_num_current = 0
        f = open(sol2_name)
        #f = open(sol2_name, 'rb', 1024*1024)
        for line in f:
            if line_num_current == line_num_to_find:
                ctg_labels.append(clean_string(line.strip())) # put back
                num_ctgs_found += 1
                if num_ctgs_found == num_ctg:
                    break
                else:
                    line_num_to_find = line_nums_to_find[num_ctgs_found]
            line_num_current += 1
        f.close()
    end_time = time.time()
    print('get_sol2_ctg_labels time: %f' % (end_time - start_time))
    return ctg_labels

def check_sol2_ctg_labels(sol2_name, num_bus, num_gen, ctg_labels_data_list):

    print('checking contingency labels sol vs data')
    num_ctg = len(ctg_labels_data_list)
    ctg_labels_sol_list = get_sol2_ctg_labels(sol2_name, num_bus, num_gen, num_ctg)
    #ctg_labels_sol_list = ctg_labels_data_list
    ctg_labels_data = set(ctg_labels_data_list)
    ctg_labels_sol = set(ctg_labels_sol_list)
    ctg_labels_data_minus_sol = ctg_labels_data - ctg_labels_sol
    ctg_labels_sol_minus_data = ctg_labels_sol - ctg_labels_data
    message = (
        'sol2 num ctgs data (list): %u, sol (list): %u, data: %u, sol: %u data - sol: %u, sol - data: %u' % (
            len(ctg_labels_data_list),
            len(ctg_labels_sol_list),
            len(ctg_labels_data),
            len(ctg_labels_sol),
            len(ctg_labels_data_minus_sol),
            len(ctg_labels_sol_minus_data)))
    print(message)
    if(len(ctg_labels_data_list) != len(ctg_labels_data)):
        raise Exception('repeated contingency label in data. %s' % message)
    elif (len(ctg_labels_sol_list) != len(ctg_labels_sol)):
        raise Exception('repeated contingency label in sol. %s' % message)
    elif (len(ctg_labels_data_minus_sol) != 0):
        raise Exception('contingency label in data not in sol. %s. labels[0]: %s' % (message, list(ctg_labels_data_minus_sol)[0]))
    elif (len(ctg_labels_sol_minus_data) != 0):
        raise Exception('contingency label in sol not in data. %s. labels[0]: %s' % (message, list(ctg_labels_sol_minus_data)[0]))
    else:
        print('sol2 ctg labels ok')

class Result:

    def __init__(self, ctgs):

        self.obj_all = 0.0
        self.cost_all = 0.0
        self.penalty_all = 0.0
        self.infeas_all = 1 # starts out infeasible
        self.ctgs = [k for k in ctgs]

        #base case
        self.obj = 0.0
        self.cost = 0.0
        self.penalty = 0.0
        self.infeas = 1
        self.max_bus_volt_mag_max_viol = (None, 0.0)
        self.max_bus_volt_mag_min_viol = (None, 0.0)
        self.max_bus_swsh_adm_imag_max_viol = (None, 0.0)
        self.max_bus_swsh_adm_imag_min_viol = (None, 0.0)
        self.max_bus_pow_balance_real_viol = (None, 0.0)
        self.max_bus_pow_balance_imag_viol = (None, 0.0)
        self.max_gen_pow_real_max_viol = (None, 0.0)
        self.max_gen_pow_real_min_viol = (None, 0.0)
        self.max_gen_pow_imag_max_viol = (None, 0.0)
        self.max_gen_pow_imag_min_viol = (None, 0.0)
        self.max_line_curr_orig_mag_max_viol = (None, 0.0)
        self.max_line_curr_dest_mag_max_viol = (None, 0.0)
        self.max_xfmr_pow_orig_mag_max_viol = (None, 0.0)
        self.max_xfmr_pow_dest_mag_max_viol = (None, 0.0)

        #ctgs
        self.ctg_obj = {k:0.0 for k in ctgs}
        self.ctg_cost = {k:0.0 for k in ctgs}
        self.ctg_penalty = {k:0.0 for k in ctgs}
        self.ctg_infeas = {k:1 for k in ctgs}
        self.ctg_max_bus_volt_mag_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_bus_volt_mag_min_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_bus_swsh_adm_imag_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_bus_swsh_adm_imag_min_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_bus_pow_balance_real_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_bus_pow_balance_imag_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_gen_pow_real_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_gen_pow_real_min_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_gen_pow_imag_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_gen_pow_imag_min_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_gen_pvpq1_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_gen_pvpq2_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_line_curr_orig_mag_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_line_curr_dest_mag_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_xfmr_pow_orig_mag_max_viol = {k:(None, 0.0) for k in ctgs}
        self.ctg_max_xfmr_pow_dest_mag_max_viol = {k:(None, 0.0) for k in ctgs}

        #reduce_ctg
        self.total_obj = 0.0
        self.total_cost = 0.0
        self.total_penalty = 0.0
        self.max_ctg_infeas = (None, 1)
        self.max_ctg_max_bus_volt_mag_max_viol = (None, 0.0)
        self.max_ctg_max_bus_volt_mag_min_viol = (None, 0.0)
        self.max_ctg_max_bus_swsh_adm_imag_max_viol = (None, 0.0)
        self.max_ctg_max_bus_swsh_adm_imag_min_viol = (None, 0.0)
        self.max_ctg_max_bus_pow_balance_real_viol = (None, 0.0)
        self.max_ctg_max_bus_pow_balance_imag_viol = (None, 0.0)
        self.max_ctg_max_gen_pow_real_max_viol = (None, 0.0)
        self.max_ctg_max_gen_pow_real_min_viol = (None, 0.0)
        self.max_ctg_max_gen_pow_imag_max_viol = (None, 0.0)
        self.max_ctg_max_gen_pow_imag_min_viol = (None, 0.0)
        self.max_ctg_max_gen_pvpq1_viol = (None, 0.0)
        self.max_ctg_max_gen_pvpq2_viol = (None, 0.0)
        self.max_ctg_max_line_curr_orig_mag_max_viol = (None, 0.0)
        self.max_ctg_max_line_curr_dest_mag_max_viol = (None, 0.0)
        self.max_ctg_max_xfmr_pow_orig_mag_max_viol = (None, 0.0)
        self.max_ctg_max_xfmr_pow_dest_mag_max_viol = (None, 0.0)

    def reduce_ctg(self):

        def compute_max_ctg_one_component(x):
            if len(x) == 0:
                return (None, 0.0)
            else:
                k = max(x.keys(), key=(lambda k: x[k][1]))
                return (k, x[k])
        
        self.total_obj = sum(self.ctg_obj.values())
        self.total_cost = sum(self.ctg_cost.values())
        self.total_penalty = sum(self.ctg_penalty.values())
        self.max_ctg_infeas = max(self.ctg_infeas.values())
        self.max_ctg_max_bus_volt_mag_max_viol = compute_max_ctg_one_component(self.ctg_max_bus_volt_mag_max_viol)
        self.max_ctg_max_bus_volt_mag_min_viol = compute_max_ctg_one_component(self.ctg_max_bus_volt_mag_min_viol)
        self.max_ctg_max_bus_swsh_adm_imag_max_viol = compute_max_ctg_one_component(self.ctg_max_bus_swsh_adm_imag_max_viol)
        self.max_ctg_max_bus_swsh_adm_imag_min_viol = compute_max_ctg_one_component(self.ctg_max_bus_swsh_adm_imag_min_viol)
        self.max_ctg_max_bus_pow_balance_real_viol = compute_max_ctg_one_component(self.ctg_max_bus_pow_balance_real_viol)
        self.max_ctg_max_bus_pow_balance_imag_viol = compute_max_ctg_one_component(self.ctg_max_bus_pow_balance_imag_viol)
        self.max_ctg_max_gen_pow_real_max_viol = compute_max_ctg_one_component(self.ctg_max_gen_pow_real_max_viol)
        self.max_ctg_max_gen_pow_real_min_viol = compute_max_ctg_one_component(self.ctg_max_gen_pow_real_min_viol)
        self.max_ctg_max_gen_pow_imag_max_viol = compute_max_ctg_one_component(self.ctg_max_gen_pow_imag_max_viol)
        self.max_ctg_max_gen_pow_imag_min_viol = compute_max_ctg_one_component(self.ctg_max_gen_pow_imag_min_viol)
        self.max_ctg_max_gen_pvpq1_viol = compute_max_ctg_one_component(self.ctg_max_gen_pvpq1_viol)
        self.max_ctg_max_gen_pvpq2_viol = compute_max_ctg_one_component(self.ctg_max_gen_pvpq2_viol)
        self.max_ctg_max_line_curr_orig_mag_max_viol = compute_max_ctg_one_component(self.ctg_max_line_curr_orig_mag_max_viol)
        self.max_ctg_max_line_curr_dest_mag_max_viol = compute_max_ctg_one_component(self.ctg_max_line_curr_dest_mag_max_viol)
        self.max_ctg_max_xfmr_pow_orig_mag_max_viol = compute_max_ctg_one_component(self.ctg_max_xfmr_curr_orig_mag_max_viol)
        self.max_ctg_max_xfmr_pow_dest_mag_max_viol = compute_max_ctg_one_component(self.ctg_max_xfmr_curr_dest_mag_max_viol)

    def convert_units(self):

        #self.obj
        #self.cost
        #self.penalty
        #self.infeas
        #self.max_bus_volt_mag_max_viol
        #self.max_bus_volt_mag_min_viol
        self.max_bus_swsh_adm_imag_max_viol *= self.base_mva
        self.max_bus_swsh_adm_imag_min_viol *= self.base_mva
        self.max_bus_pow_balance_real_viol *= self.base_mva
        self.max_bus_pow_balance_imag_viol *= self.base_mva
        self.max_gen_pow_real_max_viol *= self.base_mva
        self.max_gen_pow_real_min_viol *= self.base_mva
        self.max_gen_pow_imag_max_viol *= self.base_mva
        self.max_gen_pow_imag_min_viol *= self.base_mva
        self.max_line_curr_orig_mag_max_viol *= self.base_mva
        self.max_line_curr_dest_mag_max_viol *= self.base_mva
        self.max_xfmr_pow_orig_mag_max_viol *= self.base_mva
        self.max_xfmr_pow_dest_mag_max_viol *= self.base_mva

        #self.ctg_obj
        #self.ctg_cost
        #self.ctg_penalty
        #self.ctg_infeas
        for k in ctgs:
            #self.ctg_max_bus_volt_mag_max_viol[k][1]
            #self.ctg_max_bus_volt_mag_min_viol[k][1]
            self.ctg_max_bus_swsh_adm_imag_max_viol[k][1] *= self.base_mva
            self.ctg_max_bus_swsh_adm_imag_min_viol[k][1] *= self.base_mva
            self.ctg_max_bus_pow_balance_real_viol[k][1] *= self.base_mva
            self.ctg_max_bus_pow_balance_imag_viol[k][1] *= self.base_mva
            self.ctg_max_gen_pow_real_max_viol[k][1] *= self.base_mva
            self.ctg_max_gen_pow_real_min_viol[k][1] *= self.base_mva
            self.ctg_max_gen_pow_imag_max_viol[k][1] *= self.base_mva
            self.ctg_max_gen_pow_imag_min_viol[k][1] *= self.base_mva
            #self.ctg_max_gen_pvpq1_viol[k][1]
            #self.ctg_max_gen_pvpq2_viol[k][1]
            self.ctg_max_line_curr_orig_mag_max_viol[k][1] *= self.base_mva
            self.ctg_max_line_curr_dest_mag_max_viol[k][1] *= self.base_mva
            self.ctg_max_xfmr_pow_orig_mag_max_viol[k][1] *= self.base_mva
            self.ctg_max_xfmr_pow_dest_mag_max_viol[k][1] *= self.base_mva

    def write_detail(self, file_name):

        pass

    def write_summary(self, file_name):

        pass

def get_ctg_num_lines(file_name):
    '''this is slow since it reads the sol2 file.
    use Evaluation.get_ctg_num_lines() instead,
    which relies on knowing the problem dimensions.'''

    ctg_start_str = '--con'
    num_lines = 0
    start_time = time.time()
    # readlines reads all the lines into a list.
    # uses too much memory
    '''
    with open(file_name, 'r') as in_file:
        for l in in_file.readlines():
            if l.startswith(ctg_start_str):
                ctg_start_lines.append(line_counter)
            line_counter += 1
            if line_counter >= 1000:
                break
    '''
    # readline is slow but it keeps the memory down
    # there are some improvements that can be made while reading one line at a time
    # best may be to determine ctg_start_lines by a calculation from num_ctg, num_bus, num_gen
    # which are known from the problem data rather than reading solution2
    '''
    with open(file_name, 'r') as in_file:
        ctg_start_lines = []
        line_counter = 0
        line = in_file.readline()
        while line:
            if line[:5] == '--con':
            #if line.startswith(ctg_start_str):
                ctg_start_lines.append(line_counter)
            line_counter += 1
            line = in_file.readline()
            if line_counter >= int(1e7):
                break
        num_lines = line_counter
    '''
    #'''
    with open(file_name, 'r') as in_file:
        ctg_start_lines = []
        line_counter = 0
        for line in in_file:
            if line[:5] == '--con':
            #if line.startswith(ctg_start_str):
                ctg_start_lines.append(line_counter)
            line_counter += 1
            #if line_counter >= int(1e7):
            #    break
        num_lines = line_counter
    #'''
    '''
    with open(file_name, 'r') as in_file:
        ctg_start_lines = []
        line_counter = 0
        for line in in_file:
            if line[:5] == '--con':
            #if line.startswith(ctg_start_str):
                ctg_start_lines.append(line_counter)
            line_counter += 1
            if line_counter >= int(1e7):
                break
        num_lines = line_counter
    '''
    end_time = time.time()
    time_elapsed = end_time - start_time
    #print('get_ctg_num_lines time: %f' % time_elapsed)
    num_ctgs = len(ctg_start_lines)
    #print('num ctg from sol2: %u' % num_ctgs)
    #print('ctg_start_lines[:3]:')
    #print(ctg_start_lines[:3])
    ctg_end_lines = [
        ctg_start_lines[i + 1]
        for i in range(num_ctgs - 1)]
    ctg_end_lines += [num_lines]
    ctg_num_lines = [
        ctg_end_lines[i] - ctg_start_lines[i]
        for i in range(num_ctgs)]
    #num_ctgs = 10
    #num_lines_per_ctg = 33536
    #ctg_num_lines = num_ctgs * [num_lines_per_ctg]
    return ctg_num_lines #todo1
    #return ctg_num_lines[0:30] #todo1

class Evaluation:
    '''In per unit convention, i.e. same as the model'''

    def __init__(self):

        #self.pow_pen = MVAPEN
        self.bus = []
        self.load = []
        self.fxsh = []
        self.gen = []
        self.line = []
        self.xfmr = []
        self.area = []
        self.swsh = []
        self.ctg = []
        
        self.bus_volt_mag_min = {}
        self.bus_volt_mag_max = {}
        self.bus_volt_mag = {}
        self.bus_volt_ang = {}
        self.bus_volt_mag_min_viol = {}
        self.bus_volt_mag_max_viol = {}
        self.bus_pow_balance_real_viol = {}
        self.bus_pow_balance_imag_viol = {}
        #self.swsh_status = {}
        #self.swsh_adm_imag_min = {}
        #self.swsh_adm_imag_max = {}
        self.bus_swsh_adm_imag_min = {}
        self.bus_swsh_adm_imag_max = {}
        self.bus_swsh_adm_imag_min_viol = {}
        self.bus_swsh_adm_imag_max_viol = {}
        self.bus_swsh_adm_imag = {}

        self.load_const_pow_real = {}
        self.load_const_pow_imag = {}
        #self.load_const_curr_real = {}
        #self.load_const_curr_imag = {}
        #self.load_const_adm_real = {}
        #self.load_const_adm_imag = {}
        self.load_pow_real = {}
        self.load_pow_imag = {}
        self.load_status = {}

        self.fxsh_adm_real = {}
        self.fxsh_adm_imag = {}
        self.fxsh_pow_real = {}
        self.fxsh_pow_imag = {}
        self.fxsh_status = {}

        #self.gen_reg_bus = {}
        self.gen_pow_real_min = {}
        self.gen_pow_real_max = {}
        self.gen_pow_imag_min = {}
        self.gen_pow_imag_max = {}
        self.gen_part_fact = {}
        self.gen_pow_real = {}
        self.gen_pow_imag = {}
        self.gen_pow_real_min_viol = {}
        self.gen_pow_real_max_viol = {}
        self.gen_pow_imag_min_viol = {}
        self.gen_pow_imag_max_viol = {}
        self.gen_status = {}

        self.line_adm_real = {}
        self.line_adm_imag = {}
        self.line_adm_ch_imag = {}
        self.line_curr_mag_max = {}
        #self.line_curr_orig_real = {}
        #self.line_curr_orig_imag = {}
        #self.line_curr_dest_real = {}
        #self.line_curr_dest_imag = {}
        self.line_pow_orig_real = {}
        self.line_pow_orig_imag = {}
        self.line_pow_dest_real = {}
        self.line_pow_dest_imag = {}
        self.line_curr_orig_mag_max_viol = {}
        self.line_curr_dest_mag_max_viol = {}
        self.line_status = {}

        self.xfmr_adm_real = {}
        self.xfmr_adm_imag = {}
        self.xfmr_adm_mag_real = {}
        self.xfmr_adm_mag_imag = {}
        self.xfmr_tap_mag = {}
        self.xfmr_tap_ang = {}
        self.xfmr_pow_mag_max = {}
        #self.xfmr_curr_orig_real = {}
        #self.xfmr_curr_orig_imag = {}
        #self.xfmr_curr_dest_real = {}
        #self.xfmr_curr_dest_imag = {}
        self.xfmr_pow_orig_real = {}
        self.xfmr_pow_orig_imag = {}
        self.xfmr_pow_dest_real = {}
        self.xfmr_pow_dest_imag = {}
        self.xfmr_pow_orig_mag_max_viol = {}
        self.xfmr_pow_dest_mag_max_viol = {}
        self.xfmr_status = {}

        self.swsh_adm_imag_min = {}
        self.swsh_adm_imag_max = {}
        self.swsh_status = {}

        self.ctg_label = ""

        self.ctg_bus_volt_mag = {}
        self.ctg_bus_volt_ang = {}
        self.ctg_bus_volt_mag_max_viol = {}
        self.ctg_bus_volt_mag_min_viol = {}
        self.ctg_bus_pow_balance_real_viol = {}
        self.ctg_bus_pow_balance_imag_viol = {}
        self.ctg_bus_swsh_adm_imag = {}
        self.ctg_bus_swsh_adm_imag_min_viol = {}
        self.ctg_bus_swsh_adm_imag_max_viol = {}

        self.ctg_load_pow_real = {}
        self.ctg_load_pow_imag = {}

        self.ctg_fxsh_pow_real = {}
        self.ctg_fxsh_pow_imag = {}

        self.ctg_gen_active = {}
        #self.ctg_gen_pow_fact = {}
        self.ctg_gen_pow_real = {}
        self.ctg_gen_pow_imag = {}
        self.ctg_gen_pow_real_min_viol = {}
        self.ctg_gen_pow_real_max_viol = {}
        self.ctg_gen_pow_imag_min_viol = {}
        self.ctg_gen_pow_imag_max_viol = {}

        #self.ctg_line_curr_orig_real = {}
        #self.ctg_line_curr_orig_imag = {}
        #self.ctg_line_curr_dest_real = {}
        #self.ctg_line_curr_dest_imag = {}
        self.ctg_line_pow_orig_real = {}
        self.ctg_line_pow_orig_imag = {}
        self.ctg_line_pow_dest_real = {}
        self.ctg_line_pow_dest_imag = {}
        self.ctg_line_curr_orig_mag_max_viol = {}
        self.ctg_line_curr_dest_mag_max_viol = {}
        self.ctg_line_active = {}

        #self.ctg_xfmr_curr_orig_real = {}
        #self.ctg_xfmr_curr_orig_imag = {}
        #self.ctg_xfmr_curr_dest_real = {}
        #self.ctg_xfmr_curr_dest_imag = {}
        self.ctg_xfmr_pow_orig_real = {}
        self.ctg_xfmr_pow_orig_imag = {}
        self.ctg_xfmr_pow_dest_real = {}
        self.ctg_xfmr_pow_dest_imag = {}
        self.ctg_xfmr_pow_orig_mag_max_viol = {}
        self.ctg_xfmr_pow_dest_mag_max_viol = {}
        self.ctg_xfmr_active = {}

        #self.area_ctg_affected = {}
        #self.area_ctg_pow_real_change = {}

        self.gen_num_pl = {}
        self.gen_pl_x = {}
        self.gen_pl_y = {}

    def get_base_num_lines(self):
        '''compute the number of lines for each section in the sol1 file
        sol1 file looks like:
          --bus
          header
          num_bus data rows
          --gen
          header
          num_gen data rows
        '''

    def get_ctg_num_lines(self):
        '''compute the number of lines for each contingency in the sol2 file
        num_lines = 10 + num_bus + num_gen
        ctg_num_lines = num_ctg * [num_lines]
        sol2 file looks like:
          --ctg
          header
          1 data row
          --bus
          header
          num_bus data rows
          --gen
          header
          num_gen data rows
          --delta
          header
          1 data row
        '''

        num_lines = 10 + self.num_bus + self.num_gen
        ctg_num_lines = self.num_ctg * [num_lines]
        return ctg_num_lines

    def set_data_sets(self, data):

        start_time = time.time()
        #self.bus = [r.i for r in data.raw.buses.values()]
        #self.load = [(r.i,r.id) for r in data.raw.loads.values()]
        #self.fxsh = [(r.i,r.id) for r in data.raw.fixed_shunts.values()]
        #self.gen = [(r.i,r.id) for r in data.raw.generators.values()]
        #self.line = [(r.i,r.j,r.ckt) for r in data.raw.nontransformer_branches.values()]
        #self.xfmr = [(r.i,r.j,r.ckt) for r in data.raw.transformers.values()]
        #self.swsh = [r.i for r in data.raw.switched_shunts.values()]
        #self.area = [r.i for r in data.raw.areas.values()]
        end_time = time.time()
        print('set data sets: %f' % (end_time - start_time))

    def set_data_scalars(self, data):

        start_time = time.time()
        self.base_mva = data.raw.case_identification.sbase
        end_time = time.time()
        print('set data scalars: %f' % (end_time - start_time))

    def set_data_bus_params(self, data):

        start_time = time.time()
        buses = list(data.raw.buses.values())
        self.num_bus = len(buses)
        self.bus_i = [r.i for r in buses]
        self.bus_map = {self.bus_i[i]:i for i in range(len(self.bus_i))}
        self.bus_volt_mag_max = np.array([r.nvhi for r in buses])
        self.bus_volt_mag_min = np.array([r.nvlo for r in buses])
        self.ctg_bus_volt_mag_max = np.array([r.evhi for r in buses])
        self.ctg_bus_volt_mag_min = np.array([r.evlo for r in buses])
        
        areas = [r.area for r in buses]
        self.num_area = len(areas)
        self.area_i = [i for i in areas]
        self.area_map = dict(zip(self.area_i, range(self.num_area)))

        self.bus_area = [self.area_map[r.area] for r in buses]
        end_time = time.time()
        print('set data bus params: %f' % (end_time - start_time))

    def set_data_load_params(self, data):

        start_time = time.time()
        loads = list(data.raw.loads.values())
        self.num_load = len(loads)
        self.load_i = [r.i for r in loads]
        self.load_id = [r.id for r in loads]
        self.load_bus = [self.bus_map[self.load_i[i]] for i in range(self.num_load)]
        self.load_map = {(self.load_i[i], self.load_id[i]):i for i in range(self.num_load)}
        self.load_status = np.array([r.status for r in loads])
        self.load_const_pow_real = np.array([r.pl / self.base_mva for r in loads]) * self.load_status
        self.load_const_pow_imag = np.array([r.ql / self.base_mva for r in loads]) * self.load_status
        self.bus_load_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_load)],
             (self.load_bus, list(range(self.num_load)))),
            (self.num_bus, self.num_load))
        self.bus_load_const_pow_real = self.bus_load_matrix.dot(self.load_const_pow_real)
        self.bus_load_const_pow_imag = self.bus_load_matrix.dot(self.load_const_pow_imag)
        end_time = time.time()
        print('set data load params: %f' % (end_time - start_time))

    def set_data_fxsh_params(self, data):

        start_time = time.time()
        fxshs = list(data.raw.fixed_shunts.values())
        self.num_fxsh = len(fxshs)
        self.fxsh_i = [r.i for r in fxshs]
        self.fxsh_id = [r.id for r in fxshs]
        self.fxsh_bus = [self.bus_map[self.fxsh_i[i]] for i in range(self.num_fxsh)]
        self.fxsh_map = {(self.fxsh_i[i], self.fxsh_id[i]):i for i in range(self.num_fxsh)}
        self.fxsh_status = np.array([r.status for r in fxshs])
        self.fxsh_adm_real = np.array([r.gl / self.base_mva for r in fxshs]) * self.fxsh_status
        self.fxsh_adm_imag = np.array([r.bl / self.base_mva for r in fxshs]) * self.fxsh_status
        self.bus_fxsh_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_fxsh)],
             (self.fxsh_bus, list(range(self.num_fxsh)))),
            (self.num_bus, self.num_fxsh))
        self.bus_fxsh_adm_real = self.bus_fxsh_matrix.dot(self.fxsh_adm_real)
        self.bus_fxsh_adm_imag = self.bus_fxsh_matrix.dot(self.fxsh_adm_imag)
        end_time = time.time()
        print('set data fxsh params: %f' % (end_time - start_time))

    def set_data_gen_params(self, data):
    
        start_time = time.time()
        gens = list(data.raw.generators.values())
        self.gen_key = [(r.i, r.id) for r in gens]
        self.num_gen = len(gens)
        self.gen_i = [r.i for r in gens]
        self.gen_id = [r.id for r in gens]
        self.gen_bus = [self.bus_map[self.gen_i[i]] for i in range(self.num_gen)]
        self.gen_map = {(self.gen_i[i], self.gen_id[i]):i for i in range(self.num_gen)}
        self.gen_status = np.array([r.stat for r in gens])
        self.gen_pow_imag_max = np.array([r.qt / self.base_mva for r in gens]) * self.gen_status
        self.gen_pow_imag_min = np.array([r.qb / self.base_mva for r in gens]) * self.gen_status
        self.gen_pow_real_max = np.array([r.pt / self.base_mva for r in gens]) * self.gen_status
        self.gen_pow_real_min = np.array([r.pb / self.base_mva for r in gens]) * self.gen_status
        gen_part_fact = {(r.i, r.id) : r.r for r in data.inl.generator_inl_records.values()}
        self.gen_part_fact = np.array([gen_part_fact[(r.i, r.id)] for r in gens]) * self.gen_status
        self.bus_gen_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_gen)],
             (self.gen_bus, list(range(self.num_gen)))),
            (self.num_bus, self.num_gen))
        #self.bus_gen = {i:[] for i in range(self.num_bus)}
        #for i in range(self.num_gen):
        #    self.bus_gen[self.gen_bus[i]].append(i)

        #for i in range(self.num_gen):
        #    if self.gen_i[i] == 630653:
        #        gi = self.gen_i[i]
        #        gid = self.gen_id[i]
        #        print([gi, gid, self.gen_map[(gi, gid)]])

        self.gen_area = [self.bus_area[r] for r in self.gen_bus]
        self.area_gens = [set() for a in range(self.num_area)]
        for i in range(self.num_gen):
            self.area_gens[self.gen_area[i]].add(i)
        self.gen_out_of_service = [
            i for i in range(self.num_gen)
            if self.gen_status[i] == 0.0]
        print('num gen in service: %u, out of service: %u' % (self.num_gen - len(self.gen_out_of_service), len(self.gen_out_of_service)))

        end_time = time.time()
        print('set data gen params: %f' % (end_time - start_time))

    def set_data_line_params(self, data):
        
        start_time = time.time()
        lines = list(data.raw.nontransformer_branches.values())
        self.line_key = [(r.i, r.j, r.ckt) for r in lines]
        self.num_line = len(lines)
        self.line_i = [r.i for r in lines]
        self.line_j = [r.j for r in lines]
        self.line_ckt = [r.ckt for r in lines]
        self.line_orig_bus = [self.bus_map[self.line_i[i]] for i in range(self.num_line)]
        self.line_dest_bus = [self.bus_map[self.line_j[i]] for i in range(self.num_line)]
        self.line_map = {(self.line_i[i], self.line_j[i], self.line_ckt[i]):i for i in range(self.num_line)}
        self.line_status = np.array([r.st for r in lines])
        self.line_adm_real = np.array([r.r / (r.r**2.0 + r.x**2.0) for r in lines]) * self.line_status
        self.line_adm_imag = np.array([-r.x / (r.r**2.0 + r.x**2.0) for r in lines]) * self.line_status
        self.line_adm_ch_imag = np.array([r.b for r in lines]) * self.line_status
        self.line_adm_total_imag = self.line_adm_imag + 0.5 * self.line_adm_ch_imag
        self.line_curr_mag_max = np.array([r.ratea / self.base_mva for r in lines]) # todo - normalize by bus base kv???
        self.ctg_line_curr_mag_max = np.array([r.ratec / self.base_mva for r in lines]) # todo - normalize by bus base kv???
        self.bus_line_orig_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_line)],
             (self.line_orig_bus, list(range(self.num_line)))),
            (self.num_bus, self.num_line))
        self.bus_line_dest_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_line)],
             (self.line_dest_bus, list(range(self.num_line)))),
            (self.num_bus, self.num_line))
        #self.bus_line_orig = {i:[] for i in range(self.num_bus)}
        #self.bus_line_dest = {i:[] for i in range(self.num_bus)}
        #for i in range(self.num_line):
        #    self.bus_line_orig[self.line_orig_bus[i]].append(i)
        #    self.bus_line_dest[self.line_dest_bus[i]].append(i)
        end_time = time.time()
        print('set data line params: %f' % (end_time - start_time))

    def set_data_xfmr_params(self, data):

        start_time = time.time()
        xfmrs = list(data.raw.transformers.values())
        self.xfmr_key = [(r.i, r.j, r.ckt) for r in xfmrs]
        self.num_xfmr = len(xfmrs)
        self.xfmr_i = [r.i for r in xfmrs]
        self.xfmr_j = [r.j for r in xfmrs]
        self.xfmr_ckt = [r.ckt for r in xfmrs]
        self.xfmr_orig_bus = [self.bus_map[self.xfmr_i[i]] for i in range(self.num_xfmr)]
        self.xfmr_dest_bus = [self.bus_map[self.xfmr_j[i]] for i in range(self.num_xfmr)]
        self.xfmr_map = {(self.xfmr_i[i], self.xfmr_j[i], self.xfmr_ckt[i]):i for i in range(self.num_xfmr)}
        self.xfmr_status = np.array([r.stat for r in xfmrs])
        self.xfmr_adm_real = np.array([r.r12 / (r.r12**2.0 + r.x12**2.0) for r in xfmrs]) * self.xfmr_status
        self.xfmr_adm_imag = np.array([-r.x12 / (r.r12**2.0 + r.x12**2.0) for r in xfmrs]) * self.xfmr_status
        self.xfmr_adm_mag_real = np.array([r.mag1 for r in xfmrs]) * self.xfmr_status # todo normalize?
        self.xfmr_adm_mag_imag = np.array([r.mag2 for r in xfmrs]) * self.xfmr_status # todo normalize?
        self.xfmr_tap_mag = np.array([(r.windv1 / r.windv2) if r.stat else 1.0 for r in xfmrs]) # note status field is used here
        self.xfmr_tap_ang = np.array([r.ang1 * math.pi / 180.0 for r in xfmrs]) * self.xfmr_status
        self.xfmr_pow_mag_max = np.array([r.rata1 / self.base_mva for r in xfmrs]) # todo check normalization
        self.ctg_xfmr_pow_mag_max = np.array([r.ratc1 / self.base_mva for r in xfmrs]) # todo check normalization
        self.bus_xfmr_orig_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_xfmr)],
             (self.xfmr_orig_bus, list(range(self.num_xfmr)))),
            (self.num_bus, self.num_xfmr))
        self.bus_xfmr_dest_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_xfmr)],
             (self.xfmr_dest_bus, list(range(self.num_xfmr)))),
            (self.num_bus, self.num_xfmr))
        #self.bus_xfmr_orig = {i:[] for i in range(self.num_bus)}
        #self.bus_xfmr_dest = {i:[] for i in range(self.num_bus)}
        #for i in range(self.num_xfmr):
        #    self.bus_xfmr_orig[self.xfmr_orig_bus[i]].append(i)
        #    self.bus_xfmr_dest[self.xfmr_dest_bus[i]].append(i)
        end_time = time.time()
        print('set data xfmr params: %f' % (end_time - start_time))

    def set_data_swsh_params(self, data):

        start_time = time.time()
        # swsh
        swshs = list(data.raw.switched_shunts.values())
        self.num_swsh = len(swshs)
        self.swsh_i = [r.i for r in swshs]
        self.swsh_bus = [self.bus_map[self.swsh_i[i]] for i in range(self.num_swsh)]
        self.swsh_map = {self.swsh_i[i]:i for i in range(self.num_swsh)}
        self.swsh_status = np.array([r.stat for r in swshs])
        self.swsh_adm_imag_max = np.array([0.0 for r in swshs])
        self.swsh_adm_imag_min = np.array([0.0 for r in swshs])
        for i in range(self.num_swsh):
            r = swshs[i]
            if r.stat > 0:
                rn = [r.n1, r.n2, r.n3, r.n4, r.n5, r.n6, r.n7, r.n8]
                rb = [r.b1, r.b2, r.b3, r.b4, r.b5, r.b6, r.b7, r.b8]
                for j in range(8):
                    if rn[j] > 0:
                        if rb[j] < 0.0:
                            self.swsh_adm_imag_min[i] += float(rn[j]) * rb[j] / self.base_mva
                        elif rb[j] > 0.0:
                            self.swsh_adm_imag_max[i] += float(rn[j]) * rb[j] / self.base_mva
                        else:
                            break
                    else:
                        break
        self.bus_swsh_matrix = sp.csc_matrix(
            ([1.0 for i in range(self.num_swsh)],
             (self.swsh_bus, list(range(self.num_swsh)))),
            (self.num_bus, self.num_swsh))
        self.bus_swsh_adm_imag_max = self.bus_swsh_matrix.dot(self.swsh_adm_imag_max)
        self.bus_swsh_adm_imag_min = self.bus_swsh_matrix.dot(self.swsh_adm_imag_min)
        #self.bus_swsh = {i:[] for i in range(self.num_bus)}
        #for i in range(self.num_swsh):
        #    self.bus_swsh[self.swsh_bus[i]].append(i)
        #self.bus_swsh_adm_imag_max = np.array([
        #    np.sum(self.swsh_adm_imag_max[self.bus_swsh[i]])
        #    for i in range(self.num)])
        #self.bus_swsh_adm_imag_min = np.array([
        #    np.sum(self.swsh_adm_imag_min[self.bus_swsh[i]])
        #    for i in range(self.num)])
        end_time = time.time()
        print('set data swsh params: %f' % (end_time - start_time))

    def set_data_gen_cost_params(self, data):

        start_time = time.time()
        # todo clean up maybe
        # defines some attributes that need to be initialized above
        # piecewise linear cost functions
        
        self.gen_num_pl = [0 for i in range(self.num_gen)]
        self.gen_pl_x = [None for i in range(self.num_gen)]
        self.gen_pl_y = [None for i in range(self.num_gen)]
        for r in data.rop.generator_dispatch_records.values():
            r_bus = r.bus
            r_genid = r.genid
            gen = self.gen_map[(r_bus, r_genid)]
            r_dsptbl = r.dsptbl
            s = data.rop.active_power_dispatch_records[r_dsptbl]
            r_ctbl = s.ctbl
            t = data.rop.piecewise_linear_cost_functions[r_ctbl]
            r_npairs = t.npairs
            self.gen_num_pl[gen] = r_npairs
            self.gen_pl_x[gen] = np.zeros(r_npairs)
            self.gen_pl_y[gen] = np.zeros(r_npairs)
            for i in range(r_npairs):
                self.gen_pl_x[gen][i] = t.points[i].x / self.base_mva
                self.gen_pl_y[gen][i] = t.points[i].y
            # from here on is checking assumptions and cleaning data - this should be done in a separate module to release clean datasets only
            assert(r_npairs > 1)
            for i in range(r_npairs - 1):
                assert (self.gen_pl_x[gen][i + 1] - self.gen_pl_x[gen][i]) >= 0.0
            i_to_keep = [0]
            for i in range(r_npairs - 1):
                if self.gen_pl_x[gen][i + 1] > self.gen_pl_x[gen][i]:
                    i_to_keep.append(i + 1)
            self.gen_num_pl[gen] = len(i_to_keep)
            self.gen_pl_x[gen] = [self.gen_pl_x[gen][i] for i in i_to_keep]
            self.gen_pl_y[gen] = [self.gen_pl_y[gen][i] for i in i_to_keep]
            # check cost function convexity - this should be done in a separate module
            #'''
            if self.gen_num_pl[gen] > 2:
                d1 = [
                    ((self.gen_pl_y[gen][i + 1] - self.gen_pl_y[gen][i]) /
                     (self.gen_pl_x[gen][i + 1] - self.gen_pl_x[gen][i]))
                    for i in range(self.gen_num_pl[gen] - 1)]
                d2 = [(d1[i + 1] - d1[i]) for i in range(self.gen_num_pl[gen] - 2)]
                for i in range(len(d2)):
                    if d2[i] < 0.0:
                        print('cost convexity error')
                        print('gen i: %s' % r_bus)
                        print('gen id: %s' % r_genid)
                        print('num pairs: %s' % r_npairs)
                        print('pairs:')
                        print([(t.points[i].x, t.points[i].y) for i in range(r_npairs)])
                        #print(self.gen_num_pl[gen])
                        print('x points:')
                        print(self.gen_pl_x[gen])
                        print('y points:')
                        print(self.gen_pl_y[gen])
                        print('i: %s' % i)
                        print('slopes:')
                        print(d1)
                        #raise Exception('cost convexity error') # 
            #'''
        end_time = time.time()
        print('set data gen cost params: %f' % (end_time - start_time))

    def set_data_ctg_params(self, data):
        # contingency records
        # this section was pretty long (40 s) - much reduced now, < 1 s (see below)

        start_time = time.time()
        ctgs = data.con.contingencies.values()
        self.num_ctg = len(ctgs)
        self.ctg_label = [r.label for r in ctgs]
        self.ctg_map = dict(zip(self.ctg_label, range(self.num_ctg)))
        line_keys = set(self.line_key)
        xfmr_keys = set(self.xfmr_key)
        ctg_gen_keys_out = {
            r.label:set([(e.i, e.id) for e in r.generator_out_events])
            for r in ctgs}
        ctg_branch_keys_out = {
            r.label:set([(e.i, e.j, e.ckt) for e in r.branch_out_events])
            for r in ctgs}
        ctg_line_keys_out = {k:(v & line_keys) for k,v in ctg_branch_keys_out.items()}
        ctg_xfmr_keys_out = {k:(v & xfmr_keys) for k,v in ctg_branch_keys_out.items()}
        ctg_areas_affected = {
            k.label:(
                set([self.bus_area[self.bus_map[r[0]]] for r in ctg_gen_keys_out[k.label]]) |
                set([self.bus_area[self.bus_map[r[0]]] for r in ctg_branch_keys_out[k.label]]) |
                set([self.bus_area[self.bus_map[r[1]]] for r in ctg_branch_keys_out[k.label]]))
            for k in ctgs}
        self.ctg_gens_out = [
            [self.gen_map[k] for k in ctg_gen_keys_out[self.ctg_label[i]]]
            for i in range(self.num_ctg)]
        self.ctg_lines_out = [
            [self.line_map[k] for k in ctg_line_keys_out[self.ctg_label[i]]]
            for i in range(self.num_ctg)]
        self.ctg_xfmrs_out = [
            [self.xfmr_map[k] for k in ctg_xfmr_keys_out[self.ctg_label[i]]]
            for i in range(self.num_ctg)]
        self.ctg_areas_affected = [
            ctg_areas_affected[self.ctg_label[i]]
            for i in range(self.num_ctg)]
        end_time = time.time()
        print('set data ctg params: %f' % (end_time - start_time))

    def set_data(self, data):
        ''' set values from the data object
        convert to per unit (p.u.) convention'''

        start_time = time.time()
        self.set_data_scalars(data)
        self.set_data_bus_params(data)
        self.set_data_load_params(data)
        self.set_data_fxsh_params(data)
        self.set_data_gen_params(data)
        self.set_data_line_params(data)
        self.set_data_xfmr_params(data)
        self.set_data_swsh_params(data)
        self.set_data_gen_cost_params(data)
        self.set_data_ctg_params(data)
        end_time = time.time()
        print('set data time: %f' % (end_time - start_time))

    def set_params(self):
        '''set parameters, e.g. tolerances, penalties, and convert to PU'''
        
        self.penalty_block_pow_real_max = np.array(penalty_block_pow_real_max) / self.base_mva
        self.penalty_block_pow_real_coeff = np.array(penalty_block_pow_real_coeff) * self.base_mva
        self.penalty_block_pow_imag_max = np.array(penalty_block_pow_imag_max) / self.base_mva
        self.penalty_block_pow_imag_coeff = np.array(penalty_block_pow_imag_coeff) * self.base_mva
        self.penalty_block_pow_abs_max = np.array(penalty_block_pow_abs_max) / self.base_mva
        self.penalty_block_pow_abs_coeff = np.array(penalty_block_pow_abs_coeff) * self.base_mva

    def set_solution1(self, solution1):
        ''' set values from the solution objects
        convert to per unit (p.u.) convention'''

        start_time = time.time()
        sol_bus_i = solution1.bus_df.i.values
        sol_gen_i = solution1.gen_df.i.values
        #print(solution1.gen_df.id)
        #sol_gen_id = solution1.gen_df.id.values
        sol_gen_id = map(clean_string, list(solution1.gen_df.id.values))

        #for i in range(self.num_gen):
        #    gi = sol_gen_i[i]
        #    gid = sol_gen_id[i]
        #    if gi == 630653:
        #        print( (gi, gid) )

        # which is faster? do the same for gens
        #sol_bus_map = {sol_bus_i[i]:i for i in range(self.num_bus)}
        sol_bus_map = dict(zip(sol_bus_i, list(range(self.num_bus))))

        #sol_gen_map = {(sol_gen_i[i], sol_gen_id[i]):i for i in range(self.num_gen)}
        sol_gen_key = zip(sol_gen_i, sol_gen_id)
        sol_gen_map = dict(zip(sol_gen_key, list(range(self.num_gen))))
        #print([sol_gen_i, sol_gen_id, sol_gen_key, sol_gen_map, self.gen_key])
        # up through here is fast enough ~ 0.001 s
        
        # which is faster?
        #bus_permutation = [sol_bus_map[self.bus_i[r]] for r in range(self.num_bus)] # this line is slow ~0.015s. is there a faster python-y way to do it?
        bus_permutation = [sol_bus_map[k] for k in self.bus_i]
        #bus_permutation = list(itemgetter(*(self.bus_i))(sol_bus_map))
        #bus_permutation = itemgetter(*(self.bus_i))(sol_bus_map) # this does not work - list is needed, unfortunately, and takes some time
        #a = {'foo':0, 'bar':1, 'baz':2}
        #b = ['bar', 'baz', 'foo']
        #print(str(*b))
        #perm = list(itemgetter(*b)(a))
        #vector = np.array([11,12,13])
        #print(vector[perm])
        #print(perm)
        #print(vector.flat[1,2,0])

        # up through here takes 0.015 s
        #gen_permutation = [sol_gen_map[(self.gen_i[r], self.gen_id[r])] for r in range(self.num_gen)]
        #gen_permutation = [sol_gen_map[self.gen_key[r]] for r in range(self.num_gen)]
        gen_permutation = [sol_gen_map[k] for k in self.gen_key]
        #gen_permutation = list(itemgetter(*(self.gen_key))(sol_gen_map))
        # up through here takes 0.015 s
        
        # need it to handle arbitrary bus order in solution files
        # is there a faster way to do it?
        # maybe arrange all the bus-indexed vectors in a matrix - not much time left to save though
        # multiplication by a permutation matrix?
        self.bus_volt_mag = solution1.bus_df.vm.values[bus_permutation]
        self.bus_volt_ang = solution1.bus_df.va.values[bus_permutation] * (math.pi / 180.0)
        self.bus_swsh_adm_imag = solution1.bus_df.b.values[bus_permutation] / self.base_mva
        self.gen_pow_real = solution1.gen_df.pg.values[gen_permutation] / self.base_mva
        self.gen_pow_imag = solution1.gen_df.qg.values[gen_permutation] / self.base_mva
        self.gen_bus_volt_mag = self.bus_volt_mag[self.gen_bus]
        # up through here is fast enough ~ 0.02 s (only 0.005 s from previous point)
        end_time = time.time()
        print('set sol1 time: %f' % (end_time - start_time))

    def set_solution2(self, solution2):
        ''' set values from the solution objects
        convert to per unit (p.u.) convention'''

        self.ctg_current = self.ctg_map[clean_string(solution2.ctg_label)]
        sol_bus_i = solution2.bus_df.i.values
        sol_gen_i = solution2.gen_df.i.values
        #sol_gen_id = solution2.gen_df.id.values
        sol_gen_id = map(clean_string, list(solution2.gen_df.id.values))
        sol_bus_map = dict(zip(sol_bus_i, list(range(self.num_bus))))
        sol_gen_key = zip(sol_gen_i, sol_gen_id)
        sol_gen_map = dict(zip(sol_gen_key, list(range(self.num_gen))))
        #bus_permutation = list(itemgetter(*(self.bus_i))(sol_bus_map))
        #gen_permutation = list(itemgetter(*(self.gen_key))(sol_gen_map))
        bus_permutation = [sol_bus_map[k] for k in self.bus_i]
        gen_permutation = [sol_gen_map[k] for k in self.gen_key]
        self.ctg_bus_volt_mag = solution2.bus_df.vm.values[bus_permutation]
        self.ctg_bus_volt_ang = solution2.bus_df.va.values[bus_permutation] * (math.pi / 180.0)
        self.ctg_bus_swsh_adm_imag = solution2.bus_df.b.values[bus_permutation] / self.base_mva
        #self.ctg_gen_pow_real = solution2.gen_df.pg.values[gen_permutation] / self.base_mva # ctg_gen_pow_real is computed, not read from data
        self.ctg_gen_pow_imag = solution2.gen_df.qg.values[gen_permutation] / self.base_mva
        self.ctg_pow_real_change = solution2.delta / self.base_mva
        self.ctg_gen_bus_volt_mag = self.ctg_bus_volt_mag[self.gen_bus]

    def set_ctg_data(self):
        '''need to set:
        ctg_gen_not_participating
        ctg_gen_out_of_service
        ctg_gen_pow_imag_min
        ctg_gen_pow_imag_max
        '''

        # this is not a significant time cost
        start_time = time.time()

        '''
        self.ctg_gen_not_participating = [i for i in range(self.num_gen)] # need to set this for real
        self.ctg_gen_out_of_service = [i for i in range(self.num_gen)] # need to set this for real
        self.ctg_gen_pow_imag_min = self.gen_pow_imag_min.copy() # need to zero out generators not in service
        self.ctg_gen_pow_imag_max = self.gen_pow_imag_max.copy() # need to zero out generators not in service
        '''

        #'''
        gens_out_of_service = set(self.gen_out_of_service) | set(self.ctg_gens_out[self.ctg_current])
        areas_affected = self.ctg_areas_affected[self.ctg_current]
        gens_participating = set([g for a in areas_affected for g in self.area_gens[a]])
        gens_participating = gens_participating - gens_out_of_service
        gens_not_participating = set(range(self.num_gen)) - gens_participating
        self.ctg_gen_out_of_service = sorted(list(gens_out_of_service))
        self.ctg_gen_not_participating = sorted(list(gens_not_participating))
        self.ctg_gen_pow_imag_min = self.gen_pow_imag_min.copy() # base case p/q min/max already are 0.0 for generators out of service in the base case
        self.ctg_gen_pow_imag_max = self.gen_pow_imag_max.copy()
        self.ctg_gen_pow_imag_min[self.ctg_gen_out_of_service] = 0.0 # set q min/max to 0.0 for generators going out of service in current contingency - p not needed
        self.ctg_gen_pow_imag_max[self.ctg_gen_out_of_service] = 0.0
        #'''

        end_time = time.time()
        #print('set ctg data time: %f' % (end_time - start_time))

    def write_header(self, det_name):
        """write header line for detailed output
        the detailed output file has a header row, then a row for the base case, then a row for each contingency.
        each row is a comma separated list of fields.

        A short description of each field is given in the end of line comment after each field name in the code below.
        The description gives references to the relevant equations in the formulation,
        specified by the equation numbers in the formulation document in parentheses.
        Formulation numbers in the document may change as they are generated automatically,
        but reasonable efforts are made to keep the descriptions here consistent with the document.
        Most of the fields come in (idx, val) pairs, where idx refers to the index or key of the maximum violation in
        a class of constraints, and val refers to the value of the maximum violation.
        Most of the fields apply to the individual contingency or base case specified in the current row.
        The one exception is the 'obj' field, which gives the cumulative objective value for the base
        case and all contingencies up through the current row.
        """

        with open(det_name, 'w') as out:
        #with open(det_name, 'w', newline='') as out:
        #with open(det_name, 'w', newline='', encoding='utf-8') as out:
        #with open(det_name, 'wb') as out:
            csv_writer = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(
                ['ctg', # contingency label for the current contingency, empty if base case
                 'infeas', # binary indicator of infeasibility for the base case or contingency of the current row - 1 indicates infeasible
                 'pen', # penalty value on soft constraint violations in the base case or current contingency (1,6-31)
                 'cost', # generator cost (base case only), 0 in contingencies (1-5)
                 'obj', # obj, = pen + cost, cumulative (i.e. base case + all ctgs through the current row) (1)
                 'vmax-idx', # bus number of maximum violation of bus voltage magnitude upper bounds (32,58)
                 'vmax-val', # value of maximum violation of bus voltage magnitude upper bounds (32,58)
                 'vmin-idx', # bus number of maximum violation of bus voltage magnitude lower bounds (32,58)
                 'vmin-val', # value of maximum violation of bus voltage magnitude lower bounds (32,58)
                 'bmax-idx', # bus number of maximum violation of switched shunt susceptance upper bounds (37,63)
                 'bmax-val', # value of maximum violation of switched shunt susceptance upper bounds (37,63)
                 'bmin-idx', # bus number of maximum violation of switched shunt susceptance lower bounds (37,63)
                 'bmin-val', # value of maximum violation of switched shunt susceptance lower bounds (37,63)
                 'pbal-idx', # bus number of maximum violation of real power balance contraints (46-48,72-74)
                 'pbal-val', # value of maximum violation of real power balance contraints (46-48,72-74)
                 'qbal-idx', # bus number of maximum violation of reactive power balance contraints (49-51,75-77)
                 'qbal-val', # value of maximum violation of reactive power balance contraints (49-51,75-77)
                 'pgmax-idx', # bus and unit id of maximum violation of generator real power upper bounds (33,34)
                 'pgmax-val', # value of maximum violation of generator real power upper bounds (33,34)
                 'pgmin-idx', # bus and unit id of maximum violation of generator real power lower bounds (33,34)
                 'pgmin-val', # value of maximum violation of generator real power lower bounds (33,34)
                 'qgmax-idx', # bus and unit id of maximum violation of generator reactive power upper bounds (35,36,61,62)
                 'qgmax-val', # value of maximum violation of generator reactive power upper bounds (35,36,61,62)
                 'qgmin-idx', # bus and unit id of maximum violation of generator reactive power lower bounds (35,36,61,62)
                 'qgmin-val', # value of maximum violation of generator reactive power lower bounds (35,36,61,62)
                 'qvg1-idx', # bus and unit id of maximum violation of generator pv/pq switching constraints of type 1 (undervoltage -> reactive power at max) (94)
                 'qvg1-val', # value of maximum violation of generator pv/pq switching constraints of type 1 (undervoltage -> reactive power at max)  (94)
                 'qvg2-idx', # bus and unit id of maximum violation of generator pv/pq switching constraints of type 2 (overvoltage -> reactive power at min) (95)
                 'qvg2-val', # value of maximum violation of generator pv/pq switching constraints of type 2 (overvoltage -> reactive power at min) (95)
                 'lineomax-idx', # origin destination and circuit id of maximum violation of line origin flow bounds (52,53,78,79)
                 'lineomax-val', # value of maximum violation of line origin flow bounds (52,53,78,79)
                 'linedmax-idx', # origin destination and circuit id of maximum violation of line destination flow bounds (53,54,79,80)
                 'linedmax-val', # value of maximum violation of line destination flow bounds (53,54,79,80)
                 'xfmromax-idx', # origin destination and circuit id of maximum violation of transformer origin flow bounds (55,56,81,82)
                 'xfmromax-val', # value of maximum violation of transformer origin flow bounds (55,56,81,82)
                 'xfmrdmax-idx', # origin destination and circuit id of maximum violation of transformer destination flow bounds (56,57,82,83)
                 'xfmrdmax-val', # value of maximum violation of transformer destination flow bounds (56,57,82,83)
            ])
            #'''

    def write_base(self, det_name):
        """write detail of base case evaluation"""

        with open(det_name, 'a') as out:
        #with open(det_name, 'a', newline='') as out:
        #with open(det_name, 'ab') as out:
            csv_writer = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(
                ['', self.infeas, self.penalty, self.cost, self.obj,
                 self.max_bus_volt_mag_max_viol[0],
                 self.max_bus_volt_mag_max_viol[1],
                 self.max_bus_volt_mag_min_viol[0],
                 self.max_bus_volt_mag_min_viol[1],
                 self.max_bus_swsh_adm_imag_max_viol[0],
                 self.max_bus_swsh_adm_imag_max_viol[1],
                 self.max_bus_swsh_adm_imag_min_viol[0],
                 self.max_bus_swsh_adm_imag_min_viol[1],
                 self.max_bus_pow_balance_real_viol[0],
                 self.max_bus_pow_balance_real_viol[1],
                 self.max_bus_pow_balance_imag_viol[0],
                 self.max_bus_pow_balance_imag_viol[1],
                 self.max_gen_pow_real_max_viol[0],
                 self.max_gen_pow_real_max_viol[1],
                 self.max_gen_pow_real_min_viol[0],
                 self.max_gen_pow_real_min_viol[1],
                 self.max_gen_pow_imag_max_viol[0],
                 self.max_gen_pow_imag_max_viol[1],
                 self.max_gen_pow_imag_min_viol[0],
                 self.max_gen_pow_imag_min_viol[1],
                 None,
                 0.0,
                 None,
                 0.0,
                 self.max_line_curr_orig_mag_max_viol[0],
                 self.max_line_curr_orig_mag_max_viol[1],
                 self.max_line_curr_dest_mag_max_viol[0],
                 self.max_line_curr_dest_mag_max_viol[1],
                 self.max_xfmr_pow_orig_mag_max_viol[0],
                 self.max_xfmr_pow_orig_mag_max_viol[1],
                 self.max_xfmr_pow_dest_mag_max_viol[0],
                 self.max_xfmr_pow_dest_mag_max_viol[1],
                 ])

    def print_base(self):
        """print out summary info on the base case"""

        print(
            "base case summary info: {infeasibility: %s, penalty: %s, cost: %s, objective: %s}" % (
                self.infeas, self.penalty, self.cost, self.obj))        

    def write_ctg(self, det_name):
        """write detail of ctg evaluation"""        

        with open(det_name, 'a') as out:
        #with open(det_name, 'a', newline='') as out:
        #with open(det_name, 'ab') as out:
            csv_writer = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(
                [self.ctg_label[self.ctg_current], self.ctg_infeas, self.ctg_penalty, 0.0, self.obj,
                 self.ctg_max_bus_volt_mag_max_viol[0],
                 self.ctg_max_bus_volt_mag_max_viol[1],
                 self.ctg_max_bus_volt_mag_min_viol[0],
                 self.ctg_max_bus_volt_mag_min_viol[1],
                 self.ctg_max_bus_swsh_adm_imag_max_viol[0],
                 self.ctg_max_bus_swsh_adm_imag_max_viol[1],
                 self.ctg_max_bus_swsh_adm_imag_min_viol[0],
                 self.ctg_max_bus_swsh_adm_imag_min_viol[1],
                 self.ctg_max_bus_pow_balance_real_viol[0],
                 self.ctg_max_bus_pow_balance_real_viol[1],
                 self.ctg_max_bus_pow_balance_imag_viol[0],
                 self.ctg_max_bus_pow_balance_imag_viol[1],
                 #self.ctg_max_gen_pow_real_max_viol[0],
                 #self.ctg_max_gen_pow_real_max_viol[1],
                 #self.ctg_max_gen_pow_real_min_viol[0],
                 #self.ctg_max_gen_pow_real_min_viol[1],
                 None,
                 0.0,
                 None,
                 0.0,
                 self.ctg_max_gen_pow_imag_max_viol[0],
                 self.ctg_max_gen_pow_imag_max_viol[1],
                 self.ctg_max_gen_pow_imag_min_viol[0],
                 self.ctg_max_gen_pow_imag_min_viol[1],
                 self.ctg_max_gen_pvpq1_viol[0],
                 self.ctg_max_gen_pvpq1_viol[1],
                 self.ctg_max_gen_pvpq2_viol[0],
                 self.ctg_max_gen_pvpq2_viol[1],
                 self.ctg_max_line_curr_orig_mag_max_viol[0],
                 self.ctg_max_line_curr_orig_mag_max_viol[1],
                 self.ctg_max_line_curr_dest_mag_max_viol[0],
                 self.ctg_max_line_curr_dest_mag_max_viol[1],
                 self.ctg_max_xfmr_pow_orig_mag_max_viol[0],
                 self.ctg_max_xfmr_pow_orig_mag_max_viol[1],
                 self.ctg_max_xfmr_pow_dest_mag_max_viol[0],
                 self.ctg_max_xfmr_pow_dest_mag_max_viol[1],
                 ])

    def eval_base(self):
        """evaluate base case violations"""

        start_time = time.time()
        self.eval_cost()
        self.eval_bus_volt_viol()
        self.eval_load_pow()
        self.eval_fxsh_pow()
        self.eval_gen_pow_viol()
        self.eval_line_pow()
        self.eval_line_curr_viol()
        self.eval_xfmr_pow()
        self.eval_xfmr_pow_viol()
        self.eval_bus_swsh_adm_imag_viol()
        self.eval_bus_swsh_pow()
        self.eval_bus_pow_balance()
        #self.print_bus_pow_balance()
        self.compute_detail()
        self.eval_infeas()
        self.eval_penalty()
        self.eval_obj()
        end_time = time.time()
        print("eval base time: %f" % (end_time - start_time))

    def eval_ctg(self):

        self.eval_ctg_bus_volt_viol()
        self.eval_ctg_load_pow()
        self.eval_ctg_fxsh_pow()
        self.eval_ctg_gen_pow_real()
        #self.eval_ctg_gen_pow_real_viol() # this is not used - ctg_gen_pow_real is computed by eval, and bounds are automatic
        self.eval_ctg_gen_pow_imag_viol()
        self.eval_ctg_line_pow()
        self.eval_ctg_line_curr_viol() 
        self.eval_ctg_xfmr_pow()
        self.eval_ctg_xfmr_pow_viol()
        self.eval_ctg_bus_swsh_adm_imag_viol()
        self.eval_ctg_bus_swsh_pow()
        self.eval_ctg_bus_pow_balance()
        #self.print_ctg_bus_pow_balance()
        self.eval_ctg_gen_pvpq_viol()
        self.compute_ctg_detail()
        self.eval_ctg_infeas()
        self.eval_ctg_penalty()
        self.eval_ctg_update_obj()
        self.eval_ctg_update_infeas()

    def eval_ctg_update_obj(self):

        self.obj += self.ctg_penalty

    def eval_ctg_update_infeas(self):

        if self.ctg_infeas > hard_constr_tol:
            self.infeas = 1
    
    def eval_cost(self):
        # Let [pcmin, pcmax] denote the domain of definition of the cost function
        # Let [pmin, pmax] denote the operating bounds of a generator that is in service
        # assume [pcmin, pcmax] is a subset of [pmin, pmax]
        # let pg denote the operating point
        #
        # if pg falls outside of [pcmin, pcmax] then it is outside of [pmin, pmax]
        # and therefore the solution is infeasible, so any cost we assign is not consequential
        # Thus it is ok if we assign cost 0 in this case
        # in general we assign cost 0 to generators that are out of service
        # assume the points on a generator cost curve are given in order of increasing p (i.e. x coordinate)
        # assume the generator cost curve is convex
        #
        # update 2019-01-22
        # no longer assume pg in [pcmin, pcmax]
        # assume >= 2 points on pc curve
        # assume pc x-points are strictly increasing
        # assume pc (x,y) points are convex (nondecreasing second differences)
        # extend first and last secants to left and right resp.
        # need a separate module for data checking independent of solution evaluation

        start_time = time.time()
        self.gen_cost = np.zeros(self.num_gen)

        for k in range(self.num_gen):
            num_pl = self.gen_num_pl[k]
            pl_x = self.gen_pl_x[k]
            pl_y = self.gen_pl_y[k]
            #print([num_pl, pl_x, pl_y])
            if self.gen_status[k] == 0.0:
                continue
            #if self.gen_pow_real[k] < pl_x[0]: # do not check these
            #    continue
            #if self.gen_pow_real[k] > pl_x[num_pl - 1]:
            #    continue
            y_value = 0.0
            slope = 0.0
            x_change = 0.0
            done = False
            for i in range(num_pl - 1): # i = 0 covers first secant and extension to left
                if self.gen_pow_real[k] <= pl_x[i + 1]:
                    y_value = pl_y[i]
                    slope = (pl_y[i + 1] - pl_y[i]) / (pl_x[i + 1] - pl_x[i])
                    x_change = self.gen_pow_real[k] - pl_x[i]
                    #if pl_x[i + 1] > pl_x[i]: # do not check this here. need an external data checker to ensure pl_x points are strictly increasing
                    #    slope = (pl_y[i + 1] - pl_y[i]) / (pl_x[i + 1] - pl_x[i])
                    #    x_change = self.gen_pow_real[k] - pl_x[i]
                    done = True
                    break
            if not done:
                #print([self.gen_i[k], self.gen_id[k], self.gen_num_pl[k], self.gen_pl_x[k], self.gen_pl_y[k], self.gen_pow_real[k]])
                assert (self.gen_pow_real[k] > pl_x[num_pl - 1]) # need to extend last secant to right
                i = num_pl - 2 # num_pl >= 2 (need at least 2 points for a secant)
                y_value = pl_y[i]
                slope = (pl_y[i + 1] - pl_y[i]) / (pl_x[i + 1] - pl_x[i])
                x_change = self.gen_pow_real[k] - pl_x[i]
            self.gen_cost[k] = y_value + slope * x_change
                

        '''
        self.gen_cost = {
            k:0.0
            for k in self.gen}
        for k in self.gen:
            if self.gen_status[k]:
                y_value = self.gen_pl_y[(k[0], k[1], self.gen_num_pl[k])]
                slope = 0.0
                x_change = 0.0
                pl = self.gen_num_pl[k]
                for i in range(1, self.gen_num_pl[k]):
                    if self.gen_pow_real[k] <= self.gen_pl_x[(k[0], k[1], i + 1)]:
                        y_value = self.gen_pl_y[(k[0], k[1], i)]
                        if self.gen_pl_x[(k[0], k[1], i + 1)] > self.gen_pl_x[(k[0], k[1], i)]:
                            slope = (
                                (self.gen_pl_y[(k[0], k[1], i + 1)] -
                                 self.gen_pl_y[(k[0], k[1], i)]) /
                                (self.gen_pl_x[(k[0], k[1], i + 1)] -
                                 self.gen_pl_x[(k[0], k[1], i)]))
                            x_change = (
                                self.gen_pow_real[k] -
                                self.gen_pl_x[(k[0], k[1], i)])
                        pl = i
                        break
                self.gen_cost[k] = y_value + slope * x_change
        #self.cost = sum([0.0] + self.gen_cost.values()) # cannot do this in Python3 - not sure we need it anyway - if we need it then convert second term to list
        self.cost = sum(self.gen_cost.values())
        '''

        self.cost = np.sum(self.gen_cost)
        end_time = time.time()
        print('eval cost time: %f' % (end_time - start_time))


    def eval_bus_volt_viol(self):

        self.bus_volt_mag_min_viol = np.maximum(0.0, self.bus_volt_mag_min - self.bus_volt_mag)
        self.bus_volt_mag_max_viol = np.maximum(0.0, self.bus_volt_mag - self.bus_volt_mag_max)

    def eval_load_pow(self):

        self.bus_load_pow_real = self.bus_load_const_pow_real
        self.bus_load_pow_imag = self.bus_load_const_pow_imag

    def eval_fxsh_pow(self):

        self.bus_fxsh_pow_real = self.bus_fxsh_adm_real * (self.bus_volt_mag ** 2.0)
        self.bus_fxsh_pow_imag = - self.bus_fxsh_adm_imag * (self.bus_volt_mag ** 2.0)

    def eval_gen_pow_viol(self):

        self.gen_pow_real_min_viol = np.maximum(0.0, self.gen_pow_real_min - self.gen_pow_real)
        self.gen_pow_real_max_viol = np.maximum(0.0, self.gen_pow_real - self.gen_pow_real_max)
        self.gen_pow_imag_min_viol = np.maximum(0.0, self.gen_pow_imag_min - self.gen_pow_imag)
        self.gen_pow_imag_max_viol = np.maximum(0.0, self.gen_pow_imag - self.gen_pow_imag_max)

    def eval_line_pow(self):

        '''
        if debug:
            iorig = 223
            idest = 224
            cid = '1'
            k = (iorig, idest, cid)
            print("debug line real power")
            print("(iorig, idest, cid): %s" % str(k))
            print("vm_orig: %s" % str(self.bus_volt_mag[iorig]))
            print("vm_dest: %s" % str(self.bus_volt_mag[idest]))
            print("va_orig (rad): %s" % str(self.bus_volt_ang[iorig]))
            print("va_dest (rad): %s" % str(self.bus_volt_ang[idest]))
            print("va_orig (deg): %s" % str(self.bus_volt_ang[iorig] * 180.0/math.pi))
            print("va_dest (deg): %s" % str(self.bus_volt_ang[idest] * 180.0/math.pi))
        '''

        start_time = time.time()
        self.line_orig_volt_mag = self.bus_volt_mag[self.line_orig_bus]
        self.line_dest_volt_mag = self.bus_volt_mag[self.line_dest_bus]
        self.line_volt_ang_diff = self.bus_volt_ang[self.line_orig_bus] - self.bus_volt_ang[self.line_dest_bus]
        self.line_cos_volt_ang_diff = np.cos(self.line_volt_ang_diff)
        self.line_sin_volt_ang_diff = np.sin(self.line_volt_ang_diff)
        self.line_orig_dest_volt_mag_prod = self.line_orig_volt_mag * self.line_dest_volt_mag
        self.line_orig_volt_mag_sq = self.line_orig_volt_mag ** 2.0
        self.line_dest_volt_mag_sq = self.line_dest_volt_mag ** 2.0
        # TODO some further factorization can be done, potentially giving more speedup
        self.line_pow_orig_real = ( # line_status not needed as we have already done it on the parameter level
            self.line_adm_real * self.line_orig_volt_mag_sq + # ** 2.0 +
            ( - self.line_adm_real * self.line_cos_volt_ang_diff
              - self.line_adm_imag * self.line_sin_volt_ang_diff) *
            self.line_orig_dest_volt_mag_prod)
        self.line_pow_orig_imag = (
            - self.line_adm_total_imag * self.line_orig_volt_mag_sq + # ** 2.0 +
            (   self.line_adm_imag * self.line_cos_volt_ang_diff
              - self.line_adm_real * self.line_sin_volt_ang_diff) *
            self.line_orig_dest_volt_mag_prod)
        self.line_pow_dest_real = (
            self.line_adm_real * self.line_dest_volt_mag_sq + # ** 2.0 +
            ( - self.line_adm_real * self.line_cos_volt_ang_diff
              + self.line_adm_imag * self.line_sin_volt_ang_diff) *
            self.line_orig_dest_volt_mag_prod)
        self.line_pow_dest_imag = (
            - self.line_adm_total_imag * self.line_dest_volt_mag_sq + # ** 2.0 +
            (   self.line_adm_imag * self.line_cos_volt_ang_diff
              + self.line_adm_real * self.line_sin_volt_ang_diff) *
            self.line_orig_dest_volt_mag_prod)
        end_time = time.time()
        print('eval line pow time: %f' % (end_time - start_time))

    def eval_line_curr_viol(self):

        self.line_curr_orig_mag_max_viol = np.maximum(
            0.0,
            (self.line_pow_orig_real**2.0 + self.line_pow_orig_imag**2.0)**0.5 -
            self.line_curr_mag_max * self.line_orig_volt_mag)
        self.line_curr_dest_mag_max_viol = np.maximum(
            0.0,
            (self.line_pow_dest_real**2.0 + self.line_pow_dest_imag**2.0)**0.5 -
            self.line_curr_mag_max * self.line_dest_volt_mag)

    def eval_xfmr_pow(self):

        start_time = time.time()
        self.xfmr_orig_volt_mag = self.bus_volt_mag[self.xfmr_orig_bus]
        self.xfmr_dest_volt_mag = self.bus_volt_mag[self.xfmr_dest_bus]
        self.xfmr_volt_ang_diff = self.bus_volt_ang[self.xfmr_orig_bus] - self.bus_volt_ang[self.xfmr_dest_bus] - self.xfmr_tap_ang
        self.xfmr_cos_volt_ang_diff = np.cos(self.xfmr_volt_ang_diff)
        self.xfmr_sin_volt_ang_diff = np.sin(self.xfmr_volt_ang_diff)
        self.xfmr_orig_dest_volt_mag_prod = self.xfmr_orig_volt_mag * self.xfmr_dest_volt_mag
        self.xfmr_orig_volt_mag_sq = self.xfmr_orig_volt_mag ** 2.0
        self.xfmr_dest_volt_mag_sq = self.xfmr_dest_volt_mag ** 2.0
        self.xfmr_pow_orig_real = (
            (self.xfmr_adm_real / self.xfmr_tap_mag**2.0 + self.xfmr_adm_mag_real) * self.xfmr_orig_volt_mag_sq +
            ( - self.xfmr_adm_real / self.xfmr_tap_mag * self.xfmr_cos_volt_ang_diff
              - self.xfmr_adm_imag / self.xfmr_tap_mag * self.xfmr_sin_volt_ang_diff) *
                self.xfmr_orig_volt_mag * self.xfmr_dest_volt_mag)
        self.xfmr_pow_orig_imag = (
            - (self.xfmr_adm_imag / self.xfmr_tap_mag**2.0 + self.xfmr_adm_mag_imag) * self.xfmr_orig_volt_mag_sq +
            (   self.xfmr_adm_imag / self.xfmr_tap_mag * self.xfmr_cos_volt_ang_diff
              - self.xfmr_adm_real / self.xfmr_tap_mag * self.xfmr_sin_volt_ang_diff) *
                self.xfmr_orig_volt_mag * self.xfmr_dest_volt_mag)
        self.xfmr_pow_dest_real = (
            self.xfmr_adm_real * self.xfmr_dest_volt_mag_sq +
            ( - self.xfmr_adm_real / self.xfmr_tap_mag * self.xfmr_cos_volt_ang_diff
              + self.xfmr_adm_imag / self.xfmr_tap_mag * self.xfmr_sin_volt_ang_diff) *
                self.xfmr_orig_volt_mag * self.xfmr_dest_volt_mag)
        self.xfmr_pow_dest_imag = (
            - self.xfmr_adm_imag * self.xfmr_dest_volt_mag_sq +
            (   self.xfmr_adm_imag / self.xfmr_tap_mag * self.xfmr_cos_volt_ang_diff
              + self.xfmr_adm_real / self.xfmr_tap_mag * self.xfmr_sin_volt_ang_diff) *
                self.xfmr_orig_volt_mag * self.xfmr_dest_volt_mag)
        end_time = time.time()
        print('eval xfmr pow time: %f' % (end_time - start_time))

    def eval_xfmr_pow_viol(self):

        self.xfmr_pow_orig_mag_max_viol = np.maximum(
            0.0,
            (self.xfmr_pow_orig_real**2.0 + self.xfmr_pow_orig_imag**2.0)**0.5 -
            self.xfmr_pow_mag_max)
        self.xfmr_pow_dest_mag_max_viol = np.maximum(
            0.0,
            (self.xfmr_pow_dest_real**2.0 + self.xfmr_pow_dest_imag**2.0)**0.5 -
            self.xfmr_pow_mag_max)

    def eval_bus_swsh_adm_imag_viol(self):

        self.bus_swsh_adm_imag_min_viol = np.maximum(0.0, self.bus_swsh_adm_imag_min - self.bus_swsh_adm_imag)
        self.bus_swsh_adm_imag_max_viol = np.maximum(0.0, self.bus_swsh_adm_imag - self.bus_swsh_adm_imag_max)

    def eval_bus_swsh_pow(self):

        self.bus_swsh_pow_imag = -self.bus_swsh_adm_imag * self.bus_volt_mag**2.0

    def print_bus_pow_balance(self):

        print("bus number:")
        print(self.bus_i)
        print("bus real power balance violation:")
        print(self.bus_pow_balance_real_viol)
        print("bus reactive power balance violation:")
        print(self.bus_pow_balance_imag_viol)

    def print_ctg_bus_pow_balance(self):

        print("bus number:")
        print(self.bus_i)
        print("ctg bus real power balance violation:")
        print(self.ctg_bus_pow_balance_real_viol)
        print("ctg bus reactive power balance violation:")
        print(self.ctg_bus_pow_balance_imag_viol)

    def eval_bus_pow_balance(self):

        if debug:
            i = 223
            print("debug base case real power balance")
            print("bus: %s", str(i))
            print("generators: %s" % str([(k, self.gen_status[k], self.gen_pow_real[k]) for k in self.bus_gen[i]]))
            print("loads: %s" % str([(k, self.load_status[k], self.load_pow_real[k]) for k in self.bus_load[i]]))
            print("fixed shunts: %s" % str([(k, self.fxsh_status[k], self.fxsh_pow_real[k]) for k in self.bus_fxsh[i]]))
            print("lines orig: %s" % str([(k, self.line_status[k], self.line_pow_orig_real[k]) for k in self.bus_line_orig[i]]))
            print("lines dest: %s" % str([(k, self.line_status[k], self.line_pow_dest_real[k]) for k in self.bus_line_dest[i]]))
            print("xfmrs orig: %s" % str([(k, self.xfmr_status[k], self.xfmr_pow_orig_real[k]) for k in self.bus_xfmr_orig[i]]))
            print("xfmrs dest: %s" % str([(k, self.xfmr_status[k], self.xfmr_pow_dest_real[k]) for k in self.bus_xfmr_dest[i]]))

        start_time = time.time()
        self.bus_pow_balance_real_viol = np.abs(
            self.bus_gen_matrix.dot(self.gen_pow_real) -
            self.bus_load_pow_real -
            self.bus_fxsh_pow_real -
            self.bus_line_orig_matrix.dot(self.line_pow_orig_real) -
            self.bus_line_dest_matrix.dot(self.line_pow_dest_real) -
            self.bus_xfmr_orig_matrix.dot(self.xfmr_pow_orig_real) -
            self.bus_xfmr_dest_matrix.dot(self.xfmr_pow_dest_real))
        self.bus_pow_balance_imag_viol = np.abs(
            self.bus_gen_matrix.dot(self.gen_pow_imag) -
            self.bus_load_pow_imag -
            self.bus_fxsh_pow_imag -
            self.bus_swsh_pow_imag -
            self.bus_line_orig_matrix.dot(self.line_pow_orig_imag) -
            self.bus_line_dest_matrix.dot(self.line_pow_dest_imag) -
            self.bus_xfmr_orig_matrix.dot(self.xfmr_pow_orig_imag) -
            self.bus_xfmr_dest_matrix.dot(self.xfmr_pow_dest_imag))
        end_time = time.time()
        print('eval bus pow balance time: %f' % (end_time - start_time))

    def eval_ctg_bus_volt_viol(self):

        self.ctg_bus_volt_mag_min_viol = np.maximum(0.0, self.ctg_bus_volt_mag_min - self.ctg_bus_volt_mag)
        self.ctg_bus_volt_mag_max_viol = np.maximum(0.0, self.ctg_bus_volt_mag - self.ctg_bus_volt_mag_max)

    def eval_ctg_load_pow(self):

        self.ctg_bus_load_pow_real = self.bus_load_const_pow_real
        self.ctg_bus_load_pow_imag = self.bus_load_const_pow_imag

    def eval_ctg_fxsh_pow(self):

        self.ctg_bus_fxsh_pow_real = self.bus_fxsh_adm_real * (self.ctg_bus_volt_mag ** 2.0)
        self.ctg_bus_fxsh_pow_imag = - self.bus_fxsh_adm_imag * (self.ctg_bus_volt_mag ** 2.0)

    def eval_ctg_gen_pow_real(self):

        '''
        i = 223
        uid = '1'
        k = 'GEN-688-1'
        g = (i, uid)
        if debug:
            if self.ctg_label == k:
                print('debug ctg gen real power evaluation')
                print('ctg: %s' % str(k))
                print('gen: %s' % str(g))
                print('participating: %s' % str(self.ctg_gen_participating[g]))
                print('pmax: %f' % self.gen_pow_real_max[g])
                print('pmin: %f' % self.gen_pow_real_min[g])
                print('pg: %f' % self.gen_pow_real[g])
                print('alphag: %f' % self.gen_part_fact[g])
                print('deltak: %f' % self.ctg_pow_real_change)
                print('pgk (from sol2): %f' % self.ctg_gen_pow_real[g])
        '''

        ''' debug
        debug = False
        ctg_label = 'G_000017SENECA33U1'
        gen_i = 17
        gen_id = '1'
        gen = self.gen_map[(gen_i, gen_id)]
        if self.ctg_label[self.ctg_current] == ctg_label:
            debug = True
            print('ctg_label: %s' % self.ctg_label[self.ctg_current])
            print('gen i: %s' % gen_i)
            print('gen id: %s' % gen_id)
            print('gen: %s' % gen)
            print('gen out of service:')
            print(self.gen_out_of_service)
            print('ctg gens out:')
            print(self.ctg_gens_out[self.ctg_current])
            print('ctg gen out of service:')
            print(self.ctg_gen_out_of_service)
            #gens_out_of_service = set(self.gen_out_of_service) | set(self.ctg_gens_out[self.ctg_current])
        '''

        # new method - not a significant time cost
        start_time = time.time()
        self.ctg_gen_pow_real = np.maximum(
            self.gen_pow_real_min,
            np.minimum(
                self.gen_pow_real_max,
                self.gen_pow_real + self.gen_part_fact * self.ctg_pow_real_change))
        self.ctg_gen_pow_real[self.ctg_gen_not_participating] = self.gen_pow_real[self.ctg_gen_not_participating]
        self.ctg_gen_pow_real[self.ctg_gen_out_of_service] = 0.0
        end_time = time.time()
        #print('eval ctg gen pow real time: %f' % (end_time - start_time))

        # old method
        '''
        self.ctg_gen_pow_real = {i:0.0 for i in self.gen}
        self.ctg_gen_pow_real.update(
            {i:self.gen_pow_real[i] for i in self.gen
             if self.ctg_gen_active[i]})
        self.ctg_gen_pow_real.update(
            {i:(max(self.gen_pow_real_min[i],
                    min(self.gen_pow_real_max[i],
                        self.gen_pow_real[i] +
                        self.gen_part_fact[i] *
                        self.ctg_pow_real_change)))
             for i in self.gen if self.ctg_gen_participating[i]})
        '''

        '''
        if debug:
            if self.ctg_label == k:
                print('pgk (computed): %f' % self.ctg_gen_pow_real[g])
        '''

    def eval_ctg_gen_pow_real_viol(self):

        self.ctg_gen_pow_real_min_viol = {
            i:max(0.0, (self.gen_pow_real_min[i] if self.ctg_gen_active[i] else 0.0) - self.ctg_gen_pow_real[i])
            for i in self.gen}
        self.ctg_gen_pow_real_max_viol = {
            i:max(0.0, self.ctg_gen_pow_real[i] - (self.gen_pow_real_max[i] if self.ctg_gen_active[i] else 0.0))
            for i in self.gen}

    def eval_ctg_gen_pow_imag_viol(self):

        self.ctg_gen_pow_imag_min_viol = np.maximum(0.0, self.ctg_gen_pow_imag_min - self.ctg_gen_pow_imag)
        self.ctg_gen_pow_imag_max_viol = np.maximum(0.0, self.ctg_gen_pow_imag - self.ctg_gen_pow_imag_max)

    def eval_ctg_line_pow(self):
        '''similar to base case.
        then zero out lines that are out of service'''

        self.ctg_line_orig_volt_mag = self.ctg_bus_volt_mag[self.line_orig_bus]
        self.ctg_line_dest_volt_mag = self.ctg_bus_volt_mag[self.line_dest_bus]
        self.ctg_line_volt_ang_diff = self.ctg_bus_volt_ang[self.line_orig_bus] - self.ctg_bus_volt_ang[self.line_dest_bus]
        self.ctg_line_cos_volt_ang_diff = np.cos(self.ctg_line_volt_ang_diff)
        self.ctg_line_sin_volt_ang_diff = np.sin(self.ctg_line_volt_ang_diff)
        self.ctg_line_orig_dest_volt_mag_prod = self.ctg_line_orig_volt_mag * self.ctg_line_dest_volt_mag
        self.ctg_line_orig_volt_mag_sq = self.ctg_line_orig_volt_mag ** 2.0
        self.ctg_line_dest_volt_mag_sq = self.ctg_line_dest_volt_mag ** 2.0
        # TODO some further factorization can be done, potentially giving more speedup
        self.ctg_line_pow_orig_real = (
            self.line_adm_real * self.ctg_line_orig_volt_mag_sq + # ** 2.0 +
            ( - self.line_adm_real * self.ctg_line_cos_volt_ang_diff
              - self.line_adm_imag * self.ctg_line_sin_volt_ang_diff) *
            self.ctg_line_orig_dest_volt_mag_prod)
        self.ctg_line_pow_orig_imag = (
            - self.line_adm_total_imag * self.ctg_line_orig_volt_mag_sq + # ** 2.0 +
            (   self.line_adm_imag * self.ctg_line_cos_volt_ang_diff
              - self.line_adm_real * self.ctg_line_sin_volt_ang_diff) *
            self.ctg_line_orig_dest_volt_mag_prod)
        self.ctg_line_pow_dest_real = (
            self.line_adm_real * self.ctg_line_dest_volt_mag_sq + # ** 2.0 +
            ( - self.line_adm_real * self.ctg_line_cos_volt_ang_diff
              + self.line_adm_imag * self.ctg_line_sin_volt_ang_diff) *
            self.ctg_line_orig_dest_volt_mag_prod)
        self.ctg_line_pow_dest_imag = (
            - self.line_adm_total_imag * self.ctg_line_dest_volt_mag_sq + # ** 2.0 +
            (   self.line_adm_imag * self.ctg_line_cos_volt_ang_diff
              + self.line_adm_real * self.ctg_line_sin_volt_ang_diff) *
            self.ctg_line_orig_dest_volt_mag_prod)
        self.ctg_line_pow_orig_real[self.ctg_lines_out[self.ctg_current]] = 0.0
        self.ctg_line_pow_orig_imag[self.ctg_lines_out[self.ctg_current]] = 0.0
        self.ctg_line_pow_dest_real[self.ctg_lines_out[self.ctg_current]] = 0.0
        self.ctg_line_pow_dest_imag[self.ctg_lines_out[self.ctg_current]] = 0.0

    def eval_ctg_line_curr_viol(self):

        self.ctg_line_curr_orig_mag_max_viol = np.maximum(
            0.0,
            (self.ctg_line_pow_orig_real**2.0 + self.ctg_line_pow_orig_imag**2.0)**0.5 -
            self.ctg_line_curr_mag_max * self.ctg_line_orig_volt_mag)
        self.ctg_line_curr_dest_mag_max_viol = np.maximum(
            0.0,
            (self.ctg_line_pow_dest_real**2.0 + self.ctg_line_pow_dest_imag**2.0)**0.5 -
            self.ctg_line_curr_mag_max * self.ctg_line_dest_volt_mag)

    def eval_ctg_xfmr_pow(self):

        self.ctg_xfmr_orig_volt_mag = self.ctg_bus_volt_mag[self.xfmr_orig_bus]
        self.ctg_xfmr_dest_volt_mag = self.ctg_bus_volt_mag[self.xfmr_dest_bus]
        self.ctg_xfmr_volt_ang_diff = self.ctg_bus_volt_ang[self.xfmr_orig_bus] - self.ctg_bus_volt_ang[self.xfmr_dest_bus] - self.xfmr_tap_ang
        self.ctg_xfmr_cos_volt_ang_diff = np.cos(self.ctg_xfmr_volt_ang_diff)
        self.ctg_xfmr_sin_volt_ang_diff = np.sin(self.ctg_xfmr_volt_ang_diff)
        self.ctg_xfmr_orig_dest_volt_mag_prod = self.ctg_xfmr_orig_volt_mag * self.ctg_xfmr_dest_volt_mag
        self.ctg_xfmr_orig_volt_mag_sq = self.ctg_xfmr_orig_volt_mag ** 2.0
        self.ctg_xfmr_dest_volt_mag_sq = self.ctg_xfmr_dest_volt_mag ** 2.0
        self.ctg_xfmr_pow_orig_real = (
            (self.xfmr_adm_real / self.xfmr_tap_mag**2.0 + self.xfmr_adm_mag_real) * self.ctg_xfmr_orig_volt_mag_sq +
            ( - self.xfmr_adm_real / self.xfmr_tap_mag * self.ctg_xfmr_cos_volt_ang_diff
              - self.xfmr_adm_imag / self.xfmr_tap_mag * self.ctg_xfmr_sin_volt_ang_diff) *
                self.ctg_xfmr_orig_volt_mag * self.ctg_xfmr_dest_volt_mag)
        self.ctg_xfmr_pow_orig_imag = (
            - (self.xfmr_adm_imag / self.xfmr_tap_mag**2.0 + self.xfmr_adm_mag_imag) * self.ctg_xfmr_orig_volt_mag_sq +
            (   self.xfmr_adm_imag / self.xfmr_tap_mag * self.ctg_xfmr_cos_volt_ang_diff
              - self.xfmr_adm_real / self.xfmr_tap_mag * self.ctg_xfmr_sin_volt_ang_diff) *
                self.ctg_xfmr_orig_volt_mag * self.ctg_xfmr_dest_volt_mag)
        self.ctg_xfmr_pow_dest_real = (
            self.xfmr_adm_real * self.ctg_xfmr_dest_volt_mag_sq +
            ( - self.xfmr_adm_real / self.xfmr_tap_mag * self.ctg_xfmr_cos_volt_ang_diff
              + self.xfmr_adm_imag / self.xfmr_tap_mag * self.ctg_xfmr_sin_volt_ang_diff) *
                self.ctg_xfmr_orig_volt_mag * self.ctg_xfmr_dest_volt_mag)
        self.ctg_xfmr_pow_dest_imag = (
            - self.xfmr_adm_imag * self.ctg_xfmr_dest_volt_mag_sq +
            (   self.xfmr_adm_imag / self.xfmr_tap_mag * self.ctg_xfmr_cos_volt_ang_diff
              + self.xfmr_adm_real / self.xfmr_tap_mag * self.ctg_xfmr_sin_volt_ang_diff) *
                self.ctg_xfmr_orig_volt_mag * self.ctg_xfmr_dest_volt_mag)
        self.ctg_xfmr_pow_orig_real[self.ctg_xfmrs_out[self.ctg_current]] = 0.0
        self.ctg_xfmr_pow_orig_imag[self.ctg_xfmrs_out[self.ctg_current]] = 0.0
        self.ctg_xfmr_pow_dest_real[self.ctg_xfmrs_out[self.ctg_current]] = 0.0
        self.ctg_xfmr_pow_dest_imag[self.ctg_xfmrs_out[self.ctg_current]] = 0.0

    def eval_ctg_xfmr_pow_viol(self):

        self.ctg_xfmr_pow_orig_mag_max_viol = np.maximum(
            0.0,
            (self.ctg_xfmr_pow_orig_real**2.0 + self.ctg_xfmr_pow_orig_imag**2.0)**0.5 -
            self.ctg_xfmr_pow_mag_max)
        self.ctg_xfmr_pow_dest_mag_max_viol = np.maximum(
            0.0,
            (self.ctg_xfmr_pow_dest_real**2.0 + self.ctg_xfmr_pow_dest_imag**2.0)**0.5 -
            self.ctg_xfmr_pow_mag_max)

    def eval_ctg_bus_swsh_adm_imag_viol(self):

        self.ctg_bus_swsh_adm_imag_min_viol = np.maximum(0.0, self.bus_swsh_adm_imag_min - self.ctg_bus_swsh_adm_imag)
        self.ctg_bus_swsh_adm_imag_max_viol = np.maximum(0.0, self.ctg_bus_swsh_adm_imag - self.bus_swsh_adm_imag_max)

    def eval_ctg_bus_swsh_pow(self):

        self.ctg_bus_swsh_pow_imag = -self.ctg_bus_swsh_adm_imag * self.ctg_bus_volt_mag**2.0

    def eval_ctg_bus_pow_balance(self):

        '''
        if debug:
            #ctg = 'LINE-104-105-1'
            ctg = 'GEN-688-1'
            i = 223
            if self.ctg_label == ctg:
                print("debug contingency real power balance")
                print("ctg: %s" % str(ctg))
                print("bus: %s" % str(i))
                print("generators: %s" % str([(k, self.ctg_gen_active[k], self.ctg_gen_pow_real[k]) for k in self.bus_gen[i]]))
                print("loads: %s" % str([(k, self.load_status[k], self.ctg_load_pow_real[k]) for k in self.bus_load[i]]))
                print("fixed shunts: %s" % str([(k, self.fxsh_status[k], self.ctg_fxsh_pow_real[k]) for k in self.bus_fxsh[i]]))
                print("lines orig: %s" % str([(k, self.ctg_line_active[k], self.ctg_line_pow_orig_real[k]) for k in self.bus_line_orig[i]]))
                print("lines dest: %s" % str([(k, self.ctg_line_active[k], self.ctg_line_pow_dest_real[k]) for k in self.bus_line_dest[i]]))
                print("xfmrs orig: %s" % str([(k, self.ctg_xfmr_active[k], self.ctg_xfmr_pow_orig_real[k]) for k in self.bus_xfmr_orig[i]]))
                print("xfmrs dest: %s" % str([(k, self.ctg_xfmr_active[k], self.ctg_xfmr_pow_dest_real[k]) for k in self.bus_xfmr_dest[i]]))
        '''

        self.ctg_bus_pow_balance_real_viol = np.abs(
            self.bus_gen_matrix.dot(self.ctg_gen_pow_real) -
            self.ctg_bus_load_pow_real -
            self.ctg_bus_fxsh_pow_real -
            self.bus_line_orig_matrix.dot(self.ctg_line_pow_orig_real) -
            self.bus_line_dest_matrix.dot(self.ctg_line_pow_dest_real) -
            self.bus_xfmr_orig_matrix.dot(self.ctg_xfmr_pow_orig_real) -
            self.bus_xfmr_dest_matrix.dot(self.ctg_xfmr_pow_dest_real))
        self.ctg_bus_pow_balance_imag_viol = np.abs(
            self.bus_gen_matrix.dot(self.ctg_gen_pow_imag) -
            self.ctg_bus_load_pow_imag -
            self.ctg_bus_fxsh_pow_imag -
            self.ctg_bus_swsh_pow_imag -
            self.bus_line_orig_matrix.dot(self.ctg_line_pow_orig_imag) -
            self.bus_line_dest_matrix.dot(self.ctg_line_pow_dest_imag) -
            self.bus_xfmr_orig_matrix.dot(self.ctg_xfmr_pow_orig_imag) -
            self.bus_xfmr_dest_matrix.dot(self.ctg_xfmr_pow_dest_imag))

        ''' debug
        debug = False
        ctg_label = 'G_000017SENECA33U1'
        bus_i = 17
        #gen_i = 17
        #gen_id = '1'
        bus = self.bus_map[bus_i]
        #gen = self.gen_map[(gen_i, gen_id)]
        if self.ctg_label[self.ctg_current] == ctg_label:
            debug = True
            print('ctg_label: %s' % self.ctg_label[self.ctg_current])
            print('bus i: %s' % bus_i)
            print('bus: %s' % bus)
            print('bus ctg pow balance real viol: %f' % self.ctg_bus_pow_balance_real_viol[bus])
        '''


        ''' something we could do with numpy but not with dictionaries - what about lists?
        self.ctg_bus_pow_balance_real_viol = {
            i:abs(
                sum(self.ctg_gen_pow_real[self.bus_gen[i]]) -
                sum(self.ctg_load_pow_real[self.bus_load[i]]) -
                sum(self.ctg_fxsh_pow_real[self.bus_fxsh[i]]) -
                sum(self.ctg_line_pow_orig_real[self.bus_line_orig[i]]) -
                sum(self.ctg_line_pow_dest_real[self.bus_line_dest[i]]) -
                sum(self.ctg_xfmr_pow_orig_real[self.bus_xfmr_orig[i]]) -
                sum(self.ctg_xfmr_pow_dest_real[self.bus_xfmr_dest[i]]))
            for i in self.bus}
        '''
        ''' could do this by precomputing the index sets
        self.ctg_bus_pow_balance_real_viol = {
            i:abs(
                sum([self.ctg_gen_pow_real[k] for k in self.bus_gen[i]]) -
                sum([self.ctg_load_pow_real[k] for k in self.bus_load[i]]) -
                sum([self.ctg_fxsh_pow_real[k] for k in self.bus_fxsh[i]]) -
                sum([self.ctg_line_pow_orig_real[k] for k in self.bus_line_orig[i]]) -
                sum([self.ctg_line_pow_dest_real[k] for k in self.bus_line_dest[i]]) -
                sum([self.ctg_xfmr_pow_orig_real[k] for k in self.bus_xfmr_orig[i]]) -
                sum([self.ctg_xfmr_pow_dest_real[k] for k in self.bus_xfmr_dest[i]]))
            for i in self.bus}
        '''
        ''' original
        self.ctg_bus_pow_balance_real_viol = {
            i:abs(
                sum([self.ctg_gen_pow_real[k] for k in self.bus_gen[i] if self.ctg_gen_active[k]]) -
                sum([self.ctg_load_pow_real[k] for k in self.bus_load[i] if self.load_status[k]]) -
                sum([self.ctg_fxsh_pow_real[k] for k in self.bus_fxsh[i] if self.fxsh_status[k]]) -
                sum([self.ctg_line_pow_orig_real[k] for k in self.bus_line_orig[i] if self.ctg_line_active[k]]) -
                sum([self.ctg_line_pow_dest_real[k] for k in self.bus_line_dest[i] if self.ctg_line_active[k]]) -
                sum([self.ctg_xfmr_pow_orig_real[k] for k in self.bus_xfmr_orig[i] if self.ctg_xfmr_active[k]]) -
                sum([self.ctg_xfmr_pow_dest_real[k] for k in self.bus_xfmr_dest[i] if self.ctg_xfmr_active[k]]))
            for i in self.bus}
        self.ctg_bus_pow_balance_imag_viol = {
            i:abs(
                sum([self.ctg_gen_pow_imag[k] for k in self.bus_gen[i] if self.ctg_gen_active[k]]) -
                sum([self.ctg_load_pow_imag[k] for k in self.bus_load[i] if self.load_status[k]]) -
                sum([self.ctg_fxsh_pow_imag[k] for k in self.bus_fxsh[i] if self.fxsh_status[k]]) -
                self.ctg_bus_swsh_pow_imag[i] -
                sum([self.ctg_line_pow_orig_imag[k] for k in self.bus_line_orig[i] if self.ctg_line_active[k]]) -
                sum([self.ctg_line_pow_dest_imag[k] for k in self.bus_line_dest[i] if self.ctg_line_active[k]]) -
                sum([self.ctg_xfmr_pow_orig_imag[k] for k in self.bus_xfmr_orig[i] if self.ctg_xfmr_active[k]]) -
                sum([self.ctg_xfmr_pow_dest_imag[k] for k in self.bus_xfmr_dest[i] if self.ctg_xfmr_active[k]]))
            for i in self.bus}
        '''

    def eval_ctg_gen_pvpq_viol(self):

        self.ctg_gen_pvpq1_viol = np.minimum(
            np.maximum(0.0, self.ctg_gen_pow_imag_max - self.ctg_gen_pow_imag),
            np.maximum(0.0, self.gen_bus_volt_mag - self.ctg_gen_bus_volt_mag))
        self.ctg_gen_pvpq2_viol = np.minimum(
            np.maximum(0.0, self.ctg_gen_pow_imag - self.ctg_gen_pow_imag_min),
            np.maximum(0.0, self.ctg_gen_bus_volt_mag - self.gen_bus_volt_mag))

        '''
        self.ctg_gen_pvpq1_viol = {
            i:(min(max(0.0, self.gen_pow_imag_max[i] - self.ctg_gen_pow_imag[i]),
                   max(0.0, self.bus_volt_mag[i[0]] - self.ctg_bus_volt_mag[i[0]]))
                if self.ctg_gen_active[i]
                else 0.0)
            for i in self.gen}
        self.ctg_gen_pvpq2_viol = {
            i:(min(max(0.0, self.ctg_gen_pow_imag[i] - self.gen_pow_imag_min[i]),
                   max(0.0, self.ctg_bus_volt_mag[i[0]] - self.bus_volt_mag[i[0]]))
                if self.ctg_gen_active[i]
                else 0.0)
            for i in self.gen}
        '''

        '''
        if debug:
            ctg = 'LINE-95-96-1'
            i = 151
            uid = '2'
            g = (i,uid)
            if self.ctg_label == ctg:
                print("debug ctg gen pvpq switching constraints")
                print("ctg: %s" % str(ctg))
                print("gen: %s" % str(g))
                print("active: %u" % self.ctg_gen_active[g])
                print("qmax: %s" % self.gen_pow_imag_max[g])
                print("qmin: %s" % self.gen_pow_imag_min[g])
                print("vmax: %s" % self.bus_volt_mag_max[i])
                print("vmin: %s" % self.bus_volt_mag_min[i])
                print("v: %s" % self.bus_volt_mag[i])
                print("vk: %s" % self.ctg_bus_volt_mag[i])
                print("qk: %s" % self.ctg_gen_pow_imag[g])
                print("vq1_viol (undervoltage / qmax slack): %s" % self.ctg_gen_pvpq1_viol[g])
                print("vq2_viol (overvoltage / qmin slack: %s" % self.ctg_gen_pvpq2_viol[g])
        '''

    def eval_penalty(self):
        '''TODO: maybe this can be more efficient:
                    check eval_piecewise ... made a big improvement on this - it was creating a list needlessly
                    try concatenating to one vector'''

        start_time = time.time()
        self.penalty = base_case_penalty_weight * (
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        self.line_curr_orig_mag_max_viol,
                        self.line_curr_dest_mag_max_viol),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        self.xfmr_pow_orig_mag_max_viol,
                        self.xfmr_pow_dest_mag_max_viol),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.bus_pow_balance_real_viol,
                    self.penalty_block_pow_real_max,
                    self.penalty_block_pow_real_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.bus_pow_balance_imag_viol,
                    self.penalty_block_pow_imag_max,
                    self.penalty_block_pow_imag_coeff)))
        end_time = time.time()
        print('eval penalty time: %f' % (end_time - start_time))

    def eval_ctg_penalty(self):

        self.ctg_penalty = (1 - base_case_penalty_weight) / max(1.0, float(self.num_ctg)) * (
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        self.ctg_line_curr_orig_mag_max_viol,
                        self.ctg_line_curr_dest_mag_max_viol),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        self.ctg_xfmr_pow_orig_mag_max_viol,
                        self.ctg_xfmr_pow_dest_mag_max_viol),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.ctg_bus_pow_balance_real_viol,
                    self.penalty_block_pow_real_max,
                    self.penalty_block_pow_real_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.ctg_bus_pow_balance_imag_viol,
                    self.penalty_block_pow_imag_max,
                    self.penalty_block_pow_imag_coeff)))

    def eval_infeas(self):

        self.max_obj_viol = max(
            self.max_bus_pow_balance_real_viol[1],
            self.max_bus_pow_balance_imag_viol[1],
            self.max_line_curr_orig_mag_max_viol[1],
            self.max_line_curr_dest_mag_max_viol[1],
            self.max_xfmr_pow_orig_mag_max_viol[1],
            self.max_xfmr_pow_dest_mag_max_viol[1])
        self.max_nonobj_viol = max(
            self.max_bus_volt_mag_max_viol[1],
            self.max_bus_volt_mag_min_viol[1],
            self.max_bus_swsh_adm_imag_max_viol[1],
            self.max_bus_swsh_adm_imag_min_viol[1],
            self.max_gen_pow_real_max_viol[1],
            self.max_gen_pow_real_min_viol[1],
            self.max_gen_pow_imag_max_viol[1],
            self.max_gen_pow_imag_min_viol[1])
        self.infeas = 1 if self.max_nonobj_viol > hard_constr_tol else 0

    def eval_ctg_infeas(self):

        self.ctg_max_obj_viol = max(
            self.ctg_max_bus_pow_balance_real_viol[1],
            self.ctg_max_bus_pow_balance_imag_viol[1],
            self.ctg_max_line_curr_orig_mag_max_viol[1],
            self.ctg_max_line_curr_dest_mag_max_viol[1],
            self.ctg_max_xfmr_pow_orig_mag_max_viol[1],
            self.ctg_max_xfmr_pow_dest_mag_max_viol[1])
        self.ctg_max_nonobj_viol = max(
            self.ctg_max_bus_volt_mag_max_viol[1],
            self.ctg_max_bus_volt_mag_min_viol[1],
            self.ctg_max_bus_swsh_adm_imag_max_viol[1],
            self.ctg_max_bus_swsh_adm_imag_min_viol[1],
            #self.ctg_max_gen_pow_real_max_viol[1],
            #self.ctg_max_gen_pow_real_min_viol[1],
            self.ctg_max_gen_pow_imag_max_viol[1],
            self.ctg_max_gen_pow_imag_min_viol[1],
            self.ctg_max_gen_pvpq1_viol[1],
            self.ctg_max_gen_pvpq2_viol[1])
        self.ctg_infeas = 1 if self.ctg_max_nonobj_viol > hard_constr_tol else 0
        self.max_obj_viol = max(self.max_obj_viol, self.ctg_max_obj_viol)
        self.max_nonobj_viol = max(self.max_nonobj_viol, self.ctg_max_nonobj_viol)

    def eval_obj(self):

        self.obj = self.cost + self.penalty

    #def evaluate(self):
    #
    #    # obj
    #    self.eval_cost()
    #    self.eval_penalty()
    #    self.eval_obj()

    def normalize(self):
        '''divide constraint violations by a normalizing constant.'''

        pass

    # TODO convert back from per unit to data units here for printing to detail and summary output files
    # should we use data units for the output of the function? Yes
    def convert_to_data_units(self):
        '''convert from computation units (p.u.) to data units (mix of p.u. and phycical units)
        for writing output'''

        pass

    def compute_detail(self):

        start_time = time.time()
        self.max_bus_volt_mag_max_viol = extra_max(self.bus_i, self.bus_volt_mag_max_viol)
        self.max_bus_volt_mag_min_viol = extra_max(self.bus_i, self.bus_volt_mag_min_viol)
        self.max_bus_swsh_adm_imag_max_viol = extra_max(self.bus_i, self.bus_swsh_adm_imag_max_viol)
        self.max_bus_swsh_adm_imag_min_viol = extra_max(self.bus_i, self.bus_swsh_adm_imag_min_viol)
        self.max_bus_pow_balance_real_viol = extra_max(self.bus_i, self.bus_pow_balance_real_viol)
        self.max_bus_pow_balance_imag_viol = extra_max(self.bus_i, self.bus_pow_balance_imag_viol)
        self.max_gen_pow_real_max_viol = extra_max(self.gen_key, self.gen_pow_real_max_viol)
        self.max_gen_pow_real_min_viol = extra_max(self.gen_key, self.gen_pow_real_min_viol)
        self.max_gen_pow_imag_max_viol = extra_max(self.gen_key, self.gen_pow_imag_max_viol)
        self.max_gen_pow_imag_min_viol = extra_max(self.gen_key, self.gen_pow_imag_min_viol)
        self.max_line_curr_orig_mag_max_viol = extra_max(self.line_key, self.line_curr_orig_mag_max_viol)
        self.max_line_curr_dest_mag_max_viol = extra_max(self.line_key, self.line_curr_dest_mag_max_viol)
        self.max_xfmr_pow_orig_mag_max_viol = extra_max(self.xfmr_key, self.xfmr_pow_orig_mag_max_viol)
        self.max_xfmr_pow_dest_mag_max_viol = extra_max(self.xfmr_key, self.xfmr_pow_dest_mag_max_viol)
        end_time = time.time()
        print('compute detail time: %f' % (end_time - start_time))

    def compute_ctg_detail(self):
        
        self.ctg_max_bus_volt_mag_max_viol = extra_max(self.bus_i, self.ctg_bus_volt_mag_max_viol)
        self.ctg_max_bus_volt_mag_min_viol = extra_max(self.bus_i, self.ctg_bus_volt_mag_min_viol)
        self.ctg_max_bus_swsh_adm_imag_max_viol = extra_max(self.bus_i, self.ctg_bus_swsh_adm_imag_max_viol)
        self.ctg_max_bus_swsh_adm_imag_min_viol = extra_max(self.bus_i, self.ctg_bus_swsh_adm_imag_min_viol)
        self.ctg_max_bus_pow_balance_real_viol = extra_max(self.bus_i, self.ctg_bus_pow_balance_real_viol)
        self.ctg_max_bus_pow_balance_imag_viol = extra_max(self.bus_i, self.ctg_bus_pow_balance_imag_viol)
        #self.ctg_max_gen_pow_real_max_viol = extra_max(self.gen_key, self.ctg_gen_pow_real_max_viol) # do we need something for this?
        #self.ctg_max_gen_pow_real_min_viol = extra_max(self.gen_key, self.ctg_gen_pow_real_min_viol)
        self.ctg_max_gen_pow_imag_max_viol = extra_max(self.gen_key, self.ctg_gen_pow_imag_max_viol)
        self.ctg_max_gen_pow_imag_min_viol = extra_max(self.gen_key, self.ctg_gen_pow_imag_min_viol)
        self.ctg_max_gen_pvpq1_viol = extra_max(self.gen_key, self.ctg_gen_pvpq1_viol)
        self.ctg_max_gen_pvpq2_viol = extra_max(self.gen_key, self.ctg_gen_pvpq2_viol)
        self.ctg_max_line_curr_orig_mag_max_viol = extra_max(self.line_key, self.ctg_line_curr_orig_mag_max_viol)
        self.ctg_max_line_curr_dest_mag_max_viol = extra_max(self.line_key, self.ctg_line_curr_dest_mag_max_viol)
        self.ctg_max_xfmr_pow_orig_mag_max_viol = extra_max(self.xfmr_key, self.ctg_xfmr_pow_orig_mag_max_viol)
        self.ctg_max_xfmr_pow_dest_mag_max_viol = extra_max(self.xfmr_key, self.ctg_xfmr_pow_dest_mag_max_viol)

    '''
    def compute_summary(self):

        def dict_max_zero(d):
            return max([0] + d.values())

        self.max_bus_volt_mag_min_viol = dict_max_zero(self.bus_volt_mag_min_viol)
        self.max_bus_volt_mag_max_viol = dict_max_zero(self.bus_volt_mag_max_viol)
        self.max_gen_pow_real_min_viol = dict_max_zero(self.gen_pow_real_min_viol)
        self.max_gen_pow_real_max_viol = dict_max_zero(self.gen_pow_real_max_viol)
        self.max_gen_pow_imag_min_viol = dict_max_zero(self.gen_pow_imag_min_viol)
        self.max_gen_pow_imag_max_viol = dict_max_zero(self.gen_pow_imag_max_viol)
        self.max_line_curr_orig_mag_max_viol = dict_max_zero(self.line_curr_orig_mag_max_viol)
        self.max_line_curr_dest_mag_max_viol = dict_max_zero(self.line_curr_dest_mag_max_viol)
        self.max_xfmr_pow_orig_mag_max_viol = dict_max_zero(self.xfmr_pow_orig_mag_max_viol)
        self.max_xfmr_pow_dest_mag_max_viol = dict_max_zero(self.xfmr_pow_dest_mag_max_viol)
        self.max_swsh_adm_imag_min_viol = dict_max_zero(self.swsh_adm_imag_min_viol)
        self.max_swsh_adm_imag_max_viol = dict_max_zero(self.swsh_adm_imag_max_viol)
        self.max_bus_pow_balance_real_viol = dict_max_zero(self.bus_pow_balance_real_viol)
        self.max_bus_pow_balance_imag_viol = dict_max_zero(self.bus_pow_balance_imag_viol)
        self.max_bus_ctg_volt_mag_max_viol = dict_max_zero(self.bus_ctg_volt_mag_max_viol)
        self.max_bus_ctg_volt_mag_min_viol = dict_max_zero(self.bus_ctg_volt_mag_min_viol)
        self.max_gen_ctg_pow_real_min_viol = dict_max_zero(self.gen_ctg_pow_real_min_viol)
        self.max_gen_ctg_pow_real_max_viol = dict_max_zero(self.gen_ctg_pow_real_max_viol)
        self.max_gen_ctg_pow_imag_min_viol = dict_max_zero(self.gen_ctg_pow_imag_min_viol)
        self.max_gen_ctg_pow_imag_max_viol = dict_max_zero(self.gen_ctg_pow_imag_max_viol)
        self.max_line_ctg_curr_orig_mag_max_viol = dict_max_zero(self.line_ctg_curr_orig_mag_max_viol)
        self.max_line_ctg_curr_dest_mag_max_viol = dict_max_zero(self.line_ctg_curr_dest_mag_max_viol)
        self.max_xfmr_ctg_pow_orig_mag_max_viol = dict_max_zero(self.xfmr_ctg_pow_orig_mag_max_viol)
        self.max_xfmr_ctg_pow_dest_mag_max_viol = dict_max_zero(self.xfmr_ctg_pow_dest_mag_max_viol)
        self.max_swsh_ctg_adm_imag_min_viol = dict_max_zero(self.swsh_ctg_adm_imag_min_viol)
        self.max_swsh_ctg_adm_imag_max_viol = dict_max_zero(self.swsh_ctg_adm_imag_max_viol)
        self.max_bus_ctg_pow_balance_real_viol = dict_max_zero(self.bus_ctg_pow_balance_real_viol)
        self.max_bus_ctg_pow_balance_imag_viol = dict_max_zero(self.bus_ctg_pow_balance_imag_viol)
        # todo: complementarity violation on generator bus voltage and generator reactive power
        self.max_gen_ctg_pvpq1_viol = dict_max_zero(self.gen_ctg_pvpq1_viol)
        self.max_gen_ctg_pvpq2_viol = dict_max_zero(self.gen_ctg_pvpq2_viol)

        self.max_viol = max(
            self.max_bus_volt_mag_min_viol,
            self.max_bus_volt_mag_max_viol,
            self.max_gen_pow_real_min_viol,
            self.max_gen_pow_real_max_viol,
            self.max_gen_pow_imag_min_viol,
            self.max_gen_pow_imag_max_viol,
            self.max_line_curr_orig_mag_max_viol,
            self.max_line_curr_dest_mag_max_viol,
            self.max_xfmr_pow_orig_mag_max_viol,
            self.max_xfmr_pow_dest_mag_max_viol,
            self.max_swsh_adm_imag_min_viol,
            self.max_swsh_adm_imag_max_viol,
            self.max_bus_pow_balance_real_viol,
            self.max_bus_pow_balance_imag_viol,
            self.max_bus_ctg_volt_mag_max_viol,
            self.max_bus_ctg_volt_mag_min_viol,
            self.max_gen_ctg_pow_imag_min_viol,
            self.max_gen_ctg_pow_imag_max_viol,
            self.max_gen_ctg_pow_real_min_viol,
            self.max_gen_ctg_pow_real_max_viol,
            self.max_line_ctg_curr_orig_mag_max_viol,
            self.max_line_ctg_curr_dest_mag_max_viol,
            self.max_xfmr_ctg_pow_orig_mag_max_viol,
            self.max_xfmr_ctg_pow_dest_mag_max_viol,
            self.max_swsh_ctg_adm_imag_min_viol,
            self.max_swsh_ctg_adm_imag_max_viol,
            self.max_bus_ctg_pow_balance_real_viol,
            self.max_bus_ctg_pow_balance_imag_viol,
            self.max_gen_ctg_pvpq1_viol,
            self.max_gen_ctg_pvpq2_viol,
        )

        self.max_nonobj_viol = 0.0 # todo need to actually compute this, but so far there are no nonobjective constraints to violate anyway
        self.num_viol = 0
    '''

    '''
    def write_summary(self, out_name):

        with open(out_name, 'ab') as out:
            csv_writer = csv.writer(out, delimiter=',', quotechar="'", quoting=csv.QUOTE_MINIMAL)
        
            if self.scenario_number == '1':
                
                csv_writer.writerow([
                '','','','','',
                'Maximum base case constraint violations','','','','','','','','','','','','','',
                'Maximum contingency case constraint violations'
                ])
                
                csv_writer.writerow([
                'Scenario',
                'Objective',
                'Cost',
                'Objective-Cost',
                'Runtime(sec)',
                'bus_volt_mag_min',
                'bus_volt_mag_max',
                'gen_pow_real_min',
                'gen_pow_real_max',
                'gen_pow_imag_min',
                'gen_pow_imag_max',
                'line_curr_orig_mag_max',
                'line_curr_dest_mag_max',
                'xfmr_pow_orig_mag_max',
                'xfrm_pow_dest_mag_max',
                'swsh_adm_imag_min',
                'swsh_adm_imag_max',
                'bus_pow_balance_real',
                'bus_pow_balance_imag',
                'bus_ctg_volt_mag_min',
                'bus_ctg_volt_mag_max',
                'gen_ctg_pow_real_min',
                'gen_ctg_pow_real_max',
                'gen_ctg_pow_imag_min',
                'gen_ctg_pow_imag_max',
                'line_ctg_curr_orig_mag_max',
                'line_ctg_curr_dest_mag_max',
                'xfmr_ctg_pow_orig_mag_max',
                'xfmr_ctg_pow_dest_mag_max',
                'swsh_ctg_adm_imag_min',
                'swsh_ctg_adm_imag_max',
                'bus_ctg_pow_balance_real',
                'bus_ctg_pow_balance_imag',
                'gen_ctg_pvpq1',
                'gen_ctg_pvpq2',
                'all'])

            csv_writer.writerow([
                'scenario_%s'%(self.scenario_number),
                self.obj,
                self.cost,
                self.obj-self.cost,
                self.runtime_sec,
                self.max_bus_volt_mag_min_viol,
                self.max_bus_volt_mag_max_viol,
                self.max_gen_pow_real_min_viol,
                self.max_gen_pow_real_max_viol,
                self.max_gen_pow_imag_min_viol,
                self.max_gen_pow_imag_max_viol,
                self.max_line_curr_orig_mag_max_viol,
                self.max_line_curr_dest_mag_max_viol,
                self.max_xfmr_pow_orig_mag_max_viol,
                self.max_xfmr_pow_dest_mag_max_viol,
                self.max_swsh_adm_imag_min_viol,
                self.max_swsh_adm_imag_max_viol,
                self.max_bus_pow_balance_real_viol,
                self.max_bus_pow_balance_imag_viol,
                self.max_bus_ctg_volt_mag_min_viol,
                self.max_bus_ctg_volt_mag_max_viol,
                self.max_gen_ctg_pow_real_min_viol,
                self.max_gen_ctg_pow_real_max_viol,
                self.max_gen_ctg_pow_imag_min_viol,
                self.max_gen_ctg_pow_imag_max_viol,
                self.max_line_ctg_curr_orig_mag_max_viol,
                self.max_line_ctg_curr_dest_mag_max_viol,
                self.max_xfmr_ctg_pow_orig_mag_max_viol,
                self.max_xfmr_ctg_pow_dest_mag_max_viol,
                self.max_swsh_ctg_adm_imag_min_viol,
                self.max_swsh_ctg_adm_imag_max_viol,
                self.max_bus_ctg_pow_balance_real_viol,
                self.max_bus_ctg_pow_balance_imag_viol,
                self.max_gen_ctg_pvpq1_viol,
                self.max_gen_ctg_pvpq2_viol,
                self.max_viol])
    '''

def solution_read_sections(file_name, section_start_line_str=None, has_headers=None):

    start_time = time.time()
    with open(file_name, 'r') as in_file:
        lines = in_file.readlines()
        sections = solution_read_sections_from_lines(lines, section_start_line_str, has_headers)
    end_time = time.time()
    print('solution_read_sections time: %f' % (end_time - start_time))
    return sections

def solution_read_sections_from_lines(lines_in, section_start_line_str=None, has_headers=None):
    '''TODO: this function is inefficient ~0.13 second
    in sol2, we were able to deduce the start and end of each contingency from the data dimensions.
    We could do this also withing each contingency and the base case to deduce the start and end
    of each section.
    the bus section is the largest. since the keys are only integers (bus number) it may be possible
    to more efficiently load this into a numpy array, then extract the 0-th column as an integer array
    for the bus numbers.
    the generator section would be harder since it can have strings. might need to use pandas. but
    this section is smaller so it might not matter.'''

    start_time = time.time()
    if section_start_line_str is None:
        section_start_line_str = '--'
    if has_headers is None:
        has_headers = True
    num_lines = len(lines_in)
    delimiter_str = ","
    quote_str = "'"
    skip_initial_space = True
    lines = csv.reader( # this is fast
        lines_in,
        delimiter=delimiter_str,
        quotechar=quote_str,
        skipinitialspace=skip_initial_space)
    
    start_time_0 = time.time()
    lines = list(lines)
    end_time_0 = time.time()
    print('sub time 1: %f' % (end_time_0 - start_time_0))

    start_time_1 = time.time()
    lines = [[t.strip() for t in r] for r in lines]
    end_time_1 = time.time()
    print('sub time 1: %f' % (end_time_1 - start_time_1))

    start_time_2 = time.time()
    lines = [r for r in lines if len(r) > 0]
    end_time_2 = time.time()
    print('sub time 2: %f' % (end_time_2 - start_time_2))

    section_start_line_nums = [
        i for i in range(num_lines)
        if lines[i][0][:2] == section_start_line_str]
    num_sections = len(section_start_line_nums)
    section_end_line_nums = [
        section_start_line_nums[i]
        for i in range(1,num_sections)]
    section_end_line_nums += [num_lines]
    section_start_line_nums = [
        section_start_line_nums[i] + 1
        for i in range(num_sections)]
    if has_headers:
        section_start_line_nums = [
            section_start_line_nums[i] + 1
            for i in range(num_sections)]
    sections = [
        [lines[i]
         for i in range(
                 section_start_line_nums[j],
                 section_end_line_nums[j])]
        for j in range(num_sections)]
    end_time = time.time()
    print('solution_read_sections_from_lines time: %f' % (end_time - start_time))
    return sections

class Solution1:
    '''In physical units, i.e. data convention, i.e. same as input and output data files'''

    def __init__(self):
        '''items to be read from solution1.txt'''

        self.bus_volt_mag = {}
        self.bus_volt_ang = {}
        self.bus_swsh_adm_imag = {}
        self.gen_pow_real = {}
        self.gen_pow_imag = {}

    def read(self, file_name, num_bus, num_gen):
        
        start_time = time.time()
        self.bus_df = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'vm', 'va', 'b'],
            dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
            nrows=num_bus,
            engine='c',
            skiprows=2,
            skipinitialspace=True,
            float_precision=pandas_float_precision)
        self.gen_df = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'id', 'pg', 'qg'],
            dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'pq':np.float_},
            nrows=num_gen,
            engine='c',
            na_values=None,
            keep_default_na=False,
            #quoting=csv.QUOTE_NONE,
            skiprows=(4 + num_bus),
            skipinitialspace=True,
            float_precision=pandas_float_precision)
        self.num_bus = self.bus_df.shape[0]
        self.num_gen = self.gen_df.shape[0]
        '''
        self.bus_i = bus_array.i.values.tolist() # should this be a list?
        self.num_bus = len(self.bus_i)
        #print([self.num_bus, self.bus_i[self.num_bus - 1]])
        self.bus_map = {self.bus_i[i]:i for i in range(self.num_bus)}
        self.bus_volt_mag = bus_array.vm.values
        self.bus_volt_ang = bus_array.va.values
        self.bus_swsh_adm_imag = bus_array.b.values
        self.gen_i = gen_array.i.values.tolist() # should this be a list?
        self.gen_id = gen_array.id.values.tolist() # should this be a list?
        self.num_gen = len(self.gen_i)
        self.gen_map = {(self.gen_i[i], self.gen_id[i]):i for i in range(self.num_gen)}
        #print(self.gen_id[0:10])
        self.gen_pow_real = gen_array.pg.values
        self.gen_pow_imag = gen_array.qg.values
        '''
        end_time = time.time()
        print("sol1 read time: %f" % (end_time - start_time))

    #'''
    def read_old(self, file_name):

        start_time = time.time()
        bus = 0
        gen = 1
        section_start_line_str = '--'
        has_headers = True
        sections = solution_read_sections(file_name, section_start_line_str, has_headers)
        self.read_bus_rows(sections[bus])
        self.read_gen_rows(sections[gen])
        end_time = time.time()
        print("sol1 read time: %f" % (end_time - start_time))

        #self.read_test(file_name, 10, 10)
    #'''

    '''
    def read_test_np(self, file_name, num_bus, num_gen):
        
        start_time = time.time()
        with open(file_name, 'r') as in_file:
            discard = list(islice(in_file, 2))
            print(discard)
            lines = list(islice(in_file, num_bus))
            #bus_array = np.loadtxt(lines[4:6], dtype=[('i', '<i4'), ('vm', '<f8'), ('va', '<f8'), ('b', '<f8')], delimiter=',') # comments, unpack
            bus_array = np.loadtxt(lines, dtype=[('i', '<i4'), ('vm', '<f8'), ('va', '<f8'), ('b', '<f8')], delimiter=',')
            #bus_array = np.loadtxt(lines, dtype=[('i', np.int_), ('vm', np.float_), ('va', np.float_), ('b', np.float_)], delimiter=',', unpack=True)
            print([bus_array.shape, bus_array[0:2]])
            discard = list(islice(in_file, 2))
            print(discard)
            lines = list(islice(in_file, num_gen))
            print([lines[0], lines[1], len(lines), lines[len(lines) - 1]])
            #lines = in_file.readlines()
            #print(bus_array)
        end_time = time.time()
        print("sol1 read time (np): %f" % (end_time - start_time))
    '''

    '''
    def read_test_pd(self, file_name, num_bus, num_gen):
        
        start_time = time.time()
        bus_array = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'vm', 'va', 'b'],
            dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
            nrows=num_bus,
            engine='c',
            skiprows=2,
            float_precision=pandas_float_precision)
        bus_i = bus_array.i.values
        bus_vm = bus_array.vm.values
        bus_va = bus_array.va.values
        bus_b = bus_array.b.values
        print([bus_i.shape, bus_vm.shape, bus_va.shape, bus_b.shape])
        gen_array = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'id', 'pg', 'qg'],
            dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'pq':np.float_},
            nrows=num_gen,
            engine='c',
            skiprows=(4 + num_bus),
            float_precision=pandas_float_precision)
        gen_i = gen_array.i.values
        gen_id = gen_array.id.values
        gen_pg = gen_array.pg.values
        gen_qg = gen_array.qg.values
        print([gen_i.shape, gen_id.shape, gen_pg.shape, gen_qg.shape])
        end_time = time.time()
        print("sol1 read time (pd): %f" % (end_time - start_time))
    '''

    '''
    def read_sol2_1(self, file_name, num_bus, num_gen):
        
        start_time = time.time()
        #num_ctg = 21960
        num_ctg = 22
        ctg_block_size = num_bus + num_gen + 10
        num_rows = num_ctg * ctg_block_size

        ctg_start_row = 2
        ctg_end_row = ctg_start_row + 1 - 1
        bus_start_row = ctg_end_row + 3
        bus_end_row = bus_start_row + num_bus - 1
        gen_start_row = bus_end_row + 3
        gen_end_row = gen_start_row + num_gen - 1
        delta_start_row = gen_end_row + 3
        delta_end_row = delta_start_row + 1 - 1

        ctg_ctg_start_row = [i * ctg_block_size + ctg_start_row for i in range(num_ctg)]
        ctg_bus_start_row = [i * ctg_block_size + bus_start_row for i in range(num_ctg)]
        ctg_gen_start_row = [i * ctg_block_size + gen_start_row for i in range(num_ctg)]
        ctg_delta_start_row = [i * ctg_block_size + delta_start_row for i in range(num_ctg)]

        start_time_1 = time.time()
        for k in range(num_ctg):
            ctg_array = pd.read_csv(
                file_name,
                sep=',',
                header=None,
                names=['label'],
                dtype={'label':str},
                nrows=1,
                engine='c',
                skiprows=ctg_ctg_start_row[k],
                float_precision=pandas_float_precision)
            bus_array = pd.read_csv(
                file_name,
                sep=',',
                header=None,
                names=['i', 'vm', 'va', 'b'],
                dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
                nrows=num_bus,
                engine='c',
                skiprows=ctg_bus_start_row[k],
                float_precision=pandas_float_precision)
            gen_array = pd.read_csv(
                file_name,
                sep=',',
                header=None,
                names=['i', 'id', 'pg', 'qg'],
                dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'qg':np.float_},
                nrows=num_gen,
                engine='c',
                skiprows=ctg_gen_start_row[k],
                float_precision=pandas_float_precision)
            delta_array = pd.read_csv(
                file_name,
                sep=',',
                header=None,
                names=['delta'],
                dtype={'delta':np.float_},
                nrows=1,
                engine='c',
                skiprows=ctg_delta_start_row[k],
                float_precision=pandas_float_precision)
            #print(ctg_array.label.values.shape)
            print(ctg_array.label.values[0])
            #print(bus_array.i.values.shape)
        end_time_1 = time.time()
        print("sol2 average variable read time (pd 1): %f" % ((end_time_1 - start_time_1) / num_ctg))

        end_time = time.time()
        print("sol2 read time (pd 1): %f" % (end_time - start_time))

        start_time = time.time()
        bus_array = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'vm', 'va', 'b'],
            dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
            nrows=num_bus,
            engine='c',
            skiprows=2,
            float_precision=pandas_float_precision)
        self.bus_i = bus_array.i.values.tolist() # should this be a list?
        self.num_bus = len(self.bus_i)
        #print([self.num_bus, self.bus_i[self.num_bus - 1]])
        self.bus_map = {self.bus_i[i]:i for i in range(self.num_bus)}
        self.bus_volt_mag = bus_array.vm.values
        self.bus_volt_ang = bus_array.va.values
        self.bus_swsh_adm_imag = bus_array.b.values
        gen_array = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'id', 'pg', 'qg'],
            dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'pq':np.float_},
            nrows=num_gen,
            engine='c',
            skiprows=(4 + num_bus),
            float_precision=pandas_float_precision)
        self.gen_i = gen_array.i.values.tolist() # should this be a list?
        self.gen_id = gen_array.id.values.tolist() # should this be a list?
        self.num_gen = len(self.gen_i)
        self.gen_map = {(self.gen_i[i], self.gen_id[i]):i for i in range(self.num_gen)}
        #print(self.gen_id[0:10])
        self.gen_pow_real = gen_array.pg.values
        self.gen_pow_imag = gen_array.qg.values
        end_time = time.time()
        print("sol1 read time: %f" % (end_time - start_time))
    '''

    '''
    def read_sol2_2(self, file_name, num_bus, num_gen):
        
        start_time = time.time()
        #num_ctg = 21960
        num_ctg = 22
        ctg_block_size = num_bus + num_gen + 10
        num_rows = num_ctg * ctg_block_size

        def skip_row_in_chunk(i, chunk_size, start_row, num_rows):
            mod = i % chunk_size
            return ((mod < start_row) or 
        
        ctg_start_row = 2
        ctg_end_row = ctg_start_row + 1 - 1
        bus_start_row = ctg_end_row + 3
        bus_end_row = bus_start_row + num_bus - 1
        gen_start_row = bus_end_row + 3
        gen_end_row = gen_start_row + num_gen - 1
        delta_start_row = gen_end_row + 3
        delta_end_row = delta_start_row + 1 - 1

        def skip_row(i, block_size, start_row, end_row):
            mod = i % ctg_block_size
            return ((mod < start_row) or (mod > end_row))

        ctg_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, ctg_start_row, ctg_end_row)]
        bus_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, bus_start_row, bus_end_row)]
        gen_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, gen_start_row, gen_end_row)]
        delta_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, delta_start_row, delta_end_row)]

        ctg_reader = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['label'],
            dtype={'label':str},
            nrows=num_rows,
            skiprows=ctg_skip_rows,
            engine='c',
            chunksize=1,
            iterator=True,
            float_precision=pandas_float_precision)
        bus_reader = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'vm', 'va', 'b'],
            dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
            nrows=num_rows,
            skiprows=bus_skip_rows,
            engine='c',
            chunksize=num_bus,
            iterator=True,
            float_precision=pandas_float_precision)
        gen_reader = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['i', 'id', 'pg', 'qg'],
            dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'qg':np.float_},
            nrows=num_rows,
            skiprows=gen_skip_rows,
            engine='c',
            chunksize=num_gen,
            iterator=True,
            float_precision=pandas_float_precision)
        delta_reader = pd.read_csv(
            file_name,
            sep=',',
            header=None,
            names=['delta'],
            dtype={'delta':np.float_},
            nrows=num_rows,
            skiprows=delta_skip_rows,
            engine='c',
            chunksize=1,
            iterator=True,
            float_precision=pandas_float_precision)

        start_time_1 = time.time()
        for k in range(num_ctg):
            ctg_array = ctg_reader.get_chunk()
            #print(ctg_array.label.values.shape)
            #print(ctg_array.label.values[0])
            bus_array = bus_reader.get_chunk()
            #print(bus_array.i.values.shape)
            gen_array = gen_reader.get_chunk()
            delta_array = delta_reader.get_chunk()
            print([k, time.time() - start_time_1])
        end_time_1 = time.time()
        print("sol2 average variable read time (pd 2): %f" % ((end_time_1 - start_time_1) / num_ctg))

        end_time = time.time()
        print("sol2 read time (pd 2): %f" % (end_time - start_time))
    '''

    '''
    def read_sol2_3(self, file_name, num_bus, num_gen):
        
        def skip_row(i, block_size, start_row, end_row):
            mod = i % ctg_block_size
            return ((mod < start_row) or (mod > end_row))

        start_time = time.time()

        with open(file_name, 'r') as in_file:

            #num_ctg = 21960
            num_ctg = 22
            ctg_block_size = num_bus + num_gen + 10
            num_rows = num_ctg * ctg_block_size
        
            ctg_start_row = 2
            ctg_end_row = ctg_start_row + 1 - 1
            bus_start_row = ctg_end_row + 3
            bus_end_row = bus_start_row + num_bus - 1
            gen_start_row = bus_end_row + 3
            gen_end_row = gen_start_row + num_gen - 1
            delta_start_row = gen_end_row + 3
            delta_end_row = delta_start_row + 1 - 1

            ctg_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, ctg_start_row, ctg_end_row)]
            bus_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, bus_start_row, bus_end_row)]
            gen_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, gen_start_row, gen_end_row)]
            delta_skip_rows = [i for i in range(num_rows) if skip_row(i, ctg_block_size, delta_start_row, delta_end_row)]
            
            start_time_1 = time.time()
            for k in range(num_ctg):
                ctg_array = pd.read_csv(
                    in_file,
                    sep=',',
                    header=None,
                    names=['label'],
                    dtype={'label':str},
                    nrows=1,
                    engine='c',
                    skiprows=2,
                    float_precision=pandas_float_precision)
                print(ctg_array.label.values.shape)
                print(ctg_array.label.values[0])
                bus_array = pd.read_csv(
                    in_file,
                    sep=',',
                    header=None,
                    names=['i', 'vm', 'va', 'b'],
                    dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
                    #nrows=num_bus,
                    nrows=1,
                    engine='c',
                    skiprows=1,
                    float_precision=pandas_float_precision)
                print(bus_array.i.values.shape)
                print(bus_array.i.values[0])
                gen_array = pd.read_csv(
                    in_file,
                    sep=',',
                    header=None,
                    names=['i', 'id', 'pg', 'qg'],
                    dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'qg':np.float_},
                    nrows=num_gen,
                    engine='c',
                    skiprows=2,
                    float_precision=pandas_float_precision)
                delta_array = pd.read_csv(
                    in_file,
                    sep=',',
                    header=None,
                    names=['delta'],
                    dtype={'delta':np.float_},
                    nrows=1,
                    engine='c',
                    skiprows=2,
                    float_precision=pandas_float_precision)
                print([k, time.time() - start_time_1])
            end_time_1 = time.time()
            print("sol2 average variable read time (pd 3): %f" % ((end_time_1 - start_time_1) / num_ctg))

        end_time = time.time()
        print("sol2 read time (pd 3): %f" % (end_time - start_time))
    '''

    '''
    def read_sol2_4(self, file_name, num_bus, num_gen):
        
        #num_ctg = 21960
        #num_ctg = 2200
        num_ctg = 220
        ctg_block_size = num_bus + num_gen + 10
        num_rows = num_ctg * ctg_block_size

        ctg_start = 0
        ctg_end = ctg_start + 2 + 1
        bus_start = ctg_end
        bus_end = bus_start + 2 + num_bus
        gen_start = bus_end
        gen_end = gen_start + 2 + num_gen
        delta_start = gen_end
        delta_end = delta_start + 2 + 1
        
        ndigits_test = 40
        bus_lines_test = ['\n'] + ['\n'] + [('%u,1.%s,0.%s,0.%s\n' % (i, ndigits_test*'0', ndigits_test*'0', ndigits_test*'0')) for i in range(num_bus)]

        start_time = time.time()
        with open(file_name) as in_file:
            for k in range(num_ctg):
                
                # get lines for each section as a generator
                ctg_lines = islice(in_file, 2 + 1)
                bus_lines = islice(in_file, 2 + num_bus)
                gen_lines = islice(in_file, 2 + num_gen)
                delta_lines = islice(in_file, 2 + 1)

                # test?
                #bus_lines = bus_lines_test
                #bus_str = lines_to_str(bus_lines)

                # write lines to a string buffer
                def lines_to_str(lines):
                    #out_str = StringIO.StringIO(''.join(lines))
                    #out_str = StringIO.StringIO()
                    #out_str = StringIO.StringIO('foo')
                    out_str = cStringIO.StringIO()
                    #out_str = cStringIO.StringIO(''.join(lines))
                    out_str.writelines(lines)
                    #out_str.write('foo')
                    #out_str.flush() # do we need this?
                    #out_str.close()
                    #for l in list(lines):
                        #print(l)
                        #out_str.write(str(l))
                    #out_str.close()
                    out_str.seek(0) # need this so that read() starts at the beginning of the string
                    return out_str
                ctg_str = lines_to_str(ctg_lines)
                bus_str = lines_to_str(bus_lines)
                gen_str = lines_to_str(gen_lines)
                delta_str = lines_to_str(delta_lines)

                # test?
                #bus_lines = bus_lines_test
                #bus_str = lines_to_str(bus_lines)

                #ctg_str.open()
                #print(ctg_str.read())

                # parse file string to pandas df
                ctg_df = pd.read_csv(
                    ctg_str, sep=',', header=None, names=['label'], dtype={'label':str},
                    nrows=1, engine='c', skiprows=2, float_precision=pandas_float_precision)
                bus_df = pd.read_csv(
                    bus_str, sep=',', header=None, names=['i', 'vm', 'va', 'b'],
                    dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
                    nrows=num_bus, engine='c', skiprows=2, float_precision=pandas_float_precision)
                gen_df = pd.read_csv(
                    gen_str, sep=',', header=None, names=['i', 'id', 'pg', 'qg'],
                    dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'qg':np.float_},
                    nrows=num_gen, engine='c', skiprows=2, float_precision=pandas_float_precision)
                delta_df = pd.read_csv(
                    delta_str, sep=',', header=None, names=['delta'],
                    dtype={'delta':np.float_}, nrows=1, engine='c', skiprows=2, float_precision=pandas_float_precision)
                
                self.bus_df = bus_df
                self.gen_df = gen_df
                self.ctg_label = ctg_df.label.values[0]
                self.num_bus = bus_df.shape[0]
                self.num_gen = gen_df.shape[0]
                self.delta = delta_df.delta.values[0]
                
                print('ctg: %s, num bus: %u, num gen: %u, delta: %f' % (self.ctg_label, self.num_bus, self.num_gen, self.delta))
                
        end_time = time.time()
        print("sol2 read time (pd 4): %f" % (end_time - start_time))
        print("sol2 read time (pd 4, average): %f" % ((end_time - start_time) / num_ctg))
    '''
            
    def read_bus_rows(self, rows):

        i = 0
        vm = 1
        va = 2
        b = 3
        start_time = time.time()
        self.num_bus = len(rows)
        self.bus_i = [int(r[i]) for r in rows]
        self.bus_map = {self.bus_i[i]:i for i in range(self.num_bus)}
        self.bus_volt_mag = np.array([float(r[vm]) for r in rows])
        self.bus_volt_ang = np.array([float(r[va]) for r in rows])
        self.bus_swsh_adm_imag = np.array([float(r[b]) for r in rows])
        end_time = time.time()
        print('sol1 read bus time: %f' % (end_time - start_time))

    def read_gen_rows(self, rows):

        i = 0
        id = 1
        p = 2
        q = 3
        start_time = time.time()
        self.num_gen = len(rows)
        self.gen_i = [int(r[i]) for r in rows]
        self.gen_id = [str(r[id]).replace(' ', '') for r in rows]
        self.gen_map = {(self.gen_i[i], self.gen_id[i]):i for i in range(self.num_gen)}
        self.gen_pow_real = np.array([float(r[p]) for r in rows])
        self.gen_pow_imag = np.array([float(r[q]) for r in rows])
        end_time = time.time()
        print('sol1 read gen time: %f' % (end_time - start_time))

class Solution2:
    '''In physical units, i.e. data convention, i.e. same as input and output data files'''

    def __init__(self):
        '''items to be read from solution2.txt'''

        self.ctg_label = ""
        self.bus_volt_mag = {}
        self.bus_volt_ang = {}
        self.bus_swsh_adm_imag = {}
        self.gen_pow_real = {}
        self.gen_pow_imag = {}
        self.pow_real_change = 0.0

    def display(self):

        print("ctg_label: %s" % self.ctg_label)
        print("bus_volt_mag:")
        print(self.bus_volt_mag)
        print("bus_volt_ang:")
        print(self.bus_volt_ang)
        print("bus_swsh_adm_imag:")
        print(self.bus_swsh_adm_imag)
        print("gen_pow_real:")
        print(self.gen_pow_real)
        print("gen_pow_imag:")
        print(self.gen_pow_imag)
        print("pow_real_change:")
        print(self.pow_real_change)

    def get_all_ctg_label_lines(self, in_file, num_bus, num_gen):

        return []

    def get_all_gen_start_lines(self, in_file, num_bus, num_gen):

        return []

    def get_all_bus_start_lines(self, in_file, num_bus, num_gen):

        return []

    def read_next_ctg(self, in_file, num_bus, num_gen):

        ctg_block_size = get_ctg_block_size(num_bus, num_gen)

        ctg_start = 0
        ctg_end = ctg_start + 2 + 1
        bus_start = ctg_end
        bus_end = bus_start + 2 + num_bus
        gen_start = bus_end
        gen_end = gen_start + 2 + num_gen
        delta_start = gen_end
        delta_end = delta_start + 2 + 1
        
        # get lines for each section as a generator
        ctg_lines = islice(in_file, 2 + 1)
        bus_lines = islice(in_file, 2 + num_bus)
        gen_lines = islice(in_file, 2 + num_gen)
        delta_lines = islice(in_file, 2 + 1)
        
        # write lines to a string buffer
        def lines_to_str(lines):
            #out_str = StringIO.StringIO(''.join(lines))
            #out_str = StringIO.StringIO()
            #out_str = StringIO.StringIO('foo')
            #out_str = cStringIO.StringIO()
            out_str = StringIO()
            #out_str = cStringIO.StringIO(''.join(lines))
            out_str.writelines(lines)
            #out_str.write('foo')
            #out_str.flush() # do we need this?
            #out_str.close()
            #out_str.close()
            out_str.seek(0) # need this so that read() (called by pd.*) starts at the beginning of the string
            return out_str
        ctg_str = lines_to_str(ctg_lines)
        bus_str = lines_to_str(bus_lines)
        gen_str = lines_to_str(gen_lines)
        delta_str = lines_to_str(delta_lines)

        # parse file string to pandas df
        ctg_df = pd.read_csv(
            ctg_str, sep=',', header=None, names=['label'], dtype={'label':str},
            nrows=1, engine='c', skiprows=2, skipinitialspace=True, float_precision=pandas_float_precision)
        bus_df = pd.read_csv(
            bus_str, sep=',', header=None, names=['i', 'vm', 'va', 'b'],
            dtype={'i':np.int_, 'vm':np.float_, 'va':np.float_, 'b':np.float_},
            nrows=num_bus, engine='c', skiprows=2, skipinitialspace=True, float_precision=pandas_float_precision)
        gen_df = pd.read_csv(
            gen_str, sep=',', header=None, names=['i', 'id', 'pg', 'qg'],
            dtype={'i':np.int_, 'id':str, 'pg':np.float_, 'qg':np.float_},
            nrows=num_gen, engine='c', skiprows=2, skipinitialspace=True, float_precision=pandas_float_precision,
            na_values=None, keep_default_na=False #, #quoting=csv.QUOTE_NONE,
        )
        delta_df = pd.read_csv(
            delta_str, sep=',', header=None, names=['delta'],
            dtype={'delta':np.float_}, nrows=1, engine='c', skiprows=2, skipinitialspace=True, float_precision=pandas_float_precision)
                
        self.bus_df = bus_df
        self.gen_df = gen_df
        self.ctg_label = ctg_df.label.values[0]
        self.num_bus = bus_df.shape[0]
        self.num_gen = gen_df.shape[0]
        self.delta = delta_df.delta.values[0]
                
        #print('ctg: %s, num bus: %u, num gen: %u, delta: %f' % (self.ctg_label, self.num_bus, self.num_gen, self.delta))

    def read_from_lines(self, lines):
        """read a sol2 object from a list of text lines
        the lines may be selected as a single contingency from a file
        containing multiple contingencies"""

        con = 0
        bus = 1
        gen = 2
        delta = 3
        section_start_line_str = '--'
        has_headers = True
        sections = solution_read_sections_from_lines(lines, section_start_line_str, has_headers)
        self.read_con_rows(sections[con])
        self.read_bus_rows(sections[bus])
        self.read_gen_rows(sections[gen])
        self.read_delta_rows(sections[delta])

    def read_con_rows(self, rows):

        k = 0
        assert(len(rows) == 1)
        r = rows[0]
        rk = str(r[k])
        self.ctg_label = rk

    def read_bus_rows(self, rows):

        i = 0
        vm = 1
        va = 2
        b = 3
        for r in rows:
            ri = int(r[i])
            rvm = float(r[vm])
            rva = float(r[va])
            rb = float(r[b])
            self.bus_volt_mag[ri] = rvm
            self.bus_volt_ang[ri] = rva
            self.bus_swsh_adm_imag[ri] = rb

    def read_gen_rows(self, rows):

        i = 0
        id = 1
        p = 2
        q = 3
        for r in rows:
            ri = int(r[i])
            rid = str(r[id])
            rp = float(r[p])
            rq = float(r[q])
            self.gen_pow_real[(ri,rid)] = rp
            self.gen_pow_imag[(ri,rid)] = rq

    def read_delta_rows(self, rows):

        p = 0
        assert(len(rows) == 1)
        r = rows[0]
        rp = float(r[p])
        self.pow_real_change = rp

def trans_old(raw_name, rop_name, con_name, inl_nsame,filename):

    # read the data files
    p = data.Data()
    p.raw.read(raw_name)
    if rop_name[-3:]=='csv':
        p.rop.read_from_phase_0(rop_name)
        p.rop.trancostfuncfrom_phase_0(p.raw)
        p.rop.write(filename+".rop",p.raw)
        p.con.read_from_phase_0(con_name)
        p.con.write(filename+".con")
        p.inl.write(filename+".inl",p.raw,p.rop)
    
def run(raw_name, rop_name, con_name, inl_name, sol1_name=None, sol2_name=None, summary_name=None, detail_name=None):

    # start timer
    start_time_all = time.time()
    
    # read the data files
    start_time = time.time()
    p = data.Data()
    p.raw.read(raw_name)
    p.rop.read(rop_name)
    p.con.read(con_name)
    p.inl.read(inl_name)
    time_elapsed = time.time() - start_time
    print("read data time: %u" % time_elapsed)
    
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
    
    print('done reading data')

    if sol1_name is None:
        return True

    # set up evaluation
    e = Evaluation()
    e.set_data(p)
    e.set_params()

    print('done setting evaluation data')
    
    # base case solution evaluation
    start_time = time.time()
    s1 = Solution1()
    s1.read(sol1_name, e.num_bus, e.num_gen) # this is now fairly long ~ 0.17 second
    e.set_solution1(s1)
    e.eval_base()
    e.write_header(detail_name)
    e.write_base(detail_name)
    e.print_base()
    end_time = time.time()
    print("total base case time: %f" % (end_time - start_time))

    print('done evaluating base case - solution 1')

    if sol2_name is None:
        return True

    # ctg solution evaluation - loop over ctg to save memory
    # get ctg structure in sol
    # need to check that every contingency is found in the sol file
    start_time = time.time()
    ok = check_sol2_num_lines(sol2_name, e.num_bus, e.num_gen, e.num_ctg)
    ok = check_sol2_ctg_labels(sol2_name, e.num_bus, e.num_gen, e.ctg_label)
    s2 = Solution2()
    ctgs_reported = []
    print('start ctg eval')
    print('ctg eval log')
    print(
        '%12s %12s %12s %12s %12s' %
        ('ctg done', 'ctg to go', 't elapsed', 't per ctg', 't to go'))
    ctg_counter = 0
    time_elapsed = time.time() - start_time
    log_counter = 0
    ctg_to_go = e.num_ctg - ctg_counter
    time_per_ctg = 'na'
    time_to_go = 'na'
    print(
        '%12u %12u %12.2e %12s %12s' %
        (ctg_counter, ctg_to_go, time_elapsed, time_per_ctg, time_to_go))
    with open(sol2_name) as sol2_file:
        for k in range(e.num_ctg):
            s2.read_next_ctg(sol2_file, e.num_bus, e.num_gen)
            e.set_solution2(s2)
            ctgs_reported.append(e.ctg_current)
            e.set_ctg_data()
            e.eval_ctg()
            e.write_ctg(detail_name)
            ctg_counter += 1
            time_elapsed = time.time() - start_time
            if time_elapsed > float(log_counter + 1) * float(log_time):
                log_counter += 1
                ctg_to_go = e.num_ctg - ctg_counter
                time_per_ctg = time_elapsed / float(ctg_counter)
                time_to_go = float(ctg_to_go) * time_per_ctg
                print(
                    '%12u %12u %12.2e %12.2e %12.2e' %
                    (ctg_counter, ctg_to_go, time_elapsed, time_per_ctg, time_to_go))
    num_ctgs_reported = len(ctgs_reported)
    num_ctgs_reported_unique = len(set(ctgs_reported))
    if (num_ctgs_reported != num_ctgs_reported_unique or
        num_ctgs_reported != e.num_ctg):
        e.infeas = 1
        print("infeas, problem with contingency list in sol file")
        print("num ctg (con file): %u" % e.num_ctg)
        print("num ctg reported (sol2 file): %u" % num_ctgs_reported)
        print("num ctg reported unique (sol2 file): %u" % num_ctgs_reported_unique)
    time_elapsed = time.time() - start_time
    print("eval ctg time: %u" % time_elapsed)
    
    time_elapsed = time.time() - start_time_all
    print("eval total time: %u" % time_elapsed)
    
    print("obj: %f" % e.obj)
    print("cost: %f" % e.cost)
    print("penalty: %f" % (e.obj - e.cost))
    print("max_obj_viol: %f" % e.max_obj_viol)
    print("max_nonobj_viol: %f" % e.max_nonobj_viol)
    print("infeas: %u" % e.infeas)

    print('done evaluating contingencies - solution 2')
    print('done evaluating solution')
    
    return (e.obj, e.cost, e.obj - e.cost, e.max_obj_viol, e.max_nonobj_viol, e.infeas)
