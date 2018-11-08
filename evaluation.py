import csv
import math
import data
import time
#from collections import OrderedDict
from itertools import islice
import numpy as np
#from io import open

"""
TODO
write output in data units, not p.u.
write summary with only worst contingency for each category
numpy
process scenarios in parallel
"""

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

def eval_piecewise_linear_penalty(residual, penalty_block_max, penalty_block_coeff):
    print('len of resid %u' % len(residual))
    r = list(residual)
    num_block = len(penalty_block_coeff)
    num_block_bounded = len(penalty_block_max)
    assert(num_block_bounded + 1 == num_block)
    num_resid = len(r)
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

    ctg_start_str = '--con'
    with open(file_name, 'r') as in_file:
        lines = in_file.readlines()
    num_lines = len(lines)
    ctg_start_lines = [
        i for i in range(num_lines)
        if lines[i].startswith(ctg_start_str)]
    num_ctgs = len(ctg_start_lines)
    ctg_end_lines = [
        ctg_start_lines[i + 1]
        for i in range(num_ctgs - 1)]
    ctg_end_lines += [num_lines]
    ctg_num_lines = [
        ctg_end_lines[i] - ctg_start_lines[i]
        for i in range(num_ctgs)]
    return ctg_num_lines

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

    def set_data(self, data):
        ''' set values from the data object
        convert to per unit (p.u.) convention'''

        self.bus = [r.i for r in data.raw.buses.values()]
        self.load = [(r.i,r.id) for r in data.raw.loads.values()]
        self.fxsh = [(r.i,r.id) for r in data.raw.fixed_shunts.values()]
        self.gen = [(r.i,r.id) for r in data.raw.generators.values()]
        self.line = [(r.i,r.j,r.ckt) for r in data.raw.nontransformer_branches.values()]
        self.xfmr = [(r.i,r.j,r.ckt) for r in data.raw.transformers.values()]
        self.swsh = [r.i for r in data.raw.switched_shunts.values()]
        self.area = [r.i for r in data.raw.areas.values()]
        self.ctg = [r.label for r in data.con.contingencies.values()]
        
        self.base_mva = data.raw.case_identification.sbase

        self.bus_base_kv = {
            r.i:r.baskv
            for r in data.raw.buses.values()}
        self.bus_volt_mag_max = {
            r.i:r.nvhi
            for r in data.raw.buses.values()}
        self.bus_volt_mag_min = {
            r.i:r.nvlo
            for r in data.raw.buses.values()}
        self.ctg_bus_volt_mag_max = {
            r.i:r.evhi
            for r in data.raw.buses.values()}
        self.ctg_bus_volt_mag_min = {
            r.i:r.evlo
            for r in data.raw.buses.values()}
        self.bus_area = {
            r.i:r.area
            for r in data.raw.buses.values()}

        self.load_const_pow_real = {
            (r.i,r.id):(r.pl/self.base_mva)
            for r in data.raw.loads.values()}
        self.load_const_pow_imag = {
            (r.i,r.id):(r.ql/self.base_mva)
            for r in data.raw.loads.values()}
        self.load_status = {
            (r.i,r.id):r.status
            for r in data.raw.loads.values()}

        self.fxsh_adm_real = {
            (r.i,r.id):(r.gl/self.base_mva)
            for r in data.raw.fixed_shunts.values()}
        self.fxsh_adm_imag = {
            (r.i,r.id):(r.bl/self.base_mva)
            for r in data.raw.fixed_shunts.values()}
        self.fxsh_status = {
            (r.i,r.id):r.status
            for r in data.raw.fixed_shunts.values()}

        self.gen_status = {
            (r.i,r.id):r.stat
            for r in data.raw.generators.values()}
        self.gen_pow_imag_max = {
            (r.i,r.id):(r.qt/self.base_mva)
            for r in data.raw.generators.values()}
        self.gen_pow_imag_min = {
            (r.i,r.id):(r.qb/self.base_mva)
            for r in data.raw.generators.values()}
        self.gen_pow_real_max = {
            (r.i,r.id):(r.pt/self.base_mva)
            for r in data.raw.generators.values()}
        self.gen_pow_real_min = {
            (r.i,r.id):(r.pb/self.base_mva)
            for r in data.raw.generators.values()}
        self.gen_part_fact = {
            (r.i,r.id):r.r
            for r in data.inl.generator_inl_records.values()}

        self.line_adm_real = {
            (r.i,r.j,r.ckt):(r.r/(r.r**2.0 + r.x**2.0))
            for r in data.raw.nontransformer_branches.values()}
        self.line_adm_imag = {
            (r.i,r.j,r.ckt):(-r.x/(r.r**2.0 + r.x**2.0))
            for r in data.raw.nontransformer_branches.values()}
        self.line_adm_ch_imag = {
            (r.i,r.j,r.ckt):r.b
            for r in data.raw.nontransformer_branches.values()}
        self.line_curr_mag_max = {
            (r.i,r.j,r.ckt):(r.ratea/self.base_mva) # todo - normalize by bus base kv???
            for r in data.raw.nontransformer_branches.values()}
        self.ctg_line_curr_mag_max = {
            (r.i,r.j,r.ckt):(r.ratec/self.base_mva) # todo - normalize by bus base kv???
            for r in data.raw.nontransformer_branches.values()}
        self.line_status = {
            (r.i,r.j,r.ckt):r.st
            for r in data.raw.nontransformer_branches.values()}

        self.xfmr_adm_real = {
            (r.i,r.j,r.ckt):(r.r12 / (r.r12**2.0 + r.x12**2.0))
            for r in data.raw.transformers.values()}
        self.xfmr_adm_imag = {
            (r.i,r.j,r.ckt):(-r.x12 / (r.r12**2.0 + r.x12**2.0))
            for r in data.raw.transformers.values()}
        self.xfmr_adm_mag_real = {
            (r.i,r.j,r.ckt):r.mag1 # todo normalize?
            for r in data.raw.transformers.values()}
        self.xfmr_adm_mag_imag = {
            (r.i,r.j,r.ckt):r.mag2 # todo normalize?
            for r in data.raw.transformers.values()}
        self.xfmr_tap_mag = {
            (r.i,r.j,r.ckt):(r.windv1/r.windv2)
            for r in data.raw.transformers.values()}
        self.xfmr_tap_ang = {
            (r.i,r.j,r.ckt):(r.ang1*math.pi/180.0)
            for r in data.raw.transformers.values()}
        self.xfmr_pow_mag_max = {
            (r.i,r.j,r.ckt):(r.rata1/self.base_mva) # todo check normalization
            for r in data.raw.transformers.values()}
        self.ctg_xfmr_pow_mag_max = {
            (r.i,r.j,r.ckt):(r.ratc1/self.base_mva) # todo check normalization
            for r in data.raw.transformers.values()}
        self.xfmr_status = {
            (r.i,r.j,r.ckt):r.stat
            for r in data.raw.transformers.values()}

        # swsh
        self.swsh_status = {
            r.i:r.stat
            for r in data.raw.switched_shunts.values()}
        self.swsh_adm_imag_max = {
            r.i:((max(0.0, r.n1 * r.b1) +
                  max(0.0, r.n2 * r.b2) +
                  max(0.0, r.n3 * r.b3) +
                  max(0.0, r.n4 * r.b4) +
                  max(0.0, r.n5 * r.b5) +
                  max(0.0, r.n6 * r.b6) +
                  max(0.0, r.n7 * r.b7) +
                  max(0.0, r.n8 * r.b8)) / self.base_mva)
            for r in data.raw.switched_shunts.values()}
        self.swsh_adm_imag_min = {
            r.i:((min(0.0, r.n1 * r.b1) +
                  min(0.0, r.n2 * r.b2) +
                  min(0.0, r.n3 * r.b3) +
                  min(0.0, r.n4 * r.b4) +
                  min(0.0, r.n5 * r.b5) +
                  min(0.0, r.n6 * r.b6) +
                  min(0.0, r.n7 * r.b7) +
                  min(0.0, r.n8 * r.b8)) / self.base_mva)
            for r in data.raw.switched_shunts.values()}

        # todo clean up maybe
        # defines some attributes that need to be initialized above
        # piecewise linear cost functions
        #'''
        for r in data.rop.generator_dispatch_records.values():
            r_bus = r.bus
            r_genid = r.genid
            r_dsptbl = r.dsptbl
            s = data.rop.active_power_dispatch_records[r_dsptbl]
            r_ctbl = s.ctbl
            t = data.rop.piecewise_linear_cost_functions[r_ctbl]
            r_npairs = t.npairs
            self.gen_num_pl[(r_bus,r_genid)] = r_npairs
            for i in range(r_npairs):
                key = (r_bus, r_genid, i + 1)
                self.gen_pl_x[key] = t.points[i].x / self.base_mva
                self.gen_pl_y[key] = t.points[i].y            
        #'''

        # maps from buses to components
        self.bus_load = {
            i:[k for k in self.load if k[0] == i]
            for i in self.bus}
        self.bus_fxsh = {
            i:[k for k in self.fxsh if k[0] == i]
            for i in self.bus}
        self.bus_gen = {
            i:[k for k in self.gen if k[0] == i]
            for i in self.bus}
        self.bus_line_orig = {
            i:[k for k in self.line if k[0] == i]
            for i in self.bus}
        self.bus_line_dest = {
            i:[k for k in self.line if k[1] == i]
            for i in self.bus}
        self.bus_xfmr_orig = {
            i:[k for k in self.xfmr if k[0] == i]
            for i in self.bus}
        self.bus_xfmr_dest = {
            i:[k for k in self.xfmr if k[1] == i]
            for i in self.bus}

        self.bus_swsh_adm_imag_max = {i:0.0 for i in self.bus}
        self.bus_swsh_adm_imag_max.update(
            {i:self.swsh_adm_imag_max[i]
             for i in self.swsh if self.swsh_status[i]})
        self.bus_swsh_adm_imag_min = {i:0.0 for i in self.bus}
        self.bus_swsh_adm_imag_min.update(
            {i:self.swsh_adm_imag_min[i]
             for i in self.swsh if self.swsh_status[i]})
        
        # contingency records
        # TODO - stll need gen_ctg_part_fact
        # and area_ctg_affected will need to be done more carefully
        self.gen_area = {r:self.bus_area[r[0]] for r in self.gen}
        self.area_gens = {a:set() for a in self.area}
        for i in self.gen:
            self.area_gens[self.gen_area[i]].add(i)
        self.ctg_gens_out = {k:set() for k in self.ctg}
        self.ctg_lines_out = {k:set() for k in self.ctg}
        self.ctg_xfmrs_out = {k:set() for k in self.ctg}
        self.ctg_areas_affected = {k:set() for k in self.ctg}
        for r in data.con.contingencies.values():
            for e in r.branch_out_events:
                if (e.i, e.j, e.ckt) in data.raw.nontransformer_branches.keys():
                    self.ctg_lines_out[r.label].add((e.i, e.j, e.ckt))
                    self.ctg_areas_affected[r.label].add(self.bus_area[e.i])
                    self.ctg_areas_affected[r.label].add(self.bus_area[e.j])
                if (e.i, e.j, 0, e.ckt) in data.raw.transformers.keys():
                    self.ctg_xfmrs_out[r.label].add((e.i, e.j, e.ckt))
                    self.ctg_areas_affected[r.label].add(self.bus_area[e.i])
                    self.ctg_areas_affected[r.label].add(self.bus_area[e.j])
            for e in r.generator_out_events:
                self.ctg_gens_out[r.label].add((e.i, e.id))
                self.ctg_areas_affected[r.label].add(self.bus_area[e.i])
        #self.gen_ctg_participating = {
        #    (r[0],r[1],k):(
        #        1 if (
        #            self.gen_ctg_active[(r[0],r[1],k)] and
        #            self.area_ctg_affected[(self.gen_area[r],k)])
        #        else 0)
        #    for r in self.gen
        #    for k in self.ctg}

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

        self.bus_volt_mag = {
            i:solution1.bus_volt_mag[i]
            for i in self.bus}
        self.bus_volt_ang = {
            i:solution1.bus_volt_ang[i] * math.pi / 180.0
            for i in self.bus}
        self.bus_swsh_adm_imag = {
            i:solution1.bus_swsh_adm_imag[i] / self.base_mva
            for i in self.bus}
        self.gen_pow_real = {
            i:solution1.gen_pow_real[i] / self.base_mva
            for i in self.gen}
        self.gen_pow_imag = {
            i:solution1.gen_pow_imag[i] / self.base_mva
            for i in self.gen}
    
    def set_solution2(self, solution2):
        ''' set values from the solution objects
        convert to per unit (p.u.) convention'''

        self.ctg_label = solution2.ctg_label
        self.ctg_bus_volt_mag = {
            i:solution2.bus_volt_mag[i]
            for i in self.bus}
        self.ctg_bus_volt_ang = {
            i:solution2.bus_volt_ang[i] * math.pi / 180.0
            for i in self.bus}
        self.ctg_bus_swsh_adm_imag = {
            i:solution2.bus_swsh_adm_imag[i] / self.base_mva
            for i in self.bus}
        self.ctg_gen_pow_real = {
            i:solution2.gen_pow_real[i] / self.base_mva
            for i in self.gen}
        self.ctg_gen_pow_imag = {
            i:solution2.gen_pow_imag[i] / self.base_mva
            for i in self.gen}
        self.ctg_pow_real_change = solution2.pow_real_change / self.base_mva

    def set_ctg_data(self):

        self.ctg_gen_active = {
            i:self.gen_status[i]
            for i in self.gen}
        self.ctg_gen_active.update(
            {i:0 for i in self.ctg_gens_out[self.ctg_label]})
        self.ctg_line_active = {
            i:self.line_status[i]
            for i in self.line}
        self.ctg_line_active.update(
            {i:0 for i in self.ctg_lines_out[self.ctg_label]})
        self.ctg_xfmr_active = {
            i:self.xfmr_status[i]
            for i in self.xfmr}
        self.ctg_xfmr_active.update(
            {i:0 for i in self.ctg_xfmrs_out[self.ctg_label]})
        self.ctg_gen_participating = {i:0 for i in self.gen}
        self.ctg_gen_participating.update(
            {i:self.ctg_gen_active[i]
             for a in self.ctg_areas_affected[self.ctg_label]
             for i in self.area_gens[a]})

    def write_header(self, det_name):
        """write header line for detailed output"""

        #with open(det_name, 'w', newline='', encoding='utf-8') as out:
        with open(det_name, 'wb') as out:
            csv_writer = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            #csv_writer.writerow(['foo'])
            #'''
            csv_writer.writerow(
                ['ctg', 'infeas', 'pen', 'cost', 'obj',
                 'vmax-idx',
                 'vmax-val',
                 'vmin-idx',
                 'vmin-val',
                 'bmax-idx',
                 'bmax-val',
                 'bmin-idx',
                 'bmin-val',
                 'pbal-idx',
                 'pbal-val',
                 'qbal-idx',
                 'qbal-val',
                 'pgmax-idx',
                 'pgmax-val',
                 'pgmin-idx',
                 'pgmin-val',
                 'qgmax-idx',
                 'qgmax-val',
                 'qgmin-idx',
                 'qgmin-val',
                 'qvg1-idx',
                 'qvg1-val',
                 'qvg2-idx',
                 'qvg2-val',
                 'lineomax-idx',
                 'lineomax-val',
                 'linedmax-idx',
                 'linedmax-val',
                 'xfmromax-idx',
                 'xfmromax-val',
                 'xfmrdmax-idx',
                 'xfmrdmax-val',
            ])
            #'''

    def write_base(self, det_name):
        """write detail of base case evaluation"""

        #with open(det_name, 'a', newline='') as out:
        with open(det_name, 'ab') as out:
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

    def write_ctg(self, det_name):
        """write detail of ctg evaluation"""        

        #with open(det_name, 'a', newline='') as out:
        with open(det_name, 'ab') as out:
            csv_writer = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(
                [self.ctg_label, self.ctg_infeas, self.ctg_penalty, 0.0, self.obj,
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
                 self.ctg_max_gen_pow_real_max_viol[0],
                 self.ctg_max_gen_pow_real_max_viol[1],
                 self.ctg_max_gen_pow_real_min_viol[0],
                 self.ctg_max_gen_pow_real_min_viol[1],
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
        self.compute_detail()
        self.eval_infeas()
        self.eval_penalty()
        self.eval_obj()

    def eval_ctg(self):

        self.eval_ctg_bus_volt_viol()
        self.eval_ctg_load_pow()
        self.eval_ctg_fxsh_pow()
        self.eval_ctg_gen_pow_real()
        #self.eval_ctg_gen_pow_real_viol()
        self.eval_ctg_gen_pow_imag_viol()
        self.eval_ctg_line_pow()
        self.eval_ctg_line_curr_viol()
        self.eval_ctg_xfmr_pow()
        self.eval_ctg_xfmr_pow_viol()
        self.eval_ctg_bus_swsh_adm_imag_viol()
        self.eval_ctg_bus_swsh_pow()
        self.eval_ctg_bus_pow_balance()
        self.eval_ctg_gen_pvpq_viol()
        self.compute_ctg_detail()
        self.eval_ctg_infeas()
        self.eval_ctg_penalty()
        self.eval_ctg_update_obj()
        self.eval_ctg_update_infeas()

    def eval_ctg_update_obj(self):

        self.obj += self.ctg_penalty

    def eval_ctg_update_infeas(self):

        if self.ctg_infeas > 0:
            self.infeas = 1
    
    def eval_cost(self):
        # todo: what if gen_pow_real falls outside of domain of definition
        # of cost function?
        # maybe just assign maximum cost value as the cost

        self.gen_pl_cost = {}
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

    def eval_bus_volt_viol(self):

        self.bus_volt_mag_min_viol = {
            k:max(0.0, self.bus_volt_mag_min[k] - self.bus_volt_mag[k])
            for k in self.bus}
        self.bus_volt_mag_max_viol = {
            k:max(0.0, self.bus_volt_mag[k] - self.bus_volt_mag_max[k])
            for k in self.bus}

    def eval_load_pow(self):

        self.load_pow_real = {
            k:(self.load_const_pow_real[k]
               if self.load_status[k] else 0.0)
            for k in self.load}
        self.load_pow_imag = {
            k:(self.load_const_pow_imag[k]
               if self.load_status[k] else 0.0) 
            for k in self.load}

    def eval_fxsh_pow(self):

        self.fxsh_pow_real = {
            k:(self.fxsh_adm_real[k] * self.bus_volt_mag[k[0]]**2.0
               if self.fxsh_status[k] else 0.0)
            for k in self.fxsh}
        self.fxsh_pow_imag = {
            k:(-self.fxsh_adm_imag[k] * self.bus_volt_mag[k[0]]**2.0
               if self.fxsh_status[k] else 0.0)
            for k in self.fxsh}

    def eval_gen_pow_viol(self):

        self.gen_pow_real_min_viol = {
            k:max(0.0, (self.gen_pow_real_min[k] if self.gen_status[k] else 0.0) - self.gen_pow_real[k])
            for k in self.gen}
        self.gen_pow_real_max_viol = {
            k:max(0.0, self.gen_pow_real[k] - (self.gen_pow_real_max[k] if self.gen_status[k] else 0.0))
            for k in self.gen}
        self.gen_pow_imag_min_viol = {
            k:max(0.0, (self.gen_pow_imag_min[k] if self.gen_status[k] else 0.0) - self.gen_pow_imag[k])
            for k in self.gen}
        self.gen_pow_imag_max_viol = {
            k:max(0.0, self.gen_pow_imag[k] - (self.gen_pow_imag_max[k] if self.gen_status[k] else 0.0))
            for k in self.gen}

    def eval_line_pow(self):

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
        
        self.line_pow_orig_real = {
            k:( self.line_adm_real[k] * self.bus_volt_mag[k[0]]**2.0 +
                ( - self.line_adm_real[k] * math.cos(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]])
                  - self.line_adm_imag[k] * math.sin(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.line_status[k] else 0.0)
            for k in self.line}
        self.line_pow_orig_imag = {
            k:( - (self.line_adm_imag[k] + 0.5 * self.line_adm_ch_imag[k]) * self.bus_volt_mag[k[0]]**2.0 +
                (   self.line_adm_imag[k] * math.cos(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]])
                  - self.line_adm_real[k] * math.sin(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.line_status[k] else 0.0)
            for k in self.line}
        self.line_pow_dest_real = {
            k:( self.line_adm_real[k] * self.bus_volt_mag[k[1]]**2.0 +
                ( - self.line_adm_real[k] * math.cos(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]])
                  - self.line_adm_imag[k] * math.sin(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.line_status[k] else 0.0)
            for k in self.line}
        self.line_pow_dest_imag = {
            k:( - (self.line_adm_imag[k] + 0.5 * self.line_adm_ch_imag[k]) * self.bus_volt_mag[k[1]]**2.0 +
                (   self.line_adm_imag[k] * math.cos(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]])
                  - self.line_adm_real[k] * math.sin(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.line_status[k] else 0.0)
            for k in self.line}

    def eval_line_curr_viol(self):

        self.line_curr_orig_mag_max_viol = {
            k:max(
                0.0,
                (self.line_pow_orig_real[k]**2.0 +
                 self.line_pow_orig_imag[k]**2.0)**0.5 -
                self.line_curr_mag_max[k] * self.bus_volt_mag[k[0]])
            for k in self.line}
        self.line_curr_dest_mag_max_viol = {
            k:max(
                0.0,
                (self.line_pow_dest_real[k]**2.0 +
                 self.line_pow_dest_imag[k]**2.0)**0.5 -
                self.line_curr_mag_max[k] * self.bus_volt_mag[k[1]])
            for k in self.line}

    def eval_xfmr_pow(self):

        self.xfmr_pow_orig_real = {
            k:( (self.xfmr_adm_real[k] / self.xfmr_tap_mag[k]**2.0 + self.xfmr_adm_mag_real[k]) * self.bus_volt_mag[k[0]]**2.0 +
                ( - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.cos(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])
                  - self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.sin(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.xfmr_status[k] else 0.0)
            for k in self.xfmr}
        self.xfmr_pow_orig_imag = {
            k:( - (self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k]**2.0 + self.xfmr_adm_mag_imag[k]) * self.bus_volt_mag[k[0]]**2.0 +
                (   self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.cos(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])
                    - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.sin(self.bus_volt_ang[k[0]] - self.bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.xfmr_status[k] else 0.0)
            for k in self.xfmr}
        self.xfmr_pow_dest_real = {
            k:( self.xfmr_adm_real[k] * self.bus_volt_mag[k[1]]**2.0 +
                ( - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.cos(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])
                  - self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.sin(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.xfmr_status[k] else 0.0)
            for k in self.xfmr}
        self.xfmr_pow_dest_imag = {
            k:( - self.xfmr_adm_imag[k] * self.bus_volt_mag[k[1]]**2.0 +
                (   self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.cos(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])
                    - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.sin(self.bus_volt_ang[k[1]] - self.bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])) *
                self.bus_volt_mag[k[0]] * self.bus_volt_mag[k[1]]
                if self.xfmr_status[k] else 0.0)
            for k in self.xfmr}

    def eval_xfmr_pow_viol(self):

        self.xfmr_pow_orig_mag_max_viol = {
            k:max(
                0.0,
                (self.xfmr_pow_orig_real[k]**2.0 +
                 self.xfmr_pow_orig_imag[k]**2.0)**0.5 -
                self.xfmr_pow_mag_max[k])
            for k in self.xfmr}
        self.xfmr_pow_dest_mag_max_viol = {
            k:max(
                0.0,
                (self.xfmr_pow_dest_real[k]**2.0 +
                 self.xfmr_pow_dest_imag[k]**2.0)**0.5 -
                self.xfmr_pow_mag_max[k])
            for k in self.xfmr}

    def eval_bus_swsh_adm_imag_viol(self):

        self.bus_swsh_adm_imag_min_viol = {
            i:max(0.0, self.bus_swsh_adm_imag_min[i] - self.bus_swsh_adm_imag[i])
            for i in self.bus}
        self.bus_swsh_adm_imag_max_viol = {
            i:max(0.0, self.bus_swsh_adm_imag[i] - self.bus_swsh_adm_imag_max[i])
            for i in self.bus}

    def eval_bus_swsh_pow(self):

        self.bus_swsh_pow_imag = {
            i:(-self.bus_swsh_adm_imag[i] * self.bus_volt_mag[i]**2.0)
            for i in self.bus}

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

        self.bus_pow_balance_real_viol = {
            i:abs(
                sum([self.gen_pow_real[k] for k in self.bus_gen[i] if self.gen_status[k]]) -
                sum([self.load_pow_real[k] for k in self.bus_load[i] if self.load_status[k]]) -
                sum([self.fxsh_pow_real[k] for k in self.bus_fxsh[i] if self.fxsh_status[k]]) -
                sum([self.line_pow_orig_real[k] for k in self.bus_line_orig[i] if self.line_status[k]]) -
                sum([self.line_pow_dest_real[k] for k in self.bus_line_dest[i] if self.line_status[k]]) -
                sum([self.xfmr_pow_orig_real[k] for k in self.bus_xfmr_orig[i] if self.xfmr_status[k]]) -
                sum([self.xfmr_pow_dest_real[k] for k in self.bus_xfmr_dest[i] if self.xfmr_status[k]]))
            for i in self.bus}
        self.bus_pow_balance_imag_viol = {
            i:abs(
                sum([self.gen_pow_imag[k] for k in self.bus_gen[i] if self.gen_status[k]]) -
                sum([self.load_pow_imag[k] for k in self.bus_load[i] if self.load_status[k]]) -
                sum([self.fxsh_pow_imag[k] for k in self.bus_fxsh[i] if self.fxsh_status[k]]) -
                self.bus_swsh_pow_imag[i] -
                sum([self.line_pow_orig_imag[k] for k in self.bus_line_orig[i] if self.line_status[k]]) -
                sum([self.line_pow_dest_imag[k] for k in self.bus_line_dest[i] if self.line_status[k]]) -
                sum([self.xfmr_pow_orig_imag[k] for k in self.bus_xfmr_orig[i] if self.xfmr_status[k]]) -
                sum([self.xfmr_pow_dest_imag[k] for k in self.bus_xfmr_dest[i] if self.xfmr_status[k]]))
            for i in self.bus}

    def eval_ctg_bus_volt_viol(self):

        self.ctg_bus_volt_mag_min_viol = {
            i:max(0.0, self.ctg_bus_volt_mag_min[i] - self.ctg_bus_volt_mag[i])
            for i in self.bus}
        self.ctg_bus_volt_mag_max_viol = {
            i:max(0.0, self.ctg_bus_volt_mag[i] - self.ctg_bus_volt_mag_max[i])
            for i in self.bus}

    def eval_ctg_load_pow(self):

        self.ctg_load_pow_real = {
            i:(self.load_const_pow_real[i] if self.load_status[i] else 0.0)
            for i in self.load}
        self.ctg_load_pow_imag = {
            i:(self.load_const_pow_imag[i] if self.load_status[i] else 0.0)
            for i in self.load}

    def eval_ctg_fxsh_pow(self):

        self.ctg_fxsh_pow_real = {
            i:(self.fxsh_adm_real[i] * self.ctg_bus_volt_mag[i[0]]**2.0
               if self.fxsh_status[i] else 0.0)
            for i in self.fxsh}
        self.ctg_fxsh_pow_imag = {
            i:(-self.fxsh_adm_imag[i] * self.ctg_bus_volt_mag[i[0]]**2.0
               if self.fxsh_status[i] else 0.0)
            for i in self.fxsh}

    def eval_ctg_gen_pow_real(self):


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

        if debug:
            if self.ctg_label == k:
                print('pgk (computed): %f' % self.ctg_gen_pow_real[g])

    def eval_ctg_gen_pow_real_viol(self):

        self.ctg_gen_pow_real_min_viol = {
            i:max(0.0, (self.gen_pow_real_min[i] if self.ctg_gen_active[i] else 0.0) - self.ctg_gen_pow_real[i])
            for i in self.gen}
        self.ctg_gen_pow_real_max_viol = {
            i:max(0.0, self.ctg_gen_pow_real[i] - (self.gen_pow_real_max[i] if self.ctg_gen_active[i] else 0.0))
            for i in self.gen}

    def eval_ctg_gen_pow_imag_viol(self):

        self.ctg_gen_pow_imag_min_viol = {
            i:max(0.0, (self.gen_pow_imag_min[i] if self.ctg_gen_active[i] else 0.0) - self.ctg_gen_pow_imag[i])
            for i in self.gen}
        self.ctg_gen_pow_imag_max_viol = {
            i:max(0.0, self.ctg_gen_pow_imag[i] - (self.gen_pow_imag_max[i] if self.ctg_gen_active[i] else 0.0))
            for i in self.gen}

    def eval_ctg_line_pow(self):

        self.ctg_line_pow_orig_real = {
            k:( self.line_adm_real[k] * self.ctg_bus_volt_mag[k[0]]**2.0 +
                ( - self.line_adm_real[k] * math.cos(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]])
                  - self.line_adm_imag[k] * math.sin(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_line_active[k] else 0.0)
            for k in self.line}
        self.ctg_line_pow_orig_imag = {
            k:( - (self.line_adm_imag[k] + 0.5 * self.line_adm_ch_imag[k]) * self.ctg_bus_volt_mag[k[0]]**2.0 +
                (   self.line_adm_imag[k] * math.cos(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]])
                  - self.line_adm_real[k] * math.sin(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_line_active[k] else 0.0)
            for k in self.line}
        self.ctg_line_pow_dest_real = {
            k:( self.line_adm_real[k] * self.ctg_bus_volt_mag[k[1]]**2.0 +
                ( - self.line_adm_real[k] * math.cos(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]])
                  - self.line_adm_imag[k] * math.sin(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_line_active[k] else 0.0)
            for k in self.line}
        self.ctg_line_pow_dest_imag = {
            k:( - (self.line_adm_imag[k] + 0.5 * self.line_adm_ch_imag[k]) * self.ctg_bus_volt_mag[k[1]]**2.0 +
                (   self.line_adm_imag[k] * math.cos(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]])
                  - self.line_adm_real[k] * math.sin(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_line_active[k] else 0.0)
            for k in self.line}

    def eval_ctg_line_curr_viol(self):

        self.ctg_line_curr_orig_mag_max_viol = {
            k:max(
                0.0,
                (self.ctg_line_pow_orig_real[k]**2.0 +
                 self.ctg_line_pow_orig_imag[k]**2.0)**0.5 -
                self.ctg_line_curr_mag_max[k] * self.ctg_bus_volt_mag[k[0]])
            for k in self.line}
        self.ctg_line_curr_dest_mag_max_viol = {
            k:max(
                0.0,
                (self.ctg_line_pow_dest_real[k]**2.0 +
                 self.ctg_line_pow_dest_imag[k]**2.0)**0.5 -
                self.ctg_line_curr_mag_max[k] * self.ctg_bus_volt_mag[k[1]])
            for k in self.line}

    def eval_ctg_xfmr_pow(self):

        self.ctg_xfmr_pow_orig_real = {
            k:( (self.xfmr_adm_real[k] / self.xfmr_tap_mag[k]**2.0 + self.xfmr_adm_mag_real[k]) * self.ctg_bus_volt_mag[k[0]]**2.0 +
                ( - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.cos(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])
                  - self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.sin(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_xfmr_active[k] else 0.0)
            for k in self.xfmr}
        self.ctg_xfmr_pow_orig_imag = {
            k:( - (self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k]**2.0 + self.xfmr_adm_mag_imag[k]) * self.ctg_bus_volt_mag[k[0]]**2.0 +
                (   self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.cos(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])
                    - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.sin(self.ctg_bus_volt_ang[k[0]] - self.ctg_bus_volt_ang[k[1]] - self.xfmr_tap_ang[k])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_xfmr_active[k] else 0.0)
            for k in self.xfmr}
        self.ctg_xfmr_pow_dest_real = {
            k:( self.xfmr_adm_real[k] * self.ctg_bus_volt_mag[k[1]]**2.0 +
                ( - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.cos(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])
                  - self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.sin(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_xfmr_active[k] else 0.0)
            for k in self.xfmr}
        self.ctg_xfmr_pow_dest_imag = {
            k:( - self.xfmr_adm_imag[k] * self.ctg_bus_volt_mag[k[1]]**2.0 +
                (   self.xfmr_adm_imag[k] / self.xfmr_tap_mag[k] * math.cos(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])
                    - self.xfmr_adm_real[k] / self.xfmr_tap_mag[k] * math.sin(self.ctg_bus_volt_ang[k[1]] - self.ctg_bus_volt_ang[k[0]] + self.xfmr_tap_ang[k])) *
                self.ctg_bus_volt_mag[k[0]] * self.ctg_bus_volt_mag[k[1]]
                if self.ctg_xfmr_active[k] else 0.0)
            for k in self.xfmr}

    def eval_ctg_xfmr_pow_viol(self):

        self.ctg_xfmr_pow_orig_mag_max_viol = {
            k:max(
                0.0,
                (self.ctg_xfmr_pow_orig_real[k]**2.0 +
                 self.ctg_xfmr_pow_orig_imag[k]**2.0)**0.5 -
                self.ctg_xfmr_pow_mag_max[k])
            for k in self.xfmr}
        self.ctg_xfmr_pow_dest_mag_max_viol = {
            k:max(
                0.0,
                (self.ctg_xfmr_pow_dest_real[k]**2.0 +
                 self.ctg_xfmr_pow_dest_imag[k]**2.0)**0.5 -
                self.ctg_xfmr_pow_mag_max[k])
            for k in self.xfmr}

    def eval_ctg_bus_swsh_adm_imag_viol(self):

        self.ctg_bus_swsh_adm_imag_max_viol = {
            i:max(0.0, self.ctg_bus_swsh_adm_imag[i] - self.bus_swsh_adm_imag_max[i])
            for i in self.bus}
        self.ctg_bus_swsh_adm_imag_min_viol = {
            i:max(0.0, self.bus_swsh_adm_imag_min[i] - self.ctg_bus_swsh_adm_imag[i])
            for i in self.bus}

    def eval_ctg_bus_swsh_pow(self):

        self.ctg_bus_swsh_pow_imag = {
            i:(-self.ctg_bus_swsh_adm_imag[i] * self.ctg_bus_volt_mag[i]**2.0)
            for i in self.bus}

    def eval_ctg_bus_pow_balance(self):

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
        #''' original
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
        #'''
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

    def eval_ctg_gen_pvpq_viol(self):

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

    def eval_penalty(self):

        self.penalty = base_case_penalty_weight * (
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        list(self.line_curr_orig_mag_max_viol.values()),
                        list(self.line_curr_dest_mag_max_viol.values())),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        list(self.xfmr_pow_orig_mag_max_viol.values()),
                        list(self.xfmr_pow_dest_mag_max_viol.values())),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.bus_pow_balance_real_viol.values(),
                    self.penalty_block_pow_real_max,
                    self.penalty_block_pow_real_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.bus_pow_balance_imag_viol.values(),
                    self.penalty_block_pow_imag_max,
                    self.penalty_block_pow_imag_coeff)))

    def eval_ctg_penalty(self):

        self.ctg_penalty = (1 - base_case_penalty_weight) / max(1.0, float(len(self.ctg))) * (
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        list(self.ctg_line_curr_orig_mag_max_viol.values()),
                        list(self.ctg_line_curr_dest_mag_max_viol.values())),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    np.maximum(
                        list(self.ctg_xfmr_pow_orig_mag_max_viol.values()),
                        list(self.ctg_xfmr_pow_dest_mag_max_viol.values())),
                    self.penalty_block_pow_abs_max,
                    self.penalty_block_pow_abs_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.ctg_bus_pow_balance_real_viol.values(),
                    self.penalty_block_pow_real_max,
                    self.penalty_block_pow_real_coeff)) +
            np.sum(
                eval_piecewise_linear_penalty(
                    self.ctg_bus_pow_balance_imag_viol.values(),
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
        self.infeas = 1 if self.max_nonobj_viol > 0.0 else 0

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
            self.ctg_max_gen_pow_real_max_viol[1],
            self.ctg_max_gen_pow_real_min_viol[1],
            self.ctg_max_gen_pow_imag_max_viol[1],
            self.ctg_max_gen_pow_imag_min_viol[1],
            self.ctg_max_gen_pvpq1_viol[1],
            self.ctg_max_gen_pvpq2_viol[1])
        self.ctg_infeas = 1 if self.ctg_max_nonobj_viol > 0.0 else 0
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

        def extra_max(d):
            if len(d) == 0:
                return (None, 0.0)
            else:
                k = max(d.keys(), key=(lambda k: d[k]))
                return (k, d[k])
        
        self.max_bus_volt_mag_max_viol = extra_max(self.bus_volt_mag_max_viol)
        self.max_bus_volt_mag_min_viol = extra_max(self.bus_volt_mag_min_viol)
        self.max_bus_swsh_adm_imag_max_viol = extra_max(self.bus_swsh_adm_imag_max_viol)
        self.max_bus_swsh_adm_imag_min_viol = extra_max(self.bus_swsh_adm_imag_min_viol)
        self.max_bus_pow_balance_real_viol = extra_max(self.bus_pow_balance_real_viol)
        self.max_bus_pow_balance_imag_viol = extra_max(self.bus_pow_balance_imag_viol)
        self.max_gen_pow_real_max_viol = extra_max(self.gen_pow_real_max_viol)
        self.max_gen_pow_real_min_viol = extra_max(self.gen_pow_real_min_viol)
        self.max_gen_pow_imag_max_viol = extra_max(self.gen_pow_imag_max_viol)
        self.max_gen_pow_imag_min_viol = extra_max(self.gen_pow_imag_min_viol)
        self.max_line_curr_orig_mag_max_viol = extra_max(self.line_curr_orig_mag_max_viol)
        self.max_line_curr_dest_mag_max_viol = extra_max(self.line_curr_dest_mag_max_viol)
        self.max_xfmr_pow_orig_mag_max_viol = extra_max(self.xfmr_pow_orig_mag_max_viol)
        self.max_xfmr_pow_dest_mag_max_viol = extra_max(self.xfmr_pow_dest_mag_max_viol)

    def compute_ctg_detail(self):

        def extra_max(d):
            if len(d) == 0:
                return (None, 0.0)
            else:
                k = max(d.keys(), key=(lambda k: d[k]))
                return (k, d[k])
        
        self.ctg_max_bus_volt_mag_max_viol = extra_max(self.ctg_bus_volt_mag_max_viol)
        self.ctg_max_bus_volt_mag_min_viol = extra_max(self.ctg_bus_volt_mag_min_viol)
        self.ctg_max_bus_swsh_adm_imag_max_viol = extra_max(self.ctg_bus_swsh_adm_imag_max_viol)
        self.ctg_max_bus_swsh_adm_imag_min_viol = extra_max(self.ctg_bus_swsh_adm_imag_min_viol)
        self.ctg_max_bus_pow_balance_real_viol = extra_max(self.ctg_bus_pow_balance_real_viol)
        self.ctg_max_bus_pow_balance_imag_viol = extra_max(self.ctg_bus_pow_balance_imag_viol)
        self.ctg_max_gen_pow_real_max_viol = extra_max(self.ctg_gen_pow_real_max_viol)
        self.ctg_max_gen_pow_real_min_viol = extra_max(self.ctg_gen_pow_real_min_viol)
        self.ctg_max_gen_pow_imag_max_viol = extra_max(self.ctg_gen_pow_imag_max_viol)
        self.ctg_max_gen_pow_imag_min_viol = extra_max(self.ctg_gen_pow_imag_min_viol)
        self.ctg_max_gen_pvpq1_viol = extra_max(self.ctg_gen_pvpq1_viol)
        self.ctg_max_gen_pvpq2_viol = extra_max(self.ctg_gen_pvpq2_viol)
        self.ctg_max_line_curr_orig_mag_max_viol = extra_max(self.ctg_line_curr_orig_mag_max_viol)
        self.ctg_max_line_curr_dest_mag_max_viol = extra_max(self.ctg_line_curr_dest_mag_max_viol)
        self.ctg_max_xfmr_pow_orig_mag_max_viol = extra_max(self.ctg_xfmr_pow_orig_mag_max_viol)
        self.ctg_max_xfmr_pow_dest_mag_max_viol = extra_max(self.ctg_xfmr_pow_dest_mag_max_viol)

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

    with open(file_name, 'r') as in_file:
        lines = in_file.readlines()
    sections = solution_read_sections_from_lines(lines, section_start_line_str, has_headers)
    return sections

def solution_read_sections_from_lines(lines, section_start_line_str=None, has_headers=None):

    if section_start_line_str is None:
        section_start_line_str = '--'
    if has_headers is None:
        has_headers = True
    num_lines = len(lines)
    delimiter_str = ","
    quote_str = "'"
    skip_initial_space = True
    lines = csv.reader(
        lines,
        delimiter=delimiter_str,
        quotechar=quote_str,
        skipinitialspace=skip_initial_space)
    lines = [[t.strip() for t in r] for r in lines]
    lines = [r for r in lines if len(r) > 0]
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

    def read(self, file_name):

        bus = 0
        gen = 1
        section_start_line_str = '--'
        has_headers = True
        sections = solution_read_sections(file_name, section_start_line_str, has_headers)
        self.read_bus_rows(sections[bus])
        self.read_gen_rows(sections[gen])
            
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
    
def run(raw_name, rop_name, con_name, inl_name, sol1_name, sol2_name, summary_name, detail_name):

    # start timer
    start_time_all = time.time()

    # read the data files
    p = data.Data()

    # read raw
    start_time = time.time()
    p.raw.read(raw_name)
    time_elapsed = time.time() - start_time
    print("read raw time: %u" % time_elapsed)

    # read rop
    start_time = time.time()
    p.rop.read(rop_name)
    time_elapsed = time.time() - start_time
    print("read rop time: %u" % time_elapsed)

    # read con
    start_time = time.time()
    p.con.read(con_name)
    time_elapsed = time.time() - start_time
    print("read con time: %u" % time_elapsed)

    # read inl
    start_time = time.time()
    p.inl.read(inl_name)
    time_elapsed = time.time() - start_time
    print("read inl time: %u" % time_elapsed)

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

    # set up solution objects
    s1 = Solution1()
    s2 = Solution2()

    # read sol1
    start_time = time.time()
    s1.read(sol1_name)
    time_elapsed = time.time() - start_time
    print("read sol_base time: %u" % time_elapsed)

    # set up evaluation
    e = Evaluation()

    # set eval data
    start_time = time.time()
    e.set_data(p)
    time_elapsed = time.time() - start_time
    print("set data time: %u" % time_elapsed)

    # set penalty params (later read from case.prm)
    start_time = time.time()
    e.set_params()
    time_elapsed = time.time() - start_time
    print("set params time: %u" % time_elapsed)

    # set eval sol1
    start_time = time.time()
    e.set_solution1(s1)
    time_elapsed = time.time() - start_time
    print("set sol1 time: %u" % time_elapsed)

    # evaluate base
    start_time = time.time()
    e.eval_base()
    time_elapsed = time.time() - start_time
    print("eval base time: %u" % time_elapsed)
    
    # write base summary
    start_time = time.time()
    e.write_header(detail_name)
    e.write_base(detail_name)
    time_elapsed = time.time() - start_time
    print("write base time: %u" % time_elapsed)

    # get ctg structure in sol
    # do not forget to check that every contingency is found in the sol file
    start_time = time.time()
    ctg_num_lines = get_ctg_num_lines(sol2_name)
    num_ctgs = len(ctg_num_lines)
    ctgs_reported = []
    with open(sol2_name) as sol2_file:
        for k in range(num_ctgs):
            lines = list(islice(sol2_file, ctg_num_lines[k]))
            if not lines:
                break # error
            s2.read_from_lines(lines)
            e.set_solution2(s2)
            ctgs_reported.append(e.ctg_label)
            e.set_ctg_data()
            e.eval_ctg()
            e.write_ctg(detail_name)
    num_ctgs_reported = len(ctgs_reported)
    num_ctgs_reported_unique = len(set(ctgs_reported))
    if (num_ctgs_reported != num_ctgs_reported_unique or
        num_ctgs_reported != len(e.ctg)):
        e.infeas = 1
        print("infeas, problem with contingency list in sol file")
        print("num ctg: %u" % len(e.ctg))
        print("num ctg reported: %u" % num_ctgs_reported)
        print("num ctg reported unique: %u" % num_ctgs_reported_unique)
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

    return (e.obj, e.cost, e.obj - e.cost, e.max_obj_viol, e.max_nonobj_viol, e.infeas)
