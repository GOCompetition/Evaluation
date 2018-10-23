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

def parse_token(token, val_type, default):
    val = None
    if len(token) > 0:
        val = val_type(token)
    else:
        val = val_type(default)
    return val

def pad_row(row, new_row_len):

    row_len = len(row)
    row_len_diff = new_row_len - row_len
    row_new = row
    if row_len_diff > 0:
        row_new = row + row_len_diff * ['']
    return row_new

def remove_end_of_line_comment(token, end_of_line_str):
    
    token_new = token
    index = token_new.find("/")
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

    def set_areas_from_buses(self):
        
        area_i_set = set([b.area for b in self.buses.values()])
        def area_set_i(area, i):
            area.i = i
            return area
        self.areas = {i:area_set_i(Area(), i) for i in area_i_set}
        
    # TODO
    def write(self, file_name):
        '''write a RAW file'''
        
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
        row = rows[row_num]
        self.case_identification.read_from_row(row)
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
                transformer.k,
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

        #self.generator_dispatch_records = GeneratorDispatchRecord() # needs to be a dictionary
        self.generator_dispatch_records = {}
        self.active_power_dispatch_records = {}
        self.piecewise_linear_cost_functions = {}
        
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
                #print gen_dispatch.bus,gen_dispatch.genid, gen_dispatch.constc,gen_dispatch.linearc,gen_dispatch.quadraticc
            self.active_power_dispatch_records[gen_dispatch.bus,gen_dispatch.genid] = gen_dispatch
        #print gen_dispatch.bus,gen_dispatch.genid, gen_dispatch.constc
        #ds=self.active_power_dispatch_records.get((4, '1'))

 
        
    def write(self, file_name,rawdata):
        '''writes the ROP data to an ROP-formatted file'''
        file = open(file_name,"w") 
        file.write(" 0 / ROP file\n") 
        file.write(" 0 / End of Bus Voltage Constraint data, begin Adjustable Bus Shunt data\n") 
        file.write(" 0 / End of Adjustable Bus Shunt data, begin Bus Load data\n")
        file.write(" 0 / End of Bus Load data, begin Adjustable Bus Load Tables\n")
        file.write(" 0 / End of Adjustable Bus Load Tables, begin Generator Dispatch data\n")
        index=1
        for r in rawdata.generators.values():
            row=str(r.i)+", "+str(r.id)+", "+"1.000000"+", "+str(index)+"\n"
            #ds=self.active_power_dispatch_records.get((r.i,r.id))
            file.write(row)
            index=index+1
        
        file.write(" 0 / End of Generator Dispatch data, begin Active Power Dispatch Tables\n")
        index=1
        for r in rawdata.generators.values():
            row=str(index)+", "+str(r.pt)+", "+str(r.pb)+", "+"1.000000"+", "+"2"+", "+str(r.stat)+", "+str(index)+"\n"
            #ds=self.active_power_dispatch_records.get((r.i,r.id))
            file.write(row)
            index=index+1
        
        file.write(" 0 / End of Active Power Dispatch Tables, begin Generation Reserve data\n")
        file.write(" 0 / End of Generation Reserve data, begin Generation Reactive Capability data\n")
        file.write(" 0 / End of Generation Reactive Capability data, begin Adjustable Branch Reactance data\n")
        file.write(" 0 / End of Adjustable Branch Reactance data, begin Piece - wise Linear Cost Tables\n")
        index=1
        for r in rawdata.generators.values():
            row=str(index)+", "+"LINEAR "+str(index)+", "+str(self.active_power_dispatch_records.get((r.i,r.id)).npairs)+"\n"
            #ds=self.active_power_dispatch_records.get((r.i,r.id))
            file.write(row)
            for r2 in range(self.active_power_dispatch_records.get((r.i,r.id)).npairs):
                row=str(self.active_power_dispatch_records.get((r.i,r.id)).points[r2*2])+", "
                row=row+str(self.active_power_dispatch_records.get((r.i,r.id)).points[r2*2+1])+"\n"
                file.write(row)
            index=index+1
        file.write(" 0 / End of Piece-wise Linear Cost Tables, begin Piece-wise Quadratic Cost Tables\n")
        
        file.write(" 0 / End of Piece-wise Quadratic Cost Tables, begin Polynomial Cost Tables\n")
        
        file.write(" 0 / End of Polynomial Cost Tables, begin Period Reserve data\n")
        file.write(" 0 / End of Period Reserve data, begin Branch Flow Constraint data\n")
        file.write(" 0 / End of Branch Flow Constraint data, begin Interface Flow data\n")
        file.write(" 0 / End of Interface Flow data, begin Linear Constraint Equation Dependency data\n")
        file.write(" 0 / End of Linear Constraint Equation Dependency data, begin 2-terminal dc Line Constraint data\n")
        file.write(" 0 / End of 2-terminal dc Line Constraint data")
        file.close() 

        
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
            #piecewise_linear_cost_function = PiecewiseLinearCostFunction(ActivePowerDispatchRecord)
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

    # TODO
    def read_from_phase_0(self, file_name):
        '''takes the generator.csv file as input'''

    # TODO
        '''writes the INL data to an INL-formatted file'''
    def write(self, file_name,rawdata,rop):
        file = open(file_name,"w") 
        index=1
        for r in rawdata.generators.values():
            #the default value of machine inertia is 4.0
            row=str(r.i)+", "+str(r.id)+", "+"4.0"+", "+str(r.pt)+", "+str(r.pb)+", "+str(rop.active_power_dispatch_records.get((r.i,r.id)).powerfactor) +", "+ "0.0"+ "\n"
            #ds=self.active_power_dispatch_records.get((r.i,r.id))
            file.write(row)
            index=index+1
        file.write("0 \n")
        file.close() 






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

    def write(self, file_name):
        file = open(file_name,"w") 
        #for r in self.contingencies.values():
        for r in self.contingencies:
            row="CONTINGENCY   "+r+"\n"
            #ds=self.active_power_dispatch_records.get((r.i,r.id))
            file.write(row)
            if cmp(r[0:4],'LINE')==0:
                row="DISCONNECT LINE FROM BUS   "+str(self.contingencies.get(r).i)+" TO BUS  "+str(self.contingencies.get(r).j)+ " CKT  " + str(self.contingencies.get(r).ckt)+"\n"
            elif cmp(r[0:3],'GEN')==0: 
                row="REMOVE MACHINE  "+str(self.contingencies.get(r).id)+" FROM BUS  "+str(self.contingencies.get(r).i)+"\n"
            file.write(row)
            file.write("END\n")
        file.write("END\n")   
    def read(self, file_name):

        with open(file_name, 'r') as in_file:
            lines = in_file.readlines()
        delimiter_str = " "
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

        return (
            row[0].upper() in {'DISCONNECT', 'OPEN', 'TRIP'} and
            row[1].upper() in {'BRANCH', 'LINE'})

    def is_three_winding(self, row):

        #print row
        if len(row) < 9:
            return False
        elif row[8].upper() == 'TO':
            return True
        else:
            return False

    def is_generator_out_event(self, row):

        return(
            row[0].upper() == 'REMOVE' and
            row[1].upper() in {'UNIT', 'MACHINE'})
        
    def read_from_rows(self, rows):

        row_num = -1
        in_contingency = False
        while True:
            row_num += 1
            if row_num >= len(rows): # in case the data provider failed to put an end file line
                return
            row = rows[row_num]
            if self.row_is_file_end(row):
                return
            #if self.row_is_section_end(row):
            #    break
            if self.is_contingency_start(row):
                in_contingency = True
                contingency = Contingency()
                contingency.label = row[1]
            if self.is_end(row):
                if in_contingency:
                    self.contingencies[contingency.label] = contingency
                    in_contingency = False
                else:
                    break
            if self.is_branch_out_event(row):
                branch_out_event = BranchOutEvent()
                if self.is_three_winding(row):
                    branch_out_event.read_three_winding_from_row(row)
                else:
                    branch_out_event.read_from_row(row)
                contingency.branch_out_events.append(branch_out_event)
            if self.is_generator_out_event(row):
                generator_out_event = GeneratorOutEvent()
                generator_out_event.read_from_row(row)
                contingency.generator_out_events.append(generator_out_event)

class CaseIdentification:

    def __init__(self):

        self.ic = None
        self.sbase = None
        self.rev = None
        self.xfrrat = None
        self.nxfrat = None
        self.basfrq = None

    def read_from_row(self, row):

        row = pad_row(row, 6)
        row[5] = remove_end_of_line_comment(row[5], '/')
        self.ic = parse_token(row[0], int, 0)
        self.sbase = parse_token(row[1], float, 100.0)
        self.rev = parse_token(row[2], int, 33)
        self.xfrrat = parse_token(row[3], float, -1.0)
        self.nxfrat = parse_token(row[4], float, 1.0)
        self.basfrq = parse_token(row[5], float, 60.0) # need to remove end of line comment

class Bus:

    def __init__(self):

        self.i = None
        self.name = None
        self.baskv = None
        self.ide = None
        self.area = None
        self.zone = None
        self.owner = None
        self.vm = None
        self.va = None
        self.nvhi = None
        self.nvlo = None
        self.evhi = None
        self.evlo = None

    def read_from_row(self, row):

        row = pad_row(row, 13)
        self.i = parse_token(row[0], int, '')
        self.name = parse_token(row[1], str, 12*' ')
        self.baskv = parse_token(row[2], float, 0.0)
        self.ide = parse_token(row[3], int, 1)
        self.area = parse_token(row[4], int, 1)
        self.zone = parse_token(row[5], int, 1)
        self.owner = parse_token(row[6], int, 1)
        self.vm = parse_token(row[7], float, 1.0)
        self.va = parse_token(row[8], float, 0.0)
        self.nvhi = parse_token(row[9], float, 1.1)
        self.nvlo = parse_token(row[10], float, 0.9)
        self.evhi = parse_token(row[11], float, 1.1)
        self.evlo = parse_token(row[12], float, 0.9)
    
class Load:

    def __init__(self):

        self.i = None
        self.id = None
        self.status = None
        self.area = None
        self.zone = None
        self.pl = None
        self.ql = None
        self.ip = None
        self.iq = None
        self.yp = None
        self.yq = None
        self.owner = None
        self.scale = None
        self.intrpt = None

    def read_from_row(self, row):

        row = pad_row(row, 14)
        self.i = parse_token(row[0], int, '')
        self.id = parse_token(row[1], str, '1')
        self.status = parse_token(row[2], int, 1)
        self.area = parse_token(row[3], int, 0)
        self.zone = parse_token(row[4], int, 0)
        self.pl = parse_token(row[5], float, 0.0)
        self.ql = parse_token(row[6], float, 0.0)
        self.ip = parse_token(row[7], float, 0.0)
        self.iq = parse_token(row[8], float, 0.0)
        self.yp = parse_token(row[9], float, 0.0)
        self.yq = parse_token(row[10], float, 0.0)
        self.owner = parse_token(row[11], int, 0)
        self.scale = parse_token(row[12], int, 1)
        self.intrpt = parse_token(row[13], int, 0)

class FixedShunt:

    def __init__(self):

        self.i = None
        self.id = None
        self.status = None
        self.gl = None
        self.bl = None

    def read_from_row(self, row):

        row = pad_row(row, 5)
        self.i = parse_token(row[0], int, '')
        self.id = parse_token(row[1], str, '1')
        self.status = parse_token(row[2], int, 1)
        self.gl = parse_token(row[3], float, 0.0)
        self.bl = parse_token(row[4], float, 0.0)

class Generator:

    def __init__(self):
        self.i = None
        self.id = None
        self.pg = None
        self.qg = None
        self.qt = None
        self.qb = None
        self.vs = None
        self.ireg = None
        self.mbase = None
        self.zr = None
        self.zx = None
        self.rt = None
        self.xt = None
        self.gtap = None
        self.stat = None
        self.rmpct = None
        self.pt = None
        self.pb = None
        self.o1 = None
        self.f1 = None
        self.o2 = None
        self.f2 = None
        self.o3 = None
        self.f3 = None
        self.o4 = None
        self.f4 = None
        self.wmod = None
        self.wpf = None

    def read_from_row(self, row):

        row = pad_row(row, 28)
        self.i = parse_token(row[0], int, '')
        self.id = parse_token(row[1], str, '1')
        self.pg = parse_token(row[2], float, 0.0)
        self.qg = parse_token(row[3], float, 0.0)
        self.qt = parse_token(row[4], float, 9999.0)
        self.qb = parse_token(row[5], float, -9999.0)
        self.vs = parse_token(row[6], float, 1.0)
        self.ireg = parse_token(row[7], int, 0)
        self.mbase = parse_token(row[8], float, 0.0)
        self.zr = parse_token(row[9], float, 0.0)
        self.zx = parse_token(row[10], float, 1.0)
        self.rt = parse_token(row[11], float, 0.0)
        self.xt = parse_token(row[12], float, 0.0)
        self.gtap = parse_token(row[13], float, 1.0)
        self.stat = parse_token(row[14], int, 1)
        self.rmpct = parse_token(row[15], float, 100.0)
        self.pt = parse_token(row[16], float, 9999.0)
        self.pb = parse_token(row[17], float, -9999.0)
        self.o1 = parse_token(row[18], int, 0)
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

        self.i = None
        self.j = None
        self.ckt = None
        self.r = None
        self.x = None
        self.b = None
        self.ratea = None
        self.rateb = None
        self.ratec = None
        self.gi = None
        self.bi = None
        self.gj = None
        self.bj = None
        self.st = None
        self.met = None
        self.len = None
        self.o1 = None
        self.f1 = None
        self.o2 = None
        self.f2 = None
        self.o3 = None
        self.f3 = None
        self.o4 = None
        self.f4 = None

    def read_from_row(self, row):

        row = pad_row(row, 24)
        self.i = parse_token(row[0], int, '')
        self.j = parse_token(row[1], int, '')
        self.ckt = parse_token(row[2], str, '1')
        self.r = parse_token(row[3], float, 0.0)
        self.x = parse_token(row[4], float, 0.0)
        self.b = parse_token(row[5], float, 0.0)
        self.ratea = parse_token(row[6], float, 0.0)
        self.rateb = parse_token(row[7], float, 0.0)
        self.ratec = parse_token(row[8], float, 0.0)
        self.gi = parse_token(row[9], float, 0.0)
        self.bi = parse_token(row[10], float, 0.0)
        self.gj = parse_token(row[11], float, 0.0)
        self.bj = parse_token(row[12], float, 0.0)
        self.st = parse_token(row[13], int, 1)
        self.met = parse_token(row[14], int, 1)
        self.len = parse_token(row[15], float, 0.0)
        self.o1 = parse_token(row[16], int, 0)
        self.f1 = parse_token(row[17], float, 1.0)
        self.o2 = parse_token(row[18], int, 0)
        self.f2 = parse_token(row[19], float, 1.0)
        self.o3 = parse_token(row[20], int, 0)
        self.f3 = parse_token(row[21], float, 1.0)
        self.o4 = parse_token(row[22], int, 0)
        self.f4 = parse_token(row[23], float, 1.0)

class Transformer:

    def __init__(self):

        self.i = None
        self.j = None
        self.k = None
        self.ckt = None
        self.cw = None
        self.cz = None
        self.cm = None
        self.mag1 = None
        self.mag2 = None
        self.nmetr = None
        self.name = None
        self.stat = None
        self.o1 = None
        self.f1 = None
        self.o2 = None
        self.f2 = None
        self.o3 = None
        self.f3 = None
        self.o4 = None
        self.f4 = None
        self.vecgrp = None
        self.r12 = None
        self.x12 = None
        self.sbase12 = None
        self.r23 = None
        self.x23 = None
        self.sbase23 = None
        self.r31 = None
        self.x31 = None
        self.sbase31 = None
        self.vmstar = None
        self.anstar = None
        self.windv1 = None
        self.nomv1 = None
        self.ang1 = None
        self.rata1 = None
        self.ratb1 = None
        self.ratc1 = None
        self.cod1 = None
        self.cont1 = None
        self.rma1 = None
        self.rmi1 = None
        self.vma1 = None
        self.vmi1 = None
        self.ntp1 = None
        self.tab1 = None
        self.cr1 = None
        self.cx1 = None
        self.cnxa1 = None
        self.windv2 = None
        self.nomv2 = None
        self.ang2 = None
        self.rata2 = None
        self.ratb2 = None
        self.ratc2 = None
        self.cod2 = None
        self.cont2 = None
        self.rma2 = None
        self.rmi2 = None
        self.vma2 = None
        self.vmi2 = None
        self.ntp2 = None
        self.tab2 = None
        self.cr2 = None
        self.cx2 = None
        self.cnxa2 = None
        self.windv3 = None
        self.nomv3 = None
        self.ang3 = None
        self.rata3 = None
        self.ratb3 = None
        self.ratc3 = None
        self.cod3 = None
        self.cont3 = None
        self.rma3 = None
        self.rmi3 = None
        self.vma3 = None
        self.vmi3 = None
        self.ntp3 = None
        self.tab3 = None
        self.cr3 = None
        self.cx3 = None
        self.cnxa3 = None

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

        rows_new = rows
        if len(rows_new) == 4:
            rows_new.append([])
        rows_len = [len(r) for r in rows_new]
        rows_len_new = [21, 11, 17, 17, 17]
        rows_len_increase = [rows_len_new[i] - rows_len[i] for i in range(5)]
        # check no negatives in increase
        rows_new = [rows_new[i] + rows_len_increase[i]*[''] for i in range(5)]
        return rows_new

    def flatten_rows(self, rows):

        row = [t for r in rows for t in r]
        return row
    
    def read_from_row(self, row):

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

class Area:

    def __init__(self):

        self.i = None
        self.isw = None
        self.pdes = None
        self.ptol = None
        self.arname = None

    def read_from_row(self, row):

        row = pad_row(row, 5)
        self.i = parse_token(row[0], int, '')
        self.isw = parse_token(row[1], int, 0)
        self.pdes = parse_token(row[2], float, 0.0)
        self.ptol = parse_token(row[3], float, 10.0)
        self.arname = parse_token(row[4], str, 12*' ')

class Zone:

    def __init__(self):

        self.i = None
        self.zoname = None
        
    def read_from_row(self, row):

        row = pad_row(row, 2)
        self.i = parse_token(row[0], int, '')
        self.zoname = parse_token(row[1], str, 12*' ')

class SwitchedShunt:

    def __init__(self):

        self.i = None
        self.modsw = None
        self.adjm = None
        self.stat = None
        self.vswhi = None
        self.vswlo = None
        self.swrem = None
        self.rmpct = None
        self.rmidnt = None
        self.binit = None
        self.n1 = None
        self.b1 = None
        self.n2 = None
        self.b2 = None
        self.n3 = None
        self.b3 = None
        self.n4 = None
        self.b4 = None
        self.n5 = None
        self.b5 = None
        self.n6 = None
        self.b6 = None
        self.n7 = None
        self.b7 = None
        self.n8 = None
        self.b8 = None

    def read_from_row(self, row):

        row = pad_row(row, 26)
        self.i = parse_token(row[0], int, '')
        self.modsw = parse_token(row[1], int, 1)
        self.adjm = parse_token(row[2], int, 0)
        self.stat = parse_token(row[3], int, 1)
        self.vswhi = parse_token(row[4], float, 1.0)
        self.vswlo = parse_token(row[5], float, 1.0)
        self.swrem = parse_token(row[6], int, 0)
        self.rmpct = parse_token(row[7], float, 100.0)
        self.rmidnt = parse_token(row[8], str, 12*' ')
        self.binit = parse_token(row[9], float, 0.0)
        self.n1 = parse_token(row[10], int, 0)
        self.b1 = parse_token(row[11], float, 0.0)
        self.n2 = parse_token(row[12], int, 0)
        self.b2 = parse_token(row[13], float, 0.0)
        self.n3 = parse_token(row[14], int, 0)
        self.b3 = parse_token(row[15], float, 0.0)
        self.n4 = parse_token(row[16], int, 0)
        self.b4 = parse_token(row[17], float, 0.0)
        self.n5 = parse_token(row[18], int, 0)
        self.b5 = parse_token(row[19], float, 0.0)
        self.n6 = parse_token(row[20], int, 0)
        self.b6 = parse_token(row[21], float, 0.0)
        self.n7 = parse_token(row[22], int, 0)
        self.b7 = parse_token(row[23], float, 0.0)
        self.n8 = parse_token(row[24], int, 0)
        self.b8 = parse_token(row[25], float, 0.0)
        
class GeneratorDispatchRecord:

    def __init__(self):

        self.bus = None
        self.genid = None
        self.disp = None
        self.dsptbl = None

    def read_from_row(self, row):

        row = pad_row(row, 4)
        self.bus = parse_token(row[0], int, '')
        self.genid = parse_token(row[1], str, '1').strip()
        self.disp = parse_token(row[2], float, 1.0)
        self.dsptbl = parse_token(row[3], int, 0)
    def read_from_csv(self, row):
        self.bus = parse_token(row[0], int, '')
        self.genid = parse_token(row[1], str, '1').strip()

        
class ActivePowerDispatchRecord:

    def __init__(self):

        self.tbl = None
        self.pmax = None
        self.pmin = None
        self.fuelcost = None
        self.ctyp = None
        self.status = None
        self.ctbl = None

    def read_from_row(self, row):

        row = pad_row(row, 7)
        self.tbl = parse_token(row[0], int, '')
        self.pmax = parse_token(row[1], float, 9999.0)
        self.pmin = parse_token(row[2], float, -9999.0)
        self.fuelcost = parse_token(row[3], float, 1.0)
        self.ctyp = parse_token(row[4], int, 1)
        self.status = parse_token(row[5], int, 1)
        self.ctbl = parse_token(row[6], int, 0)



class PiecewiseLinearCostFunction():

    def __init__(self):

        self.ltbl = None
        self.label = None
        self.costzero =None
        self.npairs = None
        self.points = []

    def read_from_row(self, row):

        self.ltbl = parse_token(row[0], int, '')
        self.label = parse_token(row[1], str, '')
        self.npairs = parse_token(row[2], int, 0)
        for i in range(self.npairs):
            point = Point()
            point.read_from_row(
                row[(3 + 2*i):(5 + 2*i)])
            self.points.append(point)

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

        self.i = None
        self.id = None
        self.h = None
        self.pmax = None
        self.pmin = None
        self.r = None
        self.d = None

    def read_from_row(self, row):

        row = pad_row(row, 7)
        self.i = parse_token(row[0], int, '')
        self.id = parse_token(row[1], str, '1')
        self.h = parse_token(row[2], float, 4.0)
        self.pmax = parse_token(row[3], float, 1.0)
        self.pmin = parse_token(row[4], float, 0.0)
        self.r = parse_token(row[5], float, 0.05)
        self.d = parse_token(row[6], float, 0.0)
        
class Contingency:

    def __init__(self):

        self.label = ''
        self.branch_out_events = []
        self.generator_out_events = []

class Point:

    def __init__(self):

        self.x = None
        self.y = None

    def read_from_row(self, row):

        row = pad_row(row, 2)
        self.x = parse_token(row[0], float, 0.0)
        self.y = parse_token(row[1], float, 0.0)

class BranchOutEvent:

    def __init__(self):

        self.i = None
        self.j = None
        self.ckt = None

    def read_from_row(self, row):

        row = pad_row(row, 10)
        self.i = parse_token(row[4], int, '')
        self.j = parse_token(row[7], int, '')
        self.ckt = parse_token(row[9], str, '1')
    def read_from_csv(self, row):
        self.i = parse_token(row[2], int, '')
        self.j = parse_token(row[3], int, '')
        self.ckt = parse_token(row[4], str, '1')
    def read_three_winding_from_row(self, row):

        row = pad_row(row, 13)
        self.i = parse_token(row[4], int, '')
        self.j = parse_token(row[7], int, '')
        self.k = parse_token(row[10], int, '')
        self.ckt = parse_token(row[12], str, '1')

class GeneratorOutEvent:

    def __init__(self):

        self.i = None
        self.id = None
    def read_from_csv(self, row):
        self.i = parse_token(row[2], int, '')
        self.id = parse_token(row[3], str, '1')
    def read_from_row(self, row):

        self.i = parse_token(row[5], int, '')
        self.id = parse_token(row[2], str, '1')
