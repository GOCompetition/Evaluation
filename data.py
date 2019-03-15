"""Data structures and read/write methods for input and output data file formats

Author: Jesse Holzer, jesse.holzer@pnnl.gov

Date: 2018-04-05

"""
# data.py
# module for input and output data
# including data structures
# and read and write functions

import csv
import os
import sys
import math
import traceback
#from io import StringIO
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

# init_defaults_in_unused_field = True # do this anyway - it is not too big
read_unused_fields = True
write_defaults_in_unused_fields = False
write_values_in_unused_fields = True
gen_cost_dx_margin = 1.0e-6 # ensure that consecutive x points differ by at least this amount
gen_cost_ddydx_margin = 1.0e-6 # ensure that consecutive slopes differ by at least this amount
gen_cost_x_bounds_margin = 1.0e-6 # ensure that the pgen lower and upper bounds are covered by at least this amount

def alert(alert_dict):
    print(alert_dict)

def parse_token(token, val_type, default=None):
    val = None
    if len(token) > 0:
        val = val_type(token)
    elif default is not None:
        val = val_type(default)
    else:
        try:
            print('required field missing data, token: %s, val_type: %s' % (token, val_type))
            raise Exception('empty field not allowed')
        except Exception as e:
            traceback.print_exc()
            raise e
        #raise Exception('empty field not allowed')
    return val

def pad_row(row, new_row_len):

    try:
        if len(row) != new_row_len:
            if len(row) < new_row_len:
                print('missing field, row:')
                print(row)
                raise Exception('missing field not allowed')
            elif len(row) > new_row_len:
                row = remove_end_of_line_comment_from_row(row, '/')
                if len(row) > new_row_len:
                    print('extra field, row:')
                    print(row)
                    raise Exception('extra field not allowed')
        else:
            row = remove_end_of_line_comment_from_row(row, '/')
    except Exception as e:
        traceback.print_exc()
        raise e
    return row
    '''
    row_len = len(row)
    row_len_diff = new_row_len - row_len
    row_new = row
    if row_len_diff > 0:
        row_new = row + row_len_diff * ['']
    return row_new
    '''

def check_row_missing_fields(row, row_len_expected):

    try:
        if len(row) < row_len_expected:
            print('missing field, row:')
            print(row)
            raise Exception('missing field not allowed')
    except Exception as e:
        traceback.print_exc()
        raise e

def remove_end_of_line_comment_from_row(row, end_of_line_str):

    index = [r.find(end_of_line_str) for r in row]
    len_row = len(row)
    entries_with_end_of_line_strs = [i for i in range(len_row) if index[i] > -1]
    num_entries_with_end_of_line_strs = len(entries_with_end_of_line_strs)
    if num_entries_with_end_of_line_strs > 0:
        first_entry_with_end_of_line_str = min(entries_with_end_of_line_strs)
        len_row_new = first_entry_with_end_of_line_str + 1
        row_new = [row[i] for i in range(len_row_new)]
        row_new[len_row_new - 1] = remove_end_of_line_comment(row_new[len_row_new - 1], end_of_line_str)
    else:
        row_new = [r for r in row]
    return row_new

def remove_end_of_line_comment(token, end_of_line_str):
    
    token_new = token
    index = token_new.find(end_of_line_str)
    if index > -1:
        token_new = token_new[0:index]
    return token_new

class Data:
    '''In physical units, i.e. data convention, i.e. input and output data files'''

    def __init__(self):

        self.raw = Raw()
        self.rop = Rop()
        self.inl = Inl()
        self.con = Con()

    def read(self, raw_name, rop_name, inl_name, con_name):

        self.raw.read(raw_name)
        self.rop.read(rop_name)
        self.inl.read(inl_name)
        self.con.read(con_name)

    def write(self, raw_name, rop_name, inl_name, con_name):

        self.raw.write(raw_name)
        self.rop.write(rop_name)
        self.inl.write(inl_name)
        self.con.write(con_name)

    def check(self):
        
        self.raw.check()
        self.rop.check()
        self.inl.check()
        self.con.check()
        self.check_gen_cost_x_min_margin()
        self.check_gen_cost_x_max_margin()

    def check_gen_cost_x_min_margin(self):

        for g in self.raw.get_generators():
            g_i = g.i
            g_id = g.id
            g_pb = g.pb
            gdr = self.rop.generator_dispatch_records[(g_i, g_id)]
            apdr = self.rop.active_power_dispatch_records[gdr.dsptbl]
            plcf = self.rop.piecewise_linear_cost_functions[apdr.ctbl]
            plcf.check_x_min_margin(g_pb)

    def check_gen_cost_x_max_margin(self):

        for g in self.raw.get_generators():
            g_i = g.i
            g_id = g.id
            g_pt = g.pt
            gdr = self.rop.generator_dispatch_records[(g_i, g_id)]
            apdr = self.rop.active_power_dispatch_records[gdr.dsptbl]
            plcf = self.rop.piecewise_linear_cost_functions[apdr.ctbl]
            plcf.check_x_max_margin(g_pt)

class Raw:
    '''In physical units, i.e. data convention, i.e. input and output data files'''

    def __init__(self):

        self.case_identification = CaseIdentification()
        self.buses = {}
        self.loads = {}
        self.fixed_shunts = {}
        self.generators = {}
        self.nontransformer_branches = {}
        self.transformers = {}
        self.areas = {}
        self.switched_shunts = {}

    def check(self):

        pass

    def set_areas_from_buses(self):
        
        area_i_set = set([b.area for b in self.buses.values()])
        def area_set_i(area, i):
            area.i = i
            return area
        self.areas = {i:area_set_i(Area(), i) for i in area_i_set}

    def get_buses(self):

        return sorted(self.buses.values(), key=(lambda r: r.i))

    def get_loads(self):

        return sorted(self.loads.values(), key=(lambda r: (r.i, r.id)))

    def get_fixed_shunts(self):

        return sorted(self.fixed_shunts.values(), key=(lambda r: (r.i, r.id)))

    def get_generators(self):

        return sorted(self.generators.values(), key=(lambda r: (r.i, r.id)))

    def get_nontransformer_branches(self):

        return sorted(self.nontransformer_branches.values(), key=(lambda r: (r.i, r.j, r.ckt)))

    def get_transformers(self):

        return sorted(self.transformers.values(), key=(lambda r: (r.i, r.j, r.k, r.ckt)))

    def get_areas(self):

        return sorted(self.areas.values(), key=(lambda r: r.i))
        
    def get_switched_shunts(self):

        return sorted(self.switched_shunts.values(), key=(lambda r: r.i))

    def construct_case_identification_section(self):

        #out_str = StringIO.StringIO()
        out_str = StringIO()
        #writer = csv.writer(out_str, quotechar="'", quoting=csv.QUOTE_NONNUMERIC)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [self.case_identification.ic, self.case_identification.sbase,
                 self.case_identification.rev, self.case_identification.xfrrat,
                 self.case_identification.nxfrat, self.case_identification.basfrq],
                ["%s" % self.case_identification.record_2], # no quotes here - typical RAW file
                ["%s" % self.case_identification.record_3]] # no quotes here - typical RAW file
                #["'%s'" % self.case_identification.record_2],
                #["'%s'" % self.case_identification.record_3]]
                #["''"],
                #["''"]]
        elif write_defaults_in_unused_fields:
            rows = [
                [0, self.case_identification.sbase, 33, 0, 1, 60.0],
                ["''"],
                ["''"]]
        else:
            rows = [
                [None, self.case_identification.sbase, 33, None, None, None],
                ["''"],
                ["''"]]
        writer.writerows(rows)
        return out_str.getvalue()

    def construct_bus_section(self):
        # note use quote_none and quote the strings manually
        # values of None then are written as empty fields, which is what we want

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        
        if write_values_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.name, r.baskv, r.ide, r.area, r.zone, r.owner, r.vm, r.va, r.nvhi, r.nvlo, r.evhi, r.evlo]
                #for r in self.buses.values()] # might as well sort
                for r in self.get_buses()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, "'            '", 0.0, 1, r.area, 1, 1, r.vm, r.va, r.nvhi, r.nvlo, r.evhi, r.evlo]
                for r in self.get_buses()]
        else:
            rows = [
                [r.i, None, None, None, r.area, None, None, r.vm, r.va, r.nvhi, r.nvlo, r.evhi, r.evlo]
                for r in self.get_buses()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF BUS DATA BEGIN LOAD DATA']]) # no comma allowed without escape character
        #out_str.write('0 / END OF BUS DATA, BEGIN LOAD DATA\n')
        return out_str.getvalue()

    def construct_load_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str,  quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.id, r.status, r.area, r.zone, r.pl, r.ql, r.ip, r.iq, r.yp, r.yq, r.owner, r.scale, r.intrpt]
                for r in self.get_loads()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.id, r.status, self.buses[r.i].area, 1, r.pl, r.ql, 0.0, 0.0, 0.0, 0.0, 1, 1, 0]
                for r in self.get_loads()]
        else:
            rows = [
                [r.i, "'%s'" % r.id, r.status, None, None, r.pl, r.ql, None, None, None, None, None, None, None]
                for r in self.get_loads()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF LOAD DATA BEGIN FIXED SHUNT DATA']])
        return out_str.getvalue()

    def construct_fixed_shunt_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.id, r.status, r.gl, r.bl]
                for r in self.get_fixed_shunts()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.id, r.status, r.gl, r.bl]
                for r in self.get_fixed_shunts()]
        else:
            rows = [
                [r.i, "'%s'" % r.id, r.status, r.gl, r.bl]
                for r in self.get_fixed_shunts()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF FIXED SHUNT DATA BEGIN GENERATOR DATA']])
        return out_str.getvalue()

    def construct_generator_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.id, r.pg, r.qg, r.qt, r.qb,
                 r.vs, r.ireg, r.mbase, r.zr, r.zx, r.rt, r.xt, r.gtap,
                 r.stat, r.rmpct, r.pt, r.pb, r.o1, r.f1, r.o2,
                 r.f2, r.o3, r.f3, r.o4, r.f4, r.wmod, r.wpf]
                for r in self.get_generators()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, "'%s'" % r.id, r.pg, r.qg, r.qt, r.qb,
                 1.0, 0, self.case_identification.sbase, 0.0, 1.0, 0.0, 0.0, 1.0,
                 r.stat, 100.0, r.pt, r.pb, 1, 1.0, 0,
                 1.0, 0, 1.0, 0, 1.0, 0, 1.0]
                for r in self.get_generators()]
        else:
            rows = [
                [r.i, "'%s'" % r.id, r.pg, r.qg, r.qt, r.qb,
                 None, None, None, None, None, None, None, None,
                 r.stat, None, r.pt, r.pb, None, None, None,
                 None, None, None, None, None, None, None]
                for r in self.get_generators()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF GENERATOR DATA BEGIN BRANCH DATA']])
        return out_str.getvalue()

    def construct_nontransformer_branch_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, r.j, "'%s'" % r.ckt, r.r, r.x, r.b, r.ratea,
                 r.rateb, r.ratec, r.gi, r.bi, r.gj, r.bj, r.st, r.met, r.len,
                 r.o1, r.f1, r.o2, r.f2, r.o3, r.f3, r.o4, r.f4 ]
                for r in self.get_nontransformer_branches()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, r.j, "'%s'" % r.ckt, r.r, r.x, r.b, r.ratea,
                 0.0, r.ratec, 0.0, 0.0, 0.0, 0.0, r.st, 1, 0.0,
                 1, 1.0, 0, 1.0, 0, 1.0, 0, 1.0 ]
                for r in self.get_nontransformer_branches()]
        else:
            rows = [
                [r.i, r.j, "'%s'" % r.ckt, r.r, r.x, r.b, r.ratea,
                 None, r.ratec, None, None, None, None, r.st, None, None,
                 None, None, None, None, None, None, None, None ]
                for r in self.get_nontransformer_branches()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF BRANCH DATA BEGIN TRANSFORMER DATA']])
        return out_str.getvalue()

    def construct_transformer_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                rr
                for r in self.get_transformers()
                for rr in [
                        [r.i, r.j, r.k, "'%s'" % r.ckt, r.cw, r.cz, r.cm,
                         r.mag1, r.mag2, r.nmetr, "'%s'" % r.name, r.stat, r.o1, r.f1,
                         r.o2, r.f2, r.o3, r.f3, r.o4, r.f4, "'%s'" % r.vecgrp],
                        [r.r12, r.x12, r.sbase12],
                        [r.windv1, r.nomv1, r.ang1, r.rata1, r.ratb1, r.ratc1,
                         r.cod1, r.cont1, r.rma1, r.rmi1, r.vma1, r.vmi1, r.ntp1, r.tab1,
                         r.cr1, r.cx1, r.cnxa1],
                        [r.windv2, r.nomv2]]]
        elif write_defaults_in_unused_fields:
            rows = [
                rr
                for r in self.get_transformers()
                for rr in [
                        [r.i, r.j, 0, "'%s'" % r.ckt, 1, 1, 1,
                         r.mag1, r.mag2, 2, "'            '", r.stat, 1, 1.0,
                         0, 1.0, 0, 1.0, 0, 1.0, "'            '"],
                        [r.r12, r.x12, self.case_identification.sbase],
                        [r.windv1, 0.0, r.ang1, r.rata1, 0.0, r.ratc1,
                         0, 0, 1.1, 0.9, 1.1, 0.9, 33, 0,
                         0.0, 0.0, 0.0],
                        [r.windv2, 0.0]]]
        else:
            rows = [
                rr
                for r in self.get_transformers()
                for rr in [
                        [r.i, r.j, 0, "'%s'" % r.ckt, None, None, None,
                         r.mag1, r.mag2, None, None, r.stat, None, None,
                         None, None, None, None, None, None, None],
                        [r.r12, r.x12, None],
                        [r.windv1, None, r.ang1, r.rata1, None, r.ratc1,
                         None, None, None, None, None, None, None, None,
                         None, None, None],
                        [r.windv2, None]]]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF TRANSFORMER DATA BEGIN AREA DATA']])
        return out_str.getvalue()

    def construct_area_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, r.isw, r.pdes, r.ptol, "'%s'" % r.arname]
                for r in self.get_areas()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, 0, 0.0, 10.0, "'            '"]
                for r in self.get_areas()]
        else:
            rows = [
                [r.i, None, None, None, None]
                for r in self.get_areas()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF AREA DATA BEGIN TWO-TERMINAL DC DATA']])
        return out_str.getvalue()

    def construct_two_terminal_dc_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF TWO-TERMINAL DC DATA BEGIN VSC DC LINE DATA']])
        return out_str.getvalue()

    def construct_vsc_dc_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF VSC DC LINE DATA BEGIN IMPEDANCE CORRECTION DATA']])
        return out_str.getvalue()

    def construct_transformer_impedance_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF IMPEDANCE CORRECTION DATA BEGIN MULTI-TERMINAL DC DATA']])
        return out_str.getvalue()

    def construct_multi_terminal_dc_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF MULTI-TERMINAL DC DATA BEGIN MULTI-SECTION LINE DATA']])
        return out_str.getvalue()

    def construct_multi_section_line_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF MULTI-SECTION LINE DATA BEGIN ZONE DATA']])
        return out_str.getvalue()

    def construct_zone_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF ZONE DATA BEGIN INTER-AREA TRANSFER DATA']])
        return out_str.getvalue()

    def construct_interarea_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF INTER-AREA TRANSFER DATA BEGIN OWNER DATA']])
        return out_str.getvalue()

    def construct_owner_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF OWNER DATA BEGIN FACTS DEVICE DATA']])
        return out_str.getvalue()

    def construct_facts_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF FACTS DEVICE DATA BEGIN SWITCHED SHUNT DATA']])
        return out_str.getvalue()

    def construct_switched_shunt_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, r.modsw, r.adjm, r.stat, r.vswhi, r.vswlo, r.swrem, r.rmpct, "'%s'" % r.rmidnt,
                 r.binit, r.n1, r.b1, r.n2, r.b2, r.n3, r.b3, r.n4, r.b4,
                 r.n5, r.b5, r.n6, r.b6, r.n7, r.b7, r.n8, r.b8]
                for r in self.get_switched_shunts()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, 1, 0, r.stat, 1.0, 1.0, 0, 100.0, "'            '",
                 r.binit, r.n1, r.b1, r.n2, r.b2, r.n3, r.b3, r.n4, r.b4,
                 r.n5, r.b5, r.n6, r.b6, r.n7, r.b7, r.n8, r.b8]
                for r in self.get_switched_shunts()]
        else:
            rows = [
                [r.i, None, None, r.stat, None, None, None, None, None,
                 r.binit, r.n1, r.b1, r.n2, r.b2, r.n3, r.b3, r.n4, r.b4,
                 r.n5, r.b5, r.n6, r.b6, r.n7, r.b7, r.n8, r.b8]
                for r in self.get_switched_shunts()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF SWITCHED SHUNT DATA BEGIN GNE DATA']])
        return out_str.getvalue()

    def construct_gne_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF GNE DATA BEGIN INDUCTION MACHINE DATA']])
        return out_str.getvalue()

    def construct_induction_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF INDUCTION MACHINE DATA']])
        return out_str.getvalue()

    def construct_q_record(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        rows = [['Q']]
        writer.writerows(rows)
        return out_str.getvalue()

    def write(self, file_name):
        '''write a RAW file'''

        with open(file_name, 'w') as out_file:
            out_file.write(self.construct_case_identification_section())
            out_file.write(self.construct_bus_section())
            out_file.write(self.construct_load_section())
            out_file.write(self.construct_fixed_shunt_section())
            out_file.write(self.construct_generator_section())
            out_file.write(self.construct_nontransformer_branch_section())
            out_file.write(self.construct_transformer_section())
            out_file.write(self.construct_area_section())
            out_file.write(self.construct_two_terminal_dc_section())
            out_file.write(self.construct_vsc_dc_section())
            out_file.write(self.construct_transformer_impedance_section())
            out_file.write(self.construct_multi_terminal_dc_section())
            out_file.write(self.construct_multi_section_line_section())
            out_file.write(self.construct_zone_section())
            out_file.write(self.construct_interarea_section())
            out_file.write(self.construct_owner_section())
            out_file.write(self.construct_facts_section())
            out_file.write(self.construct_switched_shunt_section())
            out_file.write(self.construct_gne_section())
            out_file.write(self.construct_induction_section())
            out_file.write(self.construct_q_record())

    def switched_shunts_combine_blocks_steps(self):

        for r in self.switched_shunts.values():
            b_min = 0.0
            b_max = 0.0
            b1 = float(r.n1) * r.b1
            b2 = float(r.n2) * r.b2
            b3 = float(r.n3) * r.b3
            b4 = float(r.n4) * r.b4
            b5 = float(r.n5) * r.b5
            b6 = float(r.n6) * r.b6
            b7 = float(r.n7) * r.b7
            b8 = float(r.n8) * r.b8
            for b in [b1, b2, b3, b4, b5, b6, b7, b8]:
                if b > 0.0:
                    b_max += b
                elif b < 0.0:
                    b_min += b
                else:
                    break
            r.n1 = 0
            r.b1 = 0.0
            r.n2 = 0
            r.b2 = 0.0
            r.n3 = 0
            r.b3 = 0.0
            r.n4 = 0
            r.b4 = 0.0
            r.n5 = 0
            r.b5 = 0.0
            r.n6 = 0
            r.b6 = 0.0
            r.n7 = 0
            r.b7 = 0.0
            r.n8 = 0
            r.b8 = 0.0
            if b_max > 0.0:
                r.n1 = 1
                r.b1 = b_max
                if b_min < 0.0:
                    r.n2 = 1
                    r.b2 = b_min
            elif b_min < 0.0:
                r.n1 = 1
                r.b1 = b_min
        
    def set_operating_point_to_offline_solution(self):

        for r in self.buses.values():
            r.vm = 1.0
            r.va = 0.0
        for r in self.generators.values():
            r.pg = 0.0
            r.qg = 0.0
        for r in self.switched_shunts.values():
            r.binit = 0.0
        
    def read(self, file_name):

        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        delimiter_str = ","
        quote_str = "'"
        skip_initial_space = True
        rows = csv.reader(
            lines,
            delimiter=delimiter_str,
            quotechar=quote_str,
            skipinitialspace=skip_initial_space)
        rows = [[t.strip() for t in r] for r in rows]
        self.read_from_rows(rows)
        self.set_areas_from_buses()
        
    def row_is_file_end(self, row):

        is_file_end = False
        if len(row) == 0:
            is_file_end = True
        if row[0][:1] in {'','q','Q'}:
            is_file_end = True
        return is_file_end
    
    def row_is_section_end(self, row):

        is_section_end = False
        if row[0][:1] == '0':
            is_section_end = True
        return is_section_end
        
    def read_from_rows(self, rows):

        row_num = 0
        cid_rows = rows[row_num:(row_num + 3)]
        self.case_identification.read_from_rows(rows)
        row_num += 2
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            bus = Bus()
            bus.read_from_row(row)
            self.buses[bus.i] = bus
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            load = Load()
            load.read_from_row(row)
            self.loads[(load.i, load.id)] = load
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            fixed_shunt = FixedShunt()
            fixed_shunt.read_from_row(row)
            self.fixed_shunts[(fixed_shunt.i, fixed_shunt.id)] = fixed_shunt
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            generator = Generator()
            generator.read_from_row(row)
            self.generators[(generator.i, generator.id)] = generator
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            nontransformer_branch = NontransformerBranch()
            nontransformer_branch.read_from_row(row)
            self.nontransformer_branches[(
                nontransformer_branch.i,
                nontransformer_branch.j,
                nontransformer_branch.ckt)] = nontransformer_branch
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            transformer = Transformer()
            num_rows = transformer.get_num_rows_from_row(row)
            rows_temp = rows[
                row_num:(row_num + num_rows)]
            transformer.read_from_rows(rows_temp)
            self.transformers[(
                transformer.i,
                transformer.j,
                #transformer.k,
                0,
                transformer.ckt)] = transformer
            row_num += (num_rows - 1)
        while True: # areas - for now just make a set of areas based on bus info
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            area = Area()
            area.read_from_row(row)
            self.areas[area.i] = area
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True: # zone
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            switched_shunt = SwitchedShunt()
            switched_shunt.read_from_row(row)
            self.switched_shunts[switched_shunt.i] = switched_shunt

class Rop:
    '''In physical units, i.e. data convention, i.e. input and output data files'''

    def __init__(self):

        self.generator_dispatch_records = {}
        self.active_power_dispatch_records = {}
        self.piecewise_linear_cost_functions = {}
        
    def check(self):

        for r in self.get_piecewise_linear_cost_functions():
            r.check_at_least_two_points()
            r.check_dx_margin()
            r.check_ddydx_margin()

    def trancostfuncfrom_phase_0(self,rawdata):
        ds=self.active_power_dispatch_records.get((4, '1'))

        for r in rawdata.generators.values():
            ds=self.active_power_dispatch_records.get((r.i,r.id))
            #update piecewise linear info
            self.active_power_dispatch_records.get((r.i,r.id)).npairs=10
            self.active_power_dispatch_records.get((r.i,r.id)).costzero=self.active_power_dispatch_records.get((r.i,r.id)).constc
            for i in range(self.active_power_dispatch_records.get((r.i,r.id)).npairs):
                # the points will be power followed by cost, ie[power0 cost0 power 1 cost1 ....]
                self.active_power_dispatch_records.get((r.i,r.id)).points.append(r.pb+i*(r.pt-r.pb)/(self.active_power_dispatch_records.get((r.i,r.id)).npairs-1))
                self.active_power_dispatch_records.get((r.i,r.id)).points.append(self.active_power_dispatch_records.get((r.i,r.id)).constc+self.active_power_dispatch_records.get((r.i,r.id)).linearc*(r.pb+i*(r.pt-r.pb)/(self.active_power_dispatch_records.get((r.i,r.id)).npairs-1))+self.active_power_dispatch_records.get((r.i,r.id)).quadraticc*pow(r.pb+i*(r.pt-r.pb)/(self.active_power_dispatch_records.get((r.i,r.id)).npairs-1),2))
            
    def read_from_phase_0(self, file_name):
        
        '''takes the generator.csv file as input'''
        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        del lines[0]
        delimiter_str = ","
        quote_str = "'"
        skip_initial_space = True
        rows = csv.reader(
            lines,
            delimiter=delimiter_str,
            quotechar=quote_str,
            skipinitialspace=skip_initial_space)
        #[[t.strip() for t in r] for r in rows]
        for r in rows:
            indi=1
            gen_dispatch = QuadraticCostFunctions()
            gen_dispatch.read_from_csv(r)
            
            gen_dispatch.read_from_csv_quadraticinfo(r)
            while (indi<4):
                r2=rows.next()
                gen_dispatch.read_from_csv_quadraticinfo(r2)
                indi=indi+1
                #print([gen_dispatch.bus,gen_dispatch.genid, gen_dispatch.constc,gen_dispatch.linearc,gen_dispatch.quadraticc])
            self.active_power_dispatch_records[gen_dispatch.bus,gen_dispatch.genid] = gen_dispatch
        #print([gen_dispatch.bus,gen_dispatch.genid, gen_dispatch.constc])
        #ds=self.active_power_dispatch_records.get((4, '1'))

    def get_generator_dispatch_records(self):

        return sorted(self.generator_dispatch_records.values(), key=(lambda r: (r.bus, r.genid)))

    def get_active_power_dispatch_records(self):

        return sorted(self.active_power_dispatch_records.values(), key=(lambda r: r.tbl))

    def get_piecewise_linear_cost_functions(self):

        return sorted(self.piecewise_linear_cost_functions.values(), key=(lambda r: r.ltbl))

    def construct_data_modification_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF MODIFICATION CODE BEGIN BUS VOLTAGE CONSTRAINT DATA']])
        return out_str.getvalue()

    def construct_bus_voltage_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF BUS VOLTAGE CONSTRAINT DATA BEGIN ADJUSTABLE BUS SHUNT DATA']])
        return out_str.getvalue()

    def construct_adjustable_bus_shunt_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF ADJUSTABLE BUS SHUNT DATA BEGIN BUS LOAD DATA']])
        return out_str.getvalue()

    def construct_bus_load_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF BUS LOAD DATA BEGIN ADJUSTABLE BUS LOAD TABLES']])
        return out_str.getvalue()

    def construct_adjustable_bus_load_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF ADJUSTABLE BUS LOAD TABLES BEGIN GENERATOR DISPATCH DATA']])
        return out_str.getvalue()

    def construct_generator_dispatch_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.bus, "'%s'" % r.genid, r.disp, r.dsptbl]
                for r in self.get_generator_dispatch_records()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.bus, "'%s'" % r.genid, 1.0, r.dsptbl]
                for r in self.get_generator_dispatch_records()]
        else:
            rows = [
                [r.bus, "'%s'" % r.genid, None, r.dsptbl]
                for r in self.get_generator_dispatch_records()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF GENERATOR DISPATCH DATA BEGIN ACTIVE POWER DISPATCH TABLES']])
        return out_str.getvalue()

    def construct_active_power_dispatch_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.tbl, r.pmax, r.pmin, r.fuelcost, r.ctyp, r.status, r.ctbl]
                for r in self.get_active_power_dispatch_records()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.tbl, 9999.0, -9999.0, 1.0, 1, 1, r.ctbl]
                for r in self.get_active_power_dispatch_records()]
        else:
            rows = [
                [r.tbl, None, None, None, None, None, r.ctbl]
                for r in self.get_active_power_dispatch_records()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF ACTIVE POWER DISPATCH TABLES BEGIN GENERATION RESERVE DATA']])
        return out_str.getvalue()

    def construct_generator_reserve_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF GENERATION RESERVE DATA BEGIN GENERATION REACTIVE CAPABILITY DATA']])
        return out_str.getvalue()

    def construct_reactive_capability_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF GENERATION REACTIVE CAPABILITY DATA BEGIN ADJUSTABLE BRANCH REACTANCE DATA']])
        return out_str.getvalue()

    def construct_branch_reactance_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF ADJUSTABLE BRANCH REACTANCE DATA BEGIN PIECE-WISE LINEAR COST TABLES']])
        return out_str.getvalue()

    def construct_piecewise_linear_cost_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                row
                for r in self.get_piecewise_linear_cost_functions()
                for row in (
                        [[r.ltbl, "'%s'" % r.label, r.npairs]] +
                        [[p.x, p.y] for p in r.points])]
        elif write_defaults_in_unused_fields:
            rows = [
                row
                for r in self.get_piecewise_linear_cost_functions()
                for row in (
                        [[r.ltbl, "''", r.npairs]] +
                        [[p.x, p.y] for p in r.points])]
        else:
            rows = [
                row
                for r in self.get_piecewise_linear_cost_functions()
                for row in (
                        [[r.ltbl, None, r.npairs]] +
                        [[p.x, p.y] for p in r.points])]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF PIECE-WISE LINEAR COST TABLES BEGIN PIECEWISE QUADRATIC COST TABLES']])
        return out_str.getvalue()

    def construct_piecewise_quadratic_cost_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF PIECE-WISE QUADRATIC COST TABLES BEGIN POLYNOMIAL AND EXPONENTIAL COST TABLES']])
        return out_str.getvalue()

    def construct_polynomial_exponential_cost_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF POLYNOMIAL COST TABLES BEGIN PERIOD RESERVE DATA']])
        return out_str.getvalue()

    def construct_period_reserve_constraint_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF PERIOD RESERVE DATA BEGIN BRANCH FLOW CONSTRAINT DATA']])
        return out_str.getvalue()

    def construct_branch_flow_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF BRANCH FLOW CONSTRAINT DATA BEGIN INTERFACE FLOW DATA']])
        return out_str.getvalue()

    def construct_interface_flow_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF INTERFACE FLOW DATA BEGIN LINEAR CONSTRAINT EQUATION DEPENDENCY DATA']])
        return out_str.getvalue()

    def construct_linear_constraint_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF LINEAR CONSTRAINT EQUATION DEPENDENCY DATA']])
        return out_str.getvalue()
        #0 / End of Linear Constraint Equation Dependency data, begin 2-terminal dc Line Constraint data
        #0 / End of 2-terminal dc Line Constraint data

    def construct_q_record(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['Q']])
        return out_str.getvalue()

    def write(self, file_name):
        '''write an ROP file'''

        with open(file_name, 'w') as out_file:

            out_file.write(self.construct_data_modification_section())
            out_file.write(self.construct_bus_voltage_section())
            out_file.write(self.construct_adjustable_bus_shunt_section())
            out_file.write(self.construct_bus_load_section())
            out_file.write(self.construct_adjustable_bus_load_section())
            out_file.write(self.construct_generator_dispatch_section())
            out_file.write(self.construct_active_power_dispatch_section())
            out_file.write(self.construct_generator_reserve_section())
            out_file.write(self.construct_reactive_capability_section())
            out_file.write(self.construct_branch_reactance_section())
            out_file.write(self.construct_piecewise_linear_cost_section())
            out_file.write(self.construct_piecewise_quadratic_cost_section())
            out_file.write(self.construct_polynomial_exponential_cost_section())
            out_file.write(self.construct_period_reserve_constraint_section())
            out_file.write(self.construct_branch_flow_section())
            out_file.write(self.construct_interface_flow_section())
            out_file.write(self.construct_linear_constraint_section())
            out_file.write(self.construct_q_record()) # no q record in sample ROP file

    def read(self, file_name):

        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        delimiter_str = ","
        quote_str = "'"
        skip_initial_space = True
        rows = csv.reader(
            lines,
            delimiter=delimiter_str,
            quotechar=quote_str,
            skipinitialspace=skip_initial_space)
        rows = [[t.strip() for t in r] for r in rows]
        self.read_from_rows(rows)
        
    def row_is_file_end(self, row):

        is_file_end = False
        if len(row) == 0:
            is_file_end = True
        if row[0][:1] in {'','q','Q'}:
            is_file_end = True
        return is_file_end
    
    def row_is_section_end(self, row):

        is_section_end = False
        if row[0][:1] == '0':
            is_section_end = True
        return is_section_end
        
    def read_from_rows(self, rows):

        row_num = -1
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            generator_dispatch_record = GeneratorDispatchRecord()
            generator_dispatch_record.read_from_row(row)
            self.generator_dispatch_records[(
                generator_dispatch_record.bus,
                generator_dispatch_record.genid)] = generator_dispatch_record
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            active_power_dispatch_record = ActivePowerDispatchRecord()
            active_power_dispatch_record.read_from_row(row)
            self.active_power_dispatch_records[
                active_power_dispatch_record.tbl] = (
                    active_power_dispatch_record)
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            piecewise_linear_cost_function = PiecewiseLinearCostFunction()
            num_rows = piecewise_linear_cost_function.get_num_rows_from_row(row)
            rows_temp = rows[
                row_num:(row_num + num_rows)]
            piecewise_linear_cost_function.read_from_rows(rows_temp)
            self.piecewise_linear_cost_functions[
                piecewise_linear_cost_function.ltbl] = (
                piecewise_linear_cost_function)
            row_num += (num_rows - 1)

class Inl:
    '''In physical units, i.e. data convention, i.e. input and output data files'''

    def __init__(self):

        self.generator_inl_records = {}

    def check(self):

        pass

    # TODO
    def read_from_phase_0(self, file_name):
        '''takes the generator.csv file as input'''

    def write(self, file_name):
        '''write an INL file'''

        with open(file_name, 'w') as out_file:
            out_file.write(self.construct_data_section())

    def get_generator_inl_records(self):

        return sorted(self.generator_inl_records.values(), key=(lambda r: (r.i, r.id)))

    def construct_data_section(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        if write_values_in_unused_fields:
            rows = [
                [r.i, r.id, r.h, r.pmax, r.pmin, r.r, r.d]
                for r in self.get_generator_inl_records()]
        elif write_defaults_in_unused_fields:
            rows = [
                [r.i, r.id, 4.0, 0.0, 0.0, r.r, 0.0]
                for r in self.get_generator_inl_records()]
        else:
            rows = [
                [r.i, r.id, "", "", "", r.r, ""]
                for r in self.get_generator_inl_records()]
        writer.writerows(rows)
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE)
        writer.writerows([['0 / END OF DATA']])
        return out_str.getvalue()

    def read(self, file_name):

        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        delimiter_str = ","
        quote_str = "'"
        skip_initial_space = True
        rows = csv.reader(
            lines,
            delimiter=delimiter_str,
            quotechar=quote_str,
            skipinitialspace=skip_initial_space)
        rows = [[t.strip() for t in r] for r in rows]
        self.read_from_rows(rows)
        
    def row_is_file_end(self, row):

        is_file_end = False
        if len(row) == 0:
            is_file_end = True
        if row[0][:1] in {'','q','Q'}:
            is_file_end = True
        return is_file_end
    
    def row_is_section_end(self, row):

        is_section_end = False
        if row[0][:1] == '0':
            is_section_end = True
        return is_section_end
        
    def read_from_rows(self, rows):

        row_num = -1
        while True:
            row_num += 1
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            if self.row_is_section_end(row):
                break
            generator_inl_record = GeneratorInlRecord()
            generator_inl_record.read_from_row(row)
            self.generator_inl_records[(
                generator_inl_record.i,
                generator_inl_record.id)] = generator_inl_record
        
class Con:
    '''In physical units, i.e. data convention, i.e. input and output data files'''

    def __init__(self):

        self.contingencies = {}

    def check(self):

        pass

    def read_from_phase_0(self, file_name):
        '''takes the contingency.csv file as input'''
        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        delimiter_str = " "
        quote_str = "'"
        skip_initial_space = True
        del lines[0]
        rows = csv.reader(
            lines,
            delimiter=delimiter_str,
            quotechar=quote_str,
            skipinitialspace=skip_initial_space)
        rows = [[t.strip() for t in r] for r in rows]
        quote_str = "'"
        contingency = Contingency()
        #there is no contingency label for continency.csv
        for r in rows:
            tmprow=r[0].split(',')
            if tmprow[1].upper()=='B' or tmprow[1].upper()=='T':
                contingency.label ="LINE-"+tmprow[2]+"-"+tmprow[3]+"-"+tmprow[4]
                branch_out_event = BranchOutEvent()
                branch_out_event.read_from_csv(tmprow)
                contingency.branch_out_events.append(branch_out_event)
                self.contingencies[contingency.label] = branch_out_event
            elif tmprow[1].upper()=='G':
                contingency.label = "GEN-"+tmprow[2]+"-"+tmprow[3]
                generator_out_event = GeneratorOutEvent()
                generator_out_event.read_from_csv(tmprow)
                contingency.generator_out_events.append(generator_out_event)
                self.contingency.generator_out_event.read_from_csv(tmprow)

    def get_contingencies(self):

        return sorted(self.contingencies.values(), key=(lambda r: r.label))

    def construct_data_records(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE, delimiter=' ')
        rows = [
            row
            for r in self.get_contingencies()
            for row in r.construct_record_rows()]
        writer.writerows(rows)
        return out_str.getvalue()

    def construct_end_record(self):

        out_str = StringIO()
        writer = csv.writer(out_str, quoting=csv.QUOTE_NONE, delimiter=' ')
        rows = [['END']]
        writer.writerows(rows)
        return out_str.getvalue()        

    def write(self, file_name):
        '''write a CON file'''

        with open(file_name, 'w') as out_file:
            out_file.write(self.construct_data_records())
            out_file.write(self.construct_end_record())

    def read(self, file_name):

        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        try:
            for l in lines:
                if l.find("'") > -1 or l.find('"') > -1:
                    print('no quotes allowed, line:')
                    print(l)
                    raise Exception('no quotes allowed in CON')
        except Exception as e:
            traceback.print_exc()
            raise e
        delimiter_str = " "
        #quote_str = "'"
        skip_initial_space = True
        rows = csv.reader(
            lines,
            delimiter=delimiter_str,
            #quotechar=quote_str,
            skipinitialspace=skip_initial_space,
            quoting=csv.QUOTE_NONE) # QUOTE_NONE
        rows = [[t.strip() for t in r] for r in rows]
        self.read_from_rows(rows)
        
    def row_is_file_end(self, row):

        is_file_end = False
        if len(row) == 0:
            is_file_end = True
        if row[0][:1] in {'','q','Q'}:
            is_file_end = True
        return is_file_end
    
    #def row_is_section_end(self, row):
    #
    #    is_section_end = False
    #    if row[0][:1] == '0':
    #        is_section_end = True
    #    return is_section_end

    def is_contingency_start(self, row):

        return (row[0].upper() == 'CONTINGENCY')

    def is_end(self, row):

        return (row[0].upper() == 'END')

    def is_branch_out_event(self, row):

        #return (
        #    row[0].upper() in {'DISCONNECT', 'OPEN', 'TRIP'} and
        #    row[1].upper() in {'BRANCH', 'LINE'})
        return (row[0] == 'OPEN' and row[1] == 'BRANCH')

    def is_three_winding(self, row):

        #print(row)
        if len(row) < 9:
            return False
        elif row[8].upper() == 'TO':
            return True
        else:
            return False

    def is_generator_out_event(self, row):

        #return(
        #    row[0].upper() == 'REMOVE' and
        #    row[1].upper() in {'UNIT', 'MACHINE'})
        return(row[0] == 'REMOVE' and row[1] == 'UNIT')
        
    def read_from_rows(self, rows):

        row_num = -1
        in_contingency = False
        while True:
            row_num += 1
            #if row_num >= len(rows): # in case the data provider failed to put an end file line
            #    return
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            #if self.row_is_section_end(row):
            #    break
            elif self.is_contingency_start(row):
                in_contingency = True
                contingency = Contingency()
                contingency.label = row[1]
            elif self.is_end(row):
                if in_contingency:
                    self.contingencies[contingency.label] = contingency
                    in_contingency = False
                else:
                    break
            elif self.is_branch_out_event(row):
                branch_out_event = BranchOutEvent()
                if self.is_three_winding(row):
                    branch_out_event.read_three_winding_from_row(row)
                else:
                    branch_out_event.read_from_row(row)
                contingency.branch_out_events.append(branch_out_event)
            elif self.is_generator_out_event(row):
                generator_out_event = GeneratorOutEvent()
                generator_out_event.read_from_row(row)
                contingency.generator_out_events.append(generator_out_event)
            else:
                try:
                    print('format error in CON file row:')
                    print(row)
                    raise Exception('format error in CON file')
                except Exception as e:
                    traceback.print_exc()
                    raise e

class CaseIdentification:

    def __init__(self):

        self.ic = 0
        self.sbase = 100.0
        self.rev = 33
        self.xfrrat = 0
        self.nxfrat = 1
        self.basfrq = 60.0
        self.record_2 = 'GRID OPTIMIZATION COMPETITION'
        self.record_3 = 'INPUT DATA FILES ARE RAW ROP INL CON'

    def read_record_1_from_row(self, row):

        row = pad_row(row, 6)
        #row[5] = remove_end_of_line_comment(row[5], '/')
        self.sbase = parse_token(row[1], float, default=None)
        if read_unused_fields:
            self.ic = parse_token(row[0], int, 0)
            self.rev = parse_token(row[2], int, 33)
            self.xfrrat = parse_token(row[3], int, 0)
            self.nxfrat = parse_token(row[4], int, 1)
            self.basfrq = parse_token(row[5], float, 60.0) # need to remove end of line comment

    def read_from_rows(self, rows):

        self.read_record_1_from_row(rows[0])
        #self.record_2 = '' # not preserving these at this point
        #self.record_3 = '' # do that later

class Bus:

    def __init__(self):

        self.i = None # no default allowed - we want this to throw an error
        self.name = 12*' '
        self.baskv = 0.0
        self.ide = 1
        self.area = 1
        self.zone = 1
        self.owner = 1
        self.vm = 1.0
        self.va = 0.0
        self.nvhi = 1.1
        self.nvlo = 0.9
        self.evhi = 1.1
        self.evlo = 0.9

    def read_from_row(self, row):

        row = pad_row(row, 13)
        self.i = parse_token(row[0], int, default=None)
        self.area = parse_token(row[4], int, default=None)
        self.vm = parse_token(row[7], float, default=None)
        self.va = parse_token(row[8], float, default=None)
        self.nvhi = parse_token(row[9], float, default=None)
        self.nvlo = parse_token(row[10], float, default=None)
        self.evhi = parse_token(row[11], float, default=None)
        self.evlo = parse_token(row[12], float, default=None)
        if read_unused_fields:
            self.name = parse_token(row[1], str, 12*' ')
            self.baskv = parse_token(row[2], float, 0.0)
            self.ide = parse_token(row[3], int, 1)
            self.zone = parse_token(row[5], int, 1)
            self.owner = parse_token(row[6], int, 1)
    
class Load:

    def __init__(self):

        self.i = None # no default allowed - should be an error
        self.id = '1'
        self.status = 1
        self.area = 1 # default is area of bus self.i, but this is not available yet
        self.zone = 1
        self.pl = 0.0
        self.ql = 0.0
        self.ip = 0.0
        self.iq = 0.0
        self.yp = 0.0
        self.yq = 0.0
        self.owner = 1
        self.scale = 1
        self.intrpt = 0

    def read_from_row(self, row):

        row = pad_row(row, 14)
        self.i = parse_token(row[0], int, default=None)
        self.id = parse_token(row[1], str, default=None)
        self.status = parse_token(row[2], int, default=None)
        self.pl = parse_token(row[5], float, default=None)
        self.ql = parse_token(row[6], float, default=None)
        if read_unused_fields:
            self.area = parse_token(row[3], int, 1)
            self.zone = parse_token(row[4], int, 1)
            self.ip = parse_token(row[7], float, 0.0)
            self.iq = parse_token(row[8], float, 0.0)
            self.yp = parse_token(row[9], float, 0.0)
            self.yq = parse_token(row[10], float, 0.0)
            self.owner = parse_token(row[11], int, 1)
            self.scale = parse_token(row[12], int, 1)
            self.intrpt = parse_token(row[13], int, 0)

class FixedShunt:

    def __init__(self):

        self.i = None # no default allowed
        self.id = '1'
        self.status = 1
        self.gl = 0.0
        self.bl = 0.0

    def read_from_row(self, row):

        row = pad_row(row, 5)
        self.i = parse_token(row[0], int, default=None)
        self.id = parse_token(row[1], str, default=None)
        self.status = parse_token(row[2], int, default=None)
        self.gl = parse_token(row[3], float, default=None)
        self.bl = parse_token(row[4], float, default=None)
        if read_unused_fields:
            pass

class Generator:

    def __init__(self):
        self.i = None # no default allowed
        self.id = '1'
        self.pg = 0.0
        self.qg = 0.0
        self.qt = 9999.0
        self.qb = -9999.0
        self.vs = 1.0
        self.ireg = 0
        self.mbase = 100.0 # need to take default value for this from larger Raw class
        self.zr = 0.0
        self.zx = 1.0
        self.rt = 0.0
        self.xt = 0.0
        self.gtap = 1.0
        self.stat = 1
        self.rmpct = 100.0
        self.pt = 9999.0
        self.pb = -9999.0
        self.o1 = 1
        self.f1 = 1.0
        self.o2 = 0
        self.f2 = 1.0
        self.o3 = 0
        self.f3 = 1.0
        self.o4 = 0
        self.f4 = 1.0
        self.wmod = 0
        self.wpf = 1.0

    def read_from_row(self, row):

        row = pad_row(row, 28)
        self.i = parse_token(row[0], int, default=None)
        self.id = parse_token(row[1], str, default=None)
        self.pg = parse_token(row[2], float, default=None)
        self.qg = parse_token(row[3], float, default=None)
        self.qt = parse_token(row[4], float, default=None)
        self.qb = parse_token(row[5], float, default=None)
        self.stat = parse_token(row[14], int, default=None)
        self.pt = parse_token(row[16], float, default=None)
        self.pb = parse_token(row[17], float, default=None)
        if read_unused_fields:
            self.vs = parse_token(row[6], float, 1.0)
            self.ireg = parse_token(row[7], int, 0)
            self.mbase = parse_token(row[8], float, 100.0)
            self.zr = parse_token(row[9], float, 0.0)
            self.zx = parse_token(row[10], float, 1.0)
            self.rt = parse_token(row[11], float, 0.0)
            self.xt = parse_token(row[12], float, 0.0)
            self.gtap = parse_token(row[13], float, 1.0)
            self.rmpct = parse_token(row[15], float, 100.0)
            self.o1 = parse_token(row[18], int, 1)
            self.f1 = parse_token(row[19], float, 1.0)
            self.o2 = parse_token(row[20], int, 0)
            self.f2 = parse_token(row[21], float, 1.0)
            self.o3 = parse_token(row[22], int, 0)
            self.f3 = parse_token(row[23], float, 1.0)
            self.o4 = parse_token(row[24], int, 0)
            self.f4 = parse_token(row[25], float, 1.0)
            self.wmod = parse_token(row[26], int, 0)
            self.wpf = parse_token(row[27], float, 1.0)

class NontransformerBranch:

    def __init__(self):

        self.i = None # no default
        self.j = None # no default
        self.ckt = '1'
        self.r = None # no default
        self.x = None # no default
        self.b = 0.0
        self.ratea = 0.0
        self.rateb = 0.0
        self.ratec = 0.0
        self.gi = 0.0
        self.bi = 0.0
        self.gj = 0.0
        self.bj = 0.0
        self.st = 1
        self.met = 1
        self.len = 0.0
        self.o1 = 1
        self.f1 = 1.0
        self.o2 = 0
        self.f2 = 1.0
        self.o3 = 0
        self.f3 = 1.0
        self.o4 = 0
        self.f4 = 1.0

    def read_from_row(self, row):

        row = pad_row(row, 24)
        self.i = parse_token(row[0], int, default=None)
        self.j = parse_token(row[1], int, default=None)
        self.ckt = parse_token(row[2], str, default=None)
        self.r = parse_token(row[3], float, default=None)
        self.x = parse_token(row[4], float, default=None)
        self.b = parse_token(row[5], float, default=None)
        self.ratea = parse_token(row[6], float, default=None)
        self.ratec = parse_token(row[8], float, default=None)
        self.st = parse_token(row[13], int, default=None)
        if read_unused_fields:
            self.rateb = parse_token(row[7], float, 0.0)
            self.gi = parse_token(row[9], float, 0.0)
            self.bi = parse_token(row[10], float, 0.0)
            self.gj = parse_token(row[11], float, 0.0)
            self.bj = parse_token(row[12], float, 0.0)
            self.met = parse_token(row[14], int, 1)
            self.len = parse_token(row[15], float, 0.0)
            self.o1 = parse_token(row[16], int, 1)
            self.f1 = parse_token(row[17], float, 1.0)
            self.o2 = parse_token(row[18], int, 0)
            self.f2 = parse_token(row[19], float, 1.0)
            self.o3 = parse_token(row[20], int, 0)
            self.f3 = parse_token(row[21], float, 1.0)
            self.o4 = parse_token(row[22], int, 0)
            self.f4 = parse_token(row[23], float, 1.0)

class Transformer:

    def __init__(self):

        self.i = None # no default
        self.j = None # no default
        self.k = 0
        self.ckt = '1'
        self.cw = 1
        self.cz = 1
        self.cm = 1
        self.mag1 = 0.0
        self.mag2 = 0.0
        self.nmetr = 2
        self.name = 12*' '
        self.stat = 1
        self.o1 = 1
        self.f1 = 1.0
        self.o2 = 0
        self.f2 = 1.0
        self.o3 = 0
        self.f3 = 1.0
        self.o4 = 0
        self.f4 = 1.0
        self.vecgrp = 12*' '
        self.r12 = 0.0
        self.x12 = None # no default allowed
        self.sbase12 = 100.0
        self.windv1 = 1.0
        self.nomv1 = 0.0
        self.ang1 = 0.0
        self.rata1 = 0.0
        self.ratb1 = 0.0
        self.ratc1 = 0.0
        self.cod1 = 0
        self.cont1 = 0
        self.rma1 = 1.1
        self.rmi1 = 0.9
        self.vma1 = 1.1
        self.vmi1 = 0.9
        self.ntp1 = 33
        self.tab1 = 0
        self.cr1 = 0.0
        self.cx1 = 0.0
        self.cnxa1 = 0.0
        self.windv2 = 1.0
        self.nomv2 = 0.0

    @property
    def num_windings(self):

        num_windings = 0
        if self.k is None:
            num_windings = 0
        elif self.k == 0:
            num_windings = 2
        else:
            num_windings = 3
        return num_windings
    
    def get_num_rows_from_row(self, row):

        num_rows = 0
        k = parse_token(row[2], int, 0)
        if k == 0:
            num_rows = 4
        else:
            num_rows = 5
        return num_rows

    def read_from_rows(self, rows):

        full_rows = self.pad_rows(rows)
        row = self.flatten_rows(full_rows)
        try:
            self.read_from_row(row)
        except Exception as e:
            print("row:")
            print(row)
            raise e
        
    def pad_rows(self, rows):

        return rows
        '''
        rows_new = rows
        if len(rows_new) == 4:
            rows_new.append([])
        rows_len = [len(r) for r in rows_new]
        rows_len_new = [21, 11, 17, 17, 17]
        rows_len_increase = [rows_len_new[i] - rows_len[i] for i in range(5)]
        # check no negatives in increase
        rows_new = [rows_new[i] + rows_len_increase[i]*[''] for i in range(5)]
        return rows_new
        '''

    def flatten_rows(self, rows):

        row = [t for r in rows for t in r]
        return row
    
    def read_from_row(self, row):

        # general (3- or 2-winding, 5- or 4-row)
        '''
        self.i = parse_token(row[0], int, '')
        self.j = parse_token(row[1], int, '')
        self.k = parse_token(row[2], int, 0)
        self.ckt = parse_token(row[3], str, '1')
        self.cw = parse_token(row[4], int, 1)
        self.cz = parse_token(row[5], int, 1)
        self.cm = parse_token(row[6], int, 1)
        self.mag1 = parse_token(row[7], float, 0.0)
        self.mag2 = parse_token(row[8], float, 0.0)
        self.nmetr = parse_token(row[9], int, 2)
        self.name = parse_token(row[10], str, 12*' ')
        self.stat = parse_token(row[11], int, 1)
        self.o1 = parse_token(row[12], int, 0)
        self.f1 = parse_token(row[13], float, 1.0)
        self.o2 = parse_token(row[14], int, 0)
        self.f2 = parse_token(row[15], float, 1.0)
        self.o3 = parse_token(row[16], int, 0)
        self.f3 = parse_token(row[17], float, 1.0)
        self.o4 = parse_token(row[18], int, 0)
        self.f4 = parse_token(row[19], float, 1.0)
        self.vecgrp = parse_token(row[20], str, 12*' ')
        self.r12 = parse_token(row[21], float, 0.0)
        self.x12 = parse_token(row[22], float, 0.0)
        self.sbase12 = parse_token(row[23], float, 0.0)
        self.r23 = parse_token(row[24], float, 0.0)
        self.x23 = parse_token(row[25], float, 0.0)
        self.sbase23 = parse_token(row[26], float, 0.0)
        self.r31 = parse_token(row[27], float, 0.0)
        self.x31 = parse_token(row[28], float, 0.0)
        self.sbase31 = parse_token(row[29], float, 0.0)
        self.vmstar = parse_token(row[30], float, 1.0)
        self.anstar = parse_token(row[31], float, 0.0)
        self.windv1 = parse_token(row[32], float, 1.0)
        self.nomv1 = parse_token(row[33], float, 0.0)
        self.ang1 = parse_token(row[34], float, 0.0)
        self.rata1 = parse_token(row[35], float, 0.0)
        self.ratb1 = parse_token(row[36], float, 0.0)
        self.ratc1 = parse_token(row[37], float, 0.0)
        self.cod1 = parse_token(row[38], int, 0)
        self.cont1 = parse_token(row[39], int, 0)
        self.rma1 = parse_token(row[40], float, 1.1)
        self.rmi1 = parse_token(row[41], float, 0.9)
        self.vma1 = parse_token(row[42], float, 1.1)
        self.vmi1 = parse_token(row[43], float, 0.9)
        self.ntp1 = parse_token(row[44], int, 33)
        self.tab1 = parse_token(row[45], int, 0)
        self.cr1 = parse_token(row[46], float, 0.0)
        self.cx1 = parse_token(row[47], float, 0.0)
        self.cnxa1 = parse_token(row[48], float, 0.0)
        self.windv2 = parse_token(row[49], float, 1.0)
        self.nomv2 = parse_token(row[50], float, 0.0)
        self.ang2 = parse_token(row[51], float, 0.0)
        self.rata2 = parse_token(row[52], float, 0.0)
        self.ratb2 = parse_token(row[53], float, 0.0)
        self.ratc2 = parse_token(row[54], float, 0.0)
        self.cod2 = parse_token(row[55], int, 0)
        self.cont2 = parse_token(row[56], int, 0)
        self.rma2 = parse_token(row[57], float, 1.1)
        self.rmi2 = parse_token(row[58], float, 0.9)
        self.vma2 = parse_token(row[59], float, 1.1)
        self.vmi2 = parse_token(row[60], float, 0.9)
        self.ntp2 = parse_token(row[61], int, 33)
        self.tab2 = parse_token(row[62], int, 0)
        self.cr2 = parse_token(row[63], float, 0.0)
        self.cx2 = parse_token(row[64], float, 0.0)
        self.cnxa2 = parse_token(row[65], float, 0.0)
        self.windv3 = parse_token(row[66], float, 1.0)
        self.nomv3 = parse_token(row[67], float, 0.0)
        self.ang3 = parse_token(row[68], float, 0.0)
        self.rata3 = parse_token(row[69], float, 0.0)
        self.ratb3 = parse_token(row[70], float, 0.0)
        self.ratc3 = parse_token(row[71], float, 0.0)
        self.cod3 = parse_token(row[72], int, 0)
        self.cont3 = parse_token(row[73], int, 0)
        self.rma3 = parse_token(row[74], float, 1.1)
        self.rmi3 = parse_token(row[75], float, 0.9)
        self.vma3 = parse_token(row[76], float, 1.1)
        self.vmi3 = parse_token(row[77], float, 0.9)
        self.ntp3 = parse_token(row[78], int, 33)
        self.tab3 = parse_token(row[79], int, 0)
        self.cr3 = parse_token(row[80], float, 0.0)
        self.cx3 = parse_token(row[81], float, 0.0)
        self.cnxa3 = parse_token(row[82], float, 0.0)
        '''
        
        # just 2-winding, 4-row
        try:
            if len(row) != 43:
                if len(row) < 43:
                    raise Exception('missing field not allowed')
                elif len(row) > 43:
                    row = remove_end_of_line_comment_from_row(row, '/')
                    if len(row) > new_row_len:
                        raise Exception('extra field not allowed')
        except Exception as e:
            traceback.print_exc()
            raise e
        self.i = parse_token(row[0], int, default=None)
        self.j = parse_token(row[1], int, default=None)
        self.ckt = parse_token(row[3], str, default=None)
        self.mag1 = parse_token(row[7], float, default=None)
        self.mag2 = parse_token(row[8], float, default=None)
        self.stat = parse_token(row[11], int, default=None)
        self.r12 = parse_token(row[21], float, default=None)
        self.x12 = parse_token(row[22], float, default=None)
        self.windv1 = parse_token(row[24], float, default=None)
        self.ang1 = parse_token(row[26], float, default=None)
        self.rata1 = parse_token(row[27], float, default=None)
        self.ratc1 = parse_token(row[29], float, default=None)
        self.windv2 = parse_token(row[41], float, default=None)
        if read_unused_fields:
            self.k = parse_token(row[2], int, 0)
            self.cw = parse_token(row[4], int, 1)
            self.cz = parse_token(row[5], int, 1)
            self.cm = parse_token(row[6], int, 1)
            self.nmetr = parse_token(row[9], int, 2)
            self.name = parse_token(row[10], str, 12*' ')
            self.o1 = parse_token(row[12], int, 1)
            self.f1 = parse_token(row[13], float, 1.0)
            self.o2 = parse_token(row[14], int, 0)
            self.f2 = parse_token(row[15], float, 1.0)
            self.o3 = parse_token(row[16], int, 0)
            self.f3 = parse_token(row[17], float, 1.0)
            self.o4 = parse_token(row[18], int, 0)
            self.f4 = parse_token(row[19], float, 1.0)
            self.vecgrp = parse_token(row[20], str, 12*' ')
            self.sbase12 = parse_token(row[23], float, 0.0)
            self.nomv1 = parse_token(row[25], float, 0.0)
            self.ratb1 = parse_token(row[28], float, 0.0)
            self.cod1 = parse_token(row[30], int, 0)
            self.cont1 = parse_token(row[31], int, 0)
            self.rma1 = parse_token(row[32], float, 1.1)
            self.rmi1 = parse_token(row[33], float, 0.9)
            self.vma1 = parse_token(row[34], float, 1.1)
            self.vmi1 = parse_token(row[35], float, 0.9)
            self.ntp1 = parse_token(row[36], int, 33)
            self.tab1 = parse_token(row[37], int, 0)
            self.cr1 = parse_token(row[38], float, 0.0)
            self.cx1 = parse_token(row[39], float, 0.0)
            self.cnxa1 = parse_token(row[40], float, 0.0)
            self.nomv2 = parse_token(row[42], float, 0.0)

class Area:

    def __init__(self):

        self.i = None # no default
        self.isw = 0
        self.pdes = 0.0
        self.ptol = 10.0
        self.arname = 12*' '

    def read_from_row(self, row):

        row = pad_row(row, 5)
        self.i = parse_token(row[0], int, default=None)
        if read_unused_fields:
            self.isw = parse_token(row[1], int, 0)
            self.pdes = parse_token(row[2], float, 0.0)
            self.ptol = parse_token(row[3], float, 10.0)
            self.arname = parse_token(row[4], str, 12*' ')

class Zone:

    def __init__(self):

        self.i = None # no default
        self.zoname = 12*' '
        
    def read_from_row(self, row):

        row = pad_row(row, 2)
        self.i = parse_token(row[0], int, default=None)
        if read_unused_fields:
            self.zoname = parse_token(row[1], str, 12*' ')

class SwitchedShunt:

    def __init__(self):

        self.i = None # no default
        self.modsw = 1
        self.adjm = 0
        self.stat = 1
        self.vswhi = 1.0
        self.vswlo = 1.0
        self.swrem = 0
        self.rmpct = 100.0
        self.rmidnt = 12*' '
        self.binit = 0.0
        self.n1 = 0
        self.b1 = 0.0
        self.n2 = 0
        self.b2 = 0.0
        self.n3 = 0
        self.b3 = 0.0
        self.n4 = 0
        self.b4 = 0.0
        self.n5 = 0
        self.b5 = 0.0
        self.n6 = 0
        self.b6 = 0.0
        self.n7 = 0
        self.b7 = 0.0
        self.n8 = 0
        self.b8 = 0.0

    def read_from_row(self, row):

        row = pad_row(row, 26)
        self.i = parse_token(row[0], int, default=None)
        self.stat = parse_token(row[3], int, default=None)
        self.binit = parse_token(row[9], float, default=None)
        self.n1 = parse_token(row[10], int, default=None)
        self.b1 = parse_token(row[11], float, default=None)
        self.n2 = parse_token(row[12], int, default=None)
        self.b2 = parse_token(row[13], float, default=None)
        self.n3 = parse_token(row[14], int, default=None)
        self.b3 = parse_token(row[15], float, default=None)
        self.n4 = parse_token(row[16], int, default=None)
        self.b4 = parse_token(row[17], float, default=None)
        self.n5 = parse_token(row[18], int, default=None)
        self.b5 = parse_token(row[19], float, default=None)
        self.n6 = parse_token(row[20], int, default=None)
        self.b6 = parse_token(row[21], float, default=None)
        self.n7 = parse_token(row[22], int, default=None)
        self.b7 = parse_token(row[23], float, default=None)
        self.n8 = parse_token(row[24], int, default=None)
        self.b8 = parse_token(row[25], float, default=None)
        if read_unused_fields:
            self.modsw = parse_token(row[1], int, 1)
            self.adjm = parse_token(row[2], int, 0)
            self.vswhi = parse_token(row[4], float, 1.0)
            self.vswlo = parse_token(row[5], float, 1.0)
            self.swrem = parse_token(row[6], int, 0)
            self.rmpct = parse_token(row[7], float, 100.0)
            self.rmidnt = parse_token(row[8], str, 12*' ')
        
class GeneratorDispatchRecord:

    def __init__(self):

        self.bus = None # no default allowed
        self.genid = None # no default allowed
        self.disp = 1.0
        self.dsptbl = None # no default allowed

    def read_from_row(self, row):

        row = pad_row(row, 4)
        self.bus = parse_token(row[0], int, default=None)
        self.genid = parse_token(row[1], str, default=None).strip()
        self.dsptbl = parse_token(row[3], int, default=None)
        if read_unused_fields:
            self.disp = parse_token(row[2], float, 1.0)

    def read_from_csv(self, row):
        self.bus = parse_token(row[0], int, default=None)
        self.genid = parse_token(row[1], str, default=None).strip()
        
class ActivePowerDispatchRecord:

    def __init__(self):

        self.tbl = None # no default allowed
        self.pmax = 9999.0
        self.pmin = -9999.0
        self.fuelcost = 1.0
        self.ctyp = 1
        self.status = 1
        self.ctbl = None # no default allowed

    def read_from_row(self, row):

        row = pad_row(row, 7)
        self.tbl = parse_token(row[0], int, default=None)
        self.ctbl = parse_token(row[6], int, default=None)
        if read_unused_fields:
            self.pmax = parse_token(row[1], float, 9999.0)
            self.pmin = parse_token(row[2], float, -9999.0)
            self.fuelcost = parse_token(row[3], float, 1.0)
            self.ctyp = parse_token(row[4], int, 1)
            self.status = parse_token(row[5], int, 1)

class PiecewiseLinearCostFunction():

    def __init__(self):

        self.ltbl = None # no default value allowed
        self.label = ''
        self.npairs = None # no default value allowed
        self.points = [] # no default value allowed

    def check_at_least_two_points(self):

        num_points = len(self.points)
        if num_points < 2:
            alert(
                {'data_type':'PiecewiseLinearCostFunction',
                 'error_message':'fails to have at least 2 points. Please provide at least 2 sample points for each piecewise linear cost function',
                 'diagnostics':{
                     'ltbl': self.ltbl,
                     'nx': num_points}})

    def check_dx_margin(self):

        num_points = len(self.points)
        x = [self.points[i].x for i in range(num_points)]
        dx = [x[i + 1] - x[i] for i in range(num_points - 1)]
        for i in range(num_points - 1):
            if dx[i] < gen_cost_dx_margin:
                alert(
                    {'data_type':'PiecewiseLinearCostFunction',
                     'error_message':(
                         'fails dx margin at points (i, i + 1). Please ensure that the sample points on each piecewise linear cost function are listed in order of increasing x coordinate, with each consecutive pair of x points differing by at least: %10.2e (MW)' %
                         gen_cost_dx_margin),
                     'diagnostics':{
                         'ltbl': self.ltbl,
                         'i': i,
                         'dx[i]': dx[i],
                         'x[i]': x[i],
                         'x[i + 1]': x[i + 1]}})

    def check_ddydx_margin(self):

        num_points = len(self.points)
        x = [self.points[i].x for i in range(num_points)]
        y = [self.points[i].y for i in range(num_points)]
        dx = [x[i + 1] - x[i] for i in range(num_points - 1)]
        dy = [y[i + 1] - y[i] for i in range(num_points - 1)]
        dydx = [dy[i] / dx[i] for i in range(num_points - 1)]
        ddydx = [dydx[i + 1] - dydx[i] for i in range(num_points - 2)]
        for i in range(num_points - 2):
            if ddydx[i] < gen_cost_ddydx_margin:
                alert(
                    {'data_type':'PiecewiseLinearCostFunction',
                     'error_message':(
                         'fails ddydx margin at points (i, i + 1, i + 2). Please ensure that the sample points on each piecewise linear cost function have increasing slopes, with each consecutive pair of slopese differing by at least: %10.2e (USD/MW-h)' %
                         gen_cost_ddydx_margin),
                     'diagnostics':{
                         'ltbl': self.ltbl,
                         'i': i,
                         'ddydx[i]': ddydx[i],
                         'dydx[i]': dydx[i],
                         'dydx[i + 1]': dydx[i + 1],
                         'x[i]': x[i],
                         'x[i + 1]': x[i + 1],
                         'x[i + 2]': x[i + 2],
                         'y[i]': y[i],
                         'y[i + 1]': y[i + 1],
                         'y[i + 2]': y[i + 2]}})

    def check_x_min_margin(self, pmin):

        num_points = len(self.points)
        x = [self.points[i].x for i in range(num_points)]
        xmin = min(x)
        if pmin - xmin < gen_cost_x_bounds_margin:
            alert(
                {'data_type':'PiecewiseLinearCostFunction',
                 'error_message':(
                     'fails x min margin. Please ensure that for each piecewise linear cost function f for a generator g, the x coordinate of at least one of the sample points of f is less than pmin of g by at least: %10.2e (MW)' %
                     gen_cost_x_bounds_margin),
                 'diagnostics':{
                     'ltbl': self.ltbl,
                     'pmin - xmin': (pmin - xmin),
                     'pmin': pmin,
                     'xmin': xmin}})

    def check_x_max_margin(self, pmax):

        num_points = len(self.points)
        x = [self.points[i].x for i in range(num_points)]
        xmax = max(x)
        if xmax - pmax < gen_cost_x_bounds_margin:
            alert(
                {'data_type':'PiecewiseLinearCostFunction',
                 'error_message':(
                    'fails x max margin. Please ensure that for each piecewise linear cost function f for a generator g, the x coordinate of at least one of the sample points of f is greater than pmax of g by at least: %10.2e (MW)' %
                    gen_cost_x_bounds_margin),
                 'diagnostics':{
                     'ltbl': self.ltbl,
                     'xmax - pmax': (xmax - pmax),
                     'pmax': pmax,
                     'xmax': xmax}})

    def read_from_row(self, row):

        self.ltbl = parse_token(row[0], int, default=None)
        self.npairs = parse_token(row[2], int, default=None)
        for i in range(self.npairs):
            point = Point()
            point.read_from_row(
                row[(3 + 2*i):(5 + 2*i)])
            self.points.append(point)
        if read_unused_fields:
            self.label = parse_token(row[1], str, '')

    def get_num_rows_from_row(self, row):

        num_rows = parse_token(row[2], int, 0) + 1
        return num_rows

    def flatten_rows(self, rows):

        row = [t for r in rows for t in r]
        return row

    def read_from_rows(self, rows):

        self.read_from_row(self.flatten_rows(rows))
    
class  QuadraticCostFunctions(GeneratorDispatchRecord,PiecewiseLinearCostFunction):
    def __init__(self):
        GeneratorDispatchRecord.__init__(self)
        PiecewiseLinearCostFunction.__init__(self)
        self.constc = None
        self.linearc = None
        self.quadraticc = None
        self.powerfactor = None

    def read_from_csv_quadraticinfo(self, row):
        if parse_token(row[2], int, '')==0:
            self.constc = parse_token(row[3], float, 0.0)
        elif parse_token(row[2], int, '')==1:
            self.linearc =  parse_token(row[3], float, 0.0)
        elif parse_token(row[2], int, '')==2:    
            self.quadraticc =  parse_token(row[3], float, 0.0)
        elif parse_token(row[2], int, '')==9: 
            self.powerfactor =  parse_token(row[3], float, 0.0)

class GeneratorInlRecord:

    def __init__(self):

        self.i = None # no default allowed
        self.id = None # no default allowed
        self.h = 4.0
        self.pmax = 0.0
        self.pmin = 0.0
        self.r = 0.05
        self.d = 0.0

    def read_from_row(self, row):

        row = pad_row(row, 7)
        self.i = parse_token(row[0], int, default=None)
        self.id = parse_token(row[1], str, default=None)
        self.r = parse_token(row[5], float, default=None)
        if read_unused_fields:
            self.h = parse_token(row[2], float, 4.0)
            self.pmax = parse_token(row[3], float, 1.0)
            self.pmin = parse_token(row[4], float, 0.0)
            self.d = parse_token(row[6], float, 0.0)
        
class Contingency:

    def __init__(self):

        self.label = ''
        self.branch_out_events = []
        self.generator_out_events = []

    def construct_record_rows(self):

        rows = (
            [['CONTINGENCY', self.label]] +
            [r.construct_record_row()
             for r in self.branch_out_events] +
            [r.construct_record_row()
             for r in self.generator_out_events] +
            [['END']])
        return rows

class Point:

    def __init__(self):

        self.x = None
        self.y = None

    def read_from_row(self, row):

        row = pad_row(row, 2)
        self.x = parse_token(row[0], float, default=None)
        self.y = parse_token(row[1], float, default=None)

class BranchOutEvent:

    def __init__(self):

        self.i = None
        self.j = None
        self.ckt = None

    def read_from_row(self, row):

        check_row_missing_fields(row, 10)
        self.i = parse_token(row[4], int, default=None)
        self.j = parse_token(row[7], int, default=None)
        self.ckt = parse_token(row[9], str, default=None)

    def read_from_csv(self, row):

        self.i = parse_token(row[2], int, '')
        self.j = parse_token(row[3], int, '')
        self.ckt = parse_token(row[4], str, '1')

    '''
    def read_three_winding_from_row(self, row):

        row = pad_row(row, 13)
        self.i = parse_token(row[4], int, '')
        self.j = parse_token(row[7], int, '')
        self.k = parse_token(row[10], int, '')
        self.ckt = parse_token(row[12], str, '1')
    '''

    def construct_record_row(self):

        return ['OPEN', 'BRANCH', 'FROM', 'BUS', self.i, 'TO', 'BUS', self.j, 'CIRCUIT', self.ckt]

class GeneratorOutEvent:

    def __init__(self):

        self.i = None
        self.id = None

    def read_from_csv(self, row):

        self.i = parse_token(row[2], int, '')
        self.id = parse_token(row[3], str, '')

    def read_from_row(self, row):

        self.i = parse_token(row[5], int, default=None)
        self.id = parse_token(row[2], str, default=None)

    def construct_record_row(self):

        return ['REMOVE', 'UNIT', self.id, 'FROM', 'BUS', self.i]
