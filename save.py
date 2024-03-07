#Translator -- defs(cgf/yaml based file --> cgf)
import yaml
import re
'''
*********************************************RULES****************************************************
1. {start_digit ... end_digit} Anything written within these curly brackets with some 
numbers in the pattern using three dots will be considered as a set of numbers and will
be repeated depending upon on the start_digit and end_digit.
    example: pmpcfg{0 ... 10} then 10 coverpoints will be written starting from pmpcfg0
    for the first coverpoint and ending with pmpcfg10 as the last/10th coverpoint. You 
    may use something like pmpcfg{10 ... 14} or any other value as well.

2. ${} means we want to use something from the macros(constants of coverpoints itself)
which is already defined in the macros.yaml --> This feature is already available in 
the risc-v isac . PR#80

3. $number where <number> is any digit refering to the {} curly brackets values defined
in that line/coverpoint.
    example: Consider a coverpoint written in the pattern:
            (pmpcfg{0 ... 10} >> 8 & pmpcfg{5 ... 8}) and (pmpcfg$1 >> 4 & 0x90) and (pmpcfg$2) == 0   
            Note: This is just for an example.
    So, in this case, pmpcfg$1 refers to the current value being used in the pmpcfg{0 ... 10} and
    pmpcfg$2 refers to the current value being used in the pmpcfg{5 ... 8}
    Note:
        You can't use the coverpoint like pmpcfg{0,1,2} to generate three coverpoints with registers
        pmpcfg0,pmpcfg1,pmpcfg2. Even if you want to generate two coverpoints, you need to follow the
        pattern like pmpcfg{0 ... 1}.

4. {value1, value 2, value3} Anything written this way will be repeated as a coverpoint depending 
upon the values written in the {} curly brackets. So, this may be considered as a loop.
    example: consider a coverpoint written in the following fashion:
            "{lw, sw, csrrs, csrrw, csrrc}": 0
            "{(rs1_val && 0x60 == 0x00),(rs2_val && 0x023 == 0)}" : 0
    So, it will be translated as for the first coverpoint:
            lw: 0
            sw: 0
            csrrw: 0
            csrrs: 0
    And for the second coverpoint:
            (rs1_val && 0x60 == 0x00): 0
            (rs2_val && 0x23 == 0x00): 0
    Note:
        You can't use the coverpoints which need to be enumerated in 4th point format.

5. {val1, val2, end_val *number_of_time} is  to be used in the
    coverpoints not independently like in the point 4(as there will be no purpose because it will
    repeat)
    Example:
            (pmpcfg{0 ... 3} >> {0, 8, 16, 24 *4}    & 0x80 == 0x80) == 0x00: 0
    Now, {0, 8, 16, 24 *4} will be enumerated such that {0,0,0,0,8,8,8,8,.....,24,24,24,24}
    Note:
        $number functionality is only available for the point 1 and 4 and can not be used with point 5 and
        6 to avoid complexity.

6. {val1 ... end_val *number_of_time} This is simply the advanced version of point 1. So, we can repeat
    the each value that comes in the loop multiple time. 
    Example:
        (pmpcfg{0 ... 3 *4}    & 0x80 == 0x80) and (old("pmpaddr{0 ... 15}")) ^ (pmpaddr$1) == 0x00: 0
    So {0 ... 3 *4} will be repeated such that {0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3}

****************************************************************************************************
'''

class Translator:
    def __init__(self):
        self.defs_data = None
        self.data_yaml = None
        self.replacement_dict = None

        self.braces_finder          = re.compile(r'({.*?})')
        self.multi_brace_finder     = re.compile(r'({.*?{.*?}.*?})')
        self.macro_def_finder       = re.compile(r'(\${.*?})') # ${variable}To ignore any such definition
        self.number_brace_finder    = re.compile(r'(\$\d+)')   # $1
        self.macro_brace_resolver   = re.compile(r'(\%\d+)')   # 
        self.repeat_brace_index     = re.compile(r'(\*\d+)')

    def translate(self, input_path, output_path):
        self.file_handler(input_path)
        self.evaluate_cp()
        self.dump_data(output_path, self.data_yaml)

    def file_handler(self, input_path):
        with open(input_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        self.defs_data = yaml_data
    
    def dump_data(self, output_path, yaml_data):
        with open(output_path, 'w') as file:
            yaml.dump(yaml_data, file)

    def evaluate_cp(self):
        self.data_yaml = None
        for curr_cov in self.defs_data:
            self.data_yaml = {curr_cov: {}}
            for label in self.defs_data[curr_cov]:
                self.finder(curr_cov,label)

    #This function will take a single line and try to find the available combinations/rules
    #and will solve them using multiple solvers, each meant for specific purpose and solve them
    #parallely and hence reducing the time, by passing it the rules.
                
    def finder(self, curr_cov, label):
        #Line contains all the instructions under the label. But, we need a instr at a specific time
        line = (self.defs_data[curr_cov][label])
        if isinstance(line, dict):
            # Solve each coverpoint one by one under the label
            for instr in line:
                # Find the macros
                macros = self.macro_def_finder.findall(instr)
                macro_dict = {macro: f'<<MACRO{index}>>' for index, macro in enumerate(macros)}
                instr = re.sub(self.macro_def_finder, lambda match: macro_dict[match.group(0)], instr)

                # Find and replace multibraces with placeholders
                multi_braces_dict = {val: f'<<MULTI{index}>>' for index, val in enumerate(self.multi_brace_finder.findall(instr))}
                instr = re.sub(self.multi_brace_finder, lambda match: multi_braces_dict[match.group(0)], instr)

                # Find and replace single braces with placeholders
                braces_dict = {val: f'<<SINGLE{index}>>' for index, val in enumerate(self.braces_finder.findall(instr)) if "..." in val}
                instr = re.sub(self.braces_finder, lambda match: braces_dict.get(match.group(0), match.group(0)), instr)

                # Find and replace comma-separated values with placeholders
                comma_dict = {val: f'<<COMMA{index}>>' for index, val in enumerate(self.braces_finder.findall(instr)) if "..." not in val}
                instr = re.sub(self.braces_finder, lambda match: comma_dict.get(match.group(0), match.group(0)), instr)

                # Find and replace $number with placeholders
                number_brace_dict = {val: f'<<NUMBER{index}>>' for index, val in enumerate(self.number_brace_finder.findall(instr))}
                instr = re.sub(self.number_brace_finder, lambda match: number_brace_dict[match.group(0)], instr)

                # Store original values for later use
                self.replacement_dict = {**macro_dict, **multi_braces_dict, **braces_dict, **comma_dict, **number_brace_dict}

                print(instr)
                #Now, let's resolve everything :)



        #if not of interest, skip and simply generate the coverpoint
        else:
            self.generator(curr_cov, label, line, 0)




    #This function will replace the macros back in the generated coverpoint
    def macro_resolver(self, instr):
        if len(self.macros) != 0:
            replace_macros = self.macro_brace_resolver.findall(instr)
            for index, value in enumerate(replace_macros):
                instr = instr.replace(value, self.macros[index])

        return instr

    #generate the required coverpoint - append in the existing one
    def generator(self, curr_cov, label, line, rule):
        if rule == 0:
            self.data_yaml[curr_cov][label] = line
        elif rule == 1:
            if label in self.data_yaml[curr_cov]:
                self.data_yaml[curr_cov][label][line] = 0
            else:
                self.data_yaml[curr_cov][label] = {}
                self.data_yaml[curr_cov][label][line] = 0


        








if __name__ == "__main__":
    defs_path = '/home/hammad/wrapper_cgf/Wrapper-cgf/config.defs'
    cgf_path  = '/home/hammad/wrapper_cgf/Wrapper-cgf/output.cgf'
    trans = Translator()
    trans.translate(defs_path, cgf_path)


















































    # def finder(self,curr_cov, label):
    #     #Line contains all the instructions under the label. But, we need a instr at a specific time
    #     line = (self.defs_data[curr_cov][label])
    #     if type(line) == dict:
    #         for instr, values in line.items():                
    #             cond_comma_loop = False
    #             repeat_list = []
    #             macros = self.macro_def_finder.findall(instr)     
    #             self.macros = macros
    #             #replace the macros to be solved in RISC-V ISAC with some defined values and replace them back after the process
    #             for index, macro in enumerate(macros):
    #                 if macro in instr:
    #                     instr = instr.replace(macro, f'%{index}')

    #             braces = self.braces_finder.findall(instr)
    #             number_brace = self.number_brace_finder.findall(instr)       

    #             #Now, let's seperate everything.
    #             for val in braces:
    #                 if "..." in val:
    #                     repeat_list.append(val)

    #             for def_rule in repeat_list:
    #                 if def_rule in braces:
    #                     braces.remove(def_rule)
    #             comma_sep_list = braces
    #             if len(comma_sep_list) != 0:
    #                 if instr == comma_sep_list[0]:
    #                     cond_comma_loop = True
    #                     comma_sep_list_braces = []
    #                 else:
    #                     comma_sep_list_braces = braces
    #             else:
    #                 comma_sep_list_braces = []
    #             #Now if we have neither of the rule matches we will
    #             #generate the coverpoint using the generator
    #             if len(repeat_list) == 0 and len(number_brace) == 0 and len(braces) == 0:
    #                 instr = self.macro_resolver(instr)
    #                 self.generator(curr_cov, label, instr, 1)

    #             #For the case of comma seperated coverpoints/variables in {} curly braces
    #             elif len(comma_sep_list) != 0 and len(number_brace) == 0 and cond_comma_loop == True:
    #                 self.comma_sep_solver(curr_cov, label, comma_sep_list)

    #             elif len(repeat_list) != 0:
    #                 self.curly_braces_solver(curr_cov, label, instr, repeat_list, number_brace, comma_sep_list_braces)
    #     #if not of interest, skip and simply generate the coverpoint
    #     else:
    #         self.generator(curr_cov, label, line, 0)

    # #This function will solve all the  curly braces and the $ numbers in parallel. So, their coverpoints will be generated
    # #using this function.
    # def curly_braces_solver(self, curr_cov, label, instr, repeat_list, number_brace, comma_sep_list):
    #     #instr --> current specific instruction coverpoint under observation
    #     #label --> label of the coverpoint
    #     #curr_cov --> current coverpoint tag
    #     #repeat_list --> contains the data of all the { ... }
    #     #number_brace --> the numbers which are dependent on the brace
    #     diff_dict = {}
    #     diff= 0
    #     instr_list = []
    #     repeat_brace_index = self.repeat_brace_index.findall(instr)

    #     for index, val in enumerate(repeat_list):
    #         repeat_repititions = 0
    #         for repeat in repeat_brace_index:
    #             if repeat in val:
    #                 repeat_repititions = repeat.replace('*', '')
    #                 val = val.replace(repeat, '')

    #         splitter = val.replace('{', '').replace('}', '').strip()
    #         splitter = splitter.split('...')

    #         if repeat_repititions != 0:
    #             diff_calc = (((int(splitter[1])+1)*int(repeat_repititions)) - int(splitter[0]))-1
    #             diff_dict[index] =  (int(splitter[0]), int(splitter[1]), int(repeat_repititions))
    #         else:
    #             diff_calc = ((int(splitter[1])) - int(splitter[0]))
    #             diff_dict[index] =  (int(splitter[0]), int(splitter[1]), int(repeat_repititions))

    #         if diff_calc > diff:
    #             diff = diff_calc
    #     #Now, solve the comma_seperated_braces
    #     resolved_comma_sep_dict = {}
    #     if len(comma_sep_list) != 0:
    #         for ind, val in enumerate(comma_sep_list):
    #             resolved_comma_sep_dict[ind] = self.comma_sep_brace_solver(val)
    #     size_loop = diff
    #     for ind, val in resolved_comma_sep_dict.items():
    #         size = len(val)
    #         if (size_loop) < size:
    #             size_loop = size -1

    #     track_dict_braces = {}
    #     track_dict_comma = {}

    #     for index, (key, value) in enumerate(diff_dict.items()):
    #         track_dict_braces[index] = [value[0],value[1], value[2], value[0], value[0]]  #start_value, max_value, repeat_count, current_value, current_repeat_value -> initialize with start_value

    #     for index, (key, val) in enumerate(resolved_comma_sep_dict.items()):
    #         track_dict_comma[index] = [len(val), 0]                                       #max_index, current index-> start from zero

    #     for i in range(size_loop+1):
    #         old = instr

    #         for key, item in enumerate(repeat_list):
    #             new=old.replace(item,str(track_dict_braces[key][3]))  #replace with the current value
    #             old = new

    #         #index of number_brace is linked with the track_dict, so no need for seperate track
    #         for k in range(len(number_brace)):
    #             new=old.replace(number_brace[k], str(track_dict_braces[int((number_brace[k])[1:])-1][3]))
    #             old = new
    #         # Now, let's keep track of the macro_sep_dict
    #         for index,val in enumerate(comma_sep_list):
    #             new = old.replace(val, resolved_comma_sep_dict[index][track_dict_comma[index][1]])
    #             old  = new

    #         track_dict_braces = self.increment(track_dict_braces)
    #         track_dict_comma = self.increment_comma(track_dict_comma)
    #         instr_list.append(old)

    #     for instruction in instr_list:
    #         resolved_instr = self.macro_resolver(instruction)
    #         self.generator(curr_cov, label, f"{resolved_instr}", 1)

    # def comma_sep_solver(self, curr_cov, label, comma_sep):
    #     comma_sep = [cov.strip() for cov in comma_sep[0][1:-1].split(',')]
    #     for cov in comma_sep:
    #         cov = self.macro_resolver(cov)
    #         self.generator(curr_cov, label, cov, 1)

    # def generator(self, curr_cov, label, line, rule):
    #     if rule == 0:
    #         self.data_yaml[curr_cov][label] = line
    #     elif rule == 1:
    #         if label in self.data_yaml[curr_cov]:
    #             self.data_yaml[curr_cov][label][line] = 0
    #         else:
    #             self.data_yaml[curr_cov][label] = {}
    #             self.data_yaml[curr_cov][label][line] = 0

    # def translate(self, input_path, output_path):
    #     self.file_handler(input_path)
    #     self.evaluate_cp()
    #     self.dump_data(output_path, self.data_yaml)

    # #This function will replace the macros back in the instruction
    # def macro_resolver(self, instr):
    #     if len(self.macros) != 0:
    #         replace_macros = self.macro_brace_resolver.findall(instr)
    #         for index, value in enumerate(replace_macros):
    #             instr = instr.replace(value, self.macros[index])

    #     return instr

    # def comma_sep_brace_solver(self, comma_sep_list):
    #     repeat_brace_index = self.repeat_brace_index.findall(comma_sep_list)
    #     repeat_len = 0
    #     if repeat_brace_index:
    #         repeat_len = int(repeat_brace_index[0].replace('*', ''))
    #         comma_sep_list = comma_sep_list.replace(repeat_brace_index[0], '')
    #     comma_sep = [cov.strip() for cov in comma_sep_list[1:-1].split(',')]

    #     return_list = []
    #     curr_val = 0
    #     curr_index = 0
    #     if repeat_brace_index:
    #         for index in range(len(comma_sep)*repeat_len):
    #             if curr_val < (repeat_len -1):
    #                 curr_val +=1
    #                 return_list.append(comma_sep[curr_index])
    #             else:
    #                 return_list.append(comma_sep[curr_index])
    #                 curr_val = 0
    #                 curr_index +=1
    #     else:
    #         return comma_sep

    #     return return_list        

    # #helper functions
    # #Takes a dictionary in the form {index: [start, end, current]} and just need to update
    # def increment(self, dict_to_update):
    #     for key, value in dict_to_update.items():
    #         if value[4] < (value[2] -1):                #current repeat value has not reached the max repeat value
    #             new_value = value.pop(4)                #pop the previous current value
    #             value.append(new_value+1)               #update with the new value at the end of the list

    #         else:                                       #current repeat value >= max repeat value
    #             if value[3] < value[1]:                 #current value < max_value
    #                 del value[4]                        #delete the value of current_repeat_value
    #                 new_value = value.pop(3)            #delete the current value
    #                 value.append(new_value+1)           #Update the current value by 1
    #                 value.append(value[0])              #change the current_repeat_value to zero
    #             else:
    #                 del value[4]                        #delete the value of current_repeat_value
    #                 new_value = value.pop(3)            #delete the current value
    #                 value.append(value[0])              #change the current_value to zero
    #                 value.append(value[0])              #change the current_repeat_value to zero

    #     return dict_to_update

    # def increment_comma(self, dict_to_update):
    #     for key, value in dict_to_update.items():
    #         if (value[1] < (value[0] -1)):
    #             new_value = value.pop(1)
    #             value.append(new_value+1)
    #         else:
    #             del value[1]
    #             value.append(0)                        #start from index 0

    #     return dict_to_update

    