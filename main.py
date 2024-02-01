#Translator -- defs(cgf/yaml based file --> cgf)
import yaml
import re
import multiprocessing as mp
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

4. {value1, value 2, value3} Anything written this way will be repeated as a coverpoint depending 
upon the values written in the {} curly brackets. So, this may be considered as a loop.
    example: consider a coverpoint written in the following fashion:
            {lw, sw, csrrs, csrrw, csrrc}: 0
    So, it will be translated as:
            lw: 0
            sw: 0
    And, so on. Someone, may even write all the coverpoints in the curly braces and they will be
    translated like:
            {"'(pmpcfg0 >> 8) == 0': 0", "'(pmpcfg4 >> 4) == 0': 0"}
****************************************************************************************************
'''

class Translator:
    def __init__(self):
        self.defs_data = None
        self.data_yaml = None
        self.braces_finder = re.compile(r'{(.*?)}')
        self.macro_def_finder = re.compile(r'\${(.*?)}') # To ignore any such definition
        self.number_brace_finder = re.compile(r'\$(\d*)')

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
                braces = self.braces_finder.findall(instr)
                macros = self.macro_def_finder.findall(instr)     
                number_brace = self.number_brace_finder.findall(instr)          
                #Remove the macros solved in risc-v isac
                for def_rule in macros:
                    if def_rule in braces:
                        braces.remove(def_rule)
                #Now, let's seperate everything.
                for val in braces:
                    if "..." in val:
                        repeat_list.append(val)

                for def_rule in repeat_list:
                    if def_rule in braces:
                        braces.remove(def_rule)

                # print(instr)
                # print(repeat_list)
                # print(number_brace)
                # print(braces)

                #Now if we have neither of the rule matches we will
                #generate the coverpoint using the generator
                if len(repeat_list) == 0 and len(number_brace) == 0 and len(braces) == 0:
                    rule = 1
                    self.generator(curr_cov, label, instr, rule)
                #Now, start by solving the brackets with ...
                elif len(repeat_list) != 0:
                    self.curly_braces_solver(instr, repeat_list)
        else:
            rule = 0
            self.generator(curr_cov, label, line, rule)

    #This function will solve in straight order, in order to maintain the order.
    def curly_braces_solver(self, instr, repeat_list):
        diff_list = []
        for val in repeat_list:
            splitter = val.split('...')
            diff = int(splitter[1]) - int(splitter[0])
            diff_list.append(diff)              
            #let's first solve the one which has the highest value so our loop works fine.
        while max(diff_list) != 0:
            curr_diff=max(diff_list)
            index_diff = diff_list.index(curr_diff)
            diff_list[index_diff] = 0 #remove so next time the next largest without distorting the order or list
            self.curly_braces_solver(instr, index_diff, repeat_list)

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
        yaml_data = {
            'pmp_cfg_locked_write_unrelated': {
                'config': [
                    {'check': 'ISA:=regex(.*32.*);', 'check': 'ISA:=regex(.*I.*Zicsr.*);', 'def': 'rvtest_mtrap_routine=True;'}
                ],
                'mnemonics': {'csrrw': 0, 'csrrs': 0},
                'csr_comb': {
                    "(old('pmpcfg{ 0..15}') ^ pmpcfg$1)  & ((pmpcfgmsk<<{0..3}<<3) == 0x00) and (pmpcfg$1 & (pmplckmsk<<$2 !=0)" : 0,
                    "(old('pmpaddr{0..63}' == pmpaddr$1) and (pmpcfg{$1>>2} & (pmplckmsk<<{($1&3)<<3}) !=0)" : 0
                }
            }
        }
        # print(yaml_data)
        self.dump_data(output_path, self.data_yaml)
if __name__ == "__main__":
    defs_path = '/home/hammad/wrapper_cgf/config.defs'
    cgf_path  = '/home/hammad/wrapper_cgf/output.cgf'
    trans = Translator()
    trans.translate(defs_path, cgf_path)

    