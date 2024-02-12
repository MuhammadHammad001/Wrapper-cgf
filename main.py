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
****************************************************************************************************
'''

class Translator:
    def __init__(self):
        self.defs_data = None
        self.data_yaml = None
        self.macros    = None

        self.braces_finder = re.compile(r'({.*?})')
        self.macro_def_finder = re.compile(r'(\${.*?})') # To ignore any such definition
        self.number_brace_finder = re.compile(r'(\$\d+)')
        self.macro_brace_resolver = re.compile(r'(\%\d+)')

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
    def finder(self,curr_cov, label):
        #Line contains all the instructions under the label. But, we need a instr at a specific time
        line = (self.defs_data[curr_cov][label])
        if type(line) == dict:
            for instr, values in line.items():                
                repeat_list = []
                macros = self.macro_def_finder.findall(instr)     
                self.macros = macros
                #replace the macros to be solved in RISC-V ISAC with some defined values and replace them back after the process
                for index, macro in enumerate(macros):
                    if macro in instr:
                        instr = instr.replace(macro, f'%{index}')

                braces = self.braces_finder.findall(instr)
                number_brace = self.number_brace_finder.findall(instr)       

                #Now, let's seperate everything.
                for val in braces:
                    if "..." in val:
                        repeat_list.append(val)

                for def_rule in repeat_list:
                    if def_rule in braces:
                        braces.remove(def_rule)
                comma_sep_list = braces

                #Now if we have neither of the rule matches we will
                #generate the coverpoint using the generator
                if len(repeat_list) == 0 and len(number_brace) == 0 and len(braces) == 0:
                    instr = self.macro_resolver(instr)
                    self.generator(curr_cov, label, instr, 1)
                #For the case of comma seperated coverpoints/variables in {} curly braces
                elif len(comma_sep_list) != 0:
                    self.comma_sep_solver(curr_cov, label, comma_sep_list)
                elif len(repeat_list) != 0:
                    self.curly_braces_solver(curr_cov, label, instr, repeat_list, number_brace)
        else:
            self.generator(curr_cov, label, line, 0)

    #This function will solve all the  curly braces and the $ numbers in parallel. So, their coverpoints will be generated
    #using this function.
    def curly_braces_solver(self, curr_cov, label, instr, repeat_list, number_brace):
        #instr --> current specific instruction coverpoint under observation
        #label --> label of the coverpoint
        #curr_cov --> current coverpoint tag
        #repeat_list --> contains the data of all the { ... }
        #number_brace --> the numbers which are dependent on the brace
        diff_dict = {}
        diff= 0
        instr_list = []
        for index, val in enumerate(repeat_list):
            splitter = val.replace('{', '').replace('}', '').strip()
            splitter = splitter.split('...')
            diff_calc = int(splitter[1]) - int(splitter[0])
            diff_dict[index] =  (int(splitter[0]), int(splitter[1]))
            if diff_calc > diff:
                diff = diff_calc

        size_loop = diff
        track_dict_braces = {}

        for index, (key, value) in enumerate(diff_dict.items()):
            track_dict_braces[index] = [value[0],value[1], value[0]]  #start_value, max_value, current_value -> initialize with start_value

        for i in range(size_loop+1):
            old = instr

            for index, item in enumerate(repeat_list):
                new=old.replace(item,str(track_dict_braces[index][2]))  #replace with the current value
                old = new

            #index of number_brace is linked with the track_dict, so no need for seperate track
            for k in range(len(number_brace)):
                new=old.replace(number_brace[k], str(track_dict_braces[int((number_brace[k])[1:])-1][2]))
                old = new
            track_dict_braces = self.increment(track_dict_braces)
            instr_list.append(old)

        for instruction in instr_list:
            resolved_instr = self.macro_resolver(instruction)
            self.generator(curr_cov, label, f"{resolved_instr}", 1)

    def comma_sep_solver(self, curr_cov, label, comma_sep):
        comma_sep = [cov.strip() for cov in comma_sep[0][1:-1].split(',')]
        for cov in comma_sep:
            cov = self.macro_resolver(cov)
            self.generator(curr_cov, label, cov, 1)

    def generator(self, curr_cov, label, line, rule):
        if rule == 0:
            self.data_yaml[curr_cov][label] = line
        elif rule == 1:
            if label in self.data_yaml[curr_cov]:
                self.data_yaml[curr_cov][label][line] = 0
            else:
                self.data_yaml[curr_cov][label] = {}
                self.data_yaml[curr_cov][label][line] = 0

    def translate(self, input_path, output_path):
        self.file_handler(input_path)
        self.evaluate_cp()
        self.dump_data(output_path, self.data_yaml)

    #This function will replace the macros back in the instruction
    def macro_resolver(self, instr):
        if len(self.macros) != 0:
            replace_macros = self.macro_brace_resolver.findall(instr)
            for index, value in enumerate(replace_macros):
                instr = instr.replace(value, self.macros[index])

        return instr

    #helper functions
    #Takes a dictionary in the form {index: [start, end, current]} and just need to update
    def increment(self, dict_to_update):
        for key, value in dict_to_update.items():
            if value[2] < value[1]: #current value reached the max
                new_value = value.pop(2)
                value.append(new_value+1)               
            else:
                del value[2]
                value.append(value[0])
        return dict_to_update


if __name__ == "__main__":
    defs_path = '/home/hammad/wrapper_cgf/Wrapper-cgf/config.defs'
    cgf_path  = '/home/hammad/wrapper_cgf/Wrapper-cgf/output.cgf'
    trans = Translator()
    trans.translate(defs_path, cgf_path)

    