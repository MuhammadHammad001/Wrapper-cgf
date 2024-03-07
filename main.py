#Translator -- defs(cgf/yaml based file --> cgf)
import os
import re
import math
import yaml
'''
*********************************************RULES****************************************************

1. {start_digit ... end_digit}:
   - Anything within curly brackets containing numbers separated by three dots will be considered a range.
   - The range will generate coverpoints from start_digit to end_digit, inclusive.
   - Example: pmpcfg{0 ... 10} will generate coverpoints from pmpcfg0 to pmpcfg10.

2. ${} Macro Usage:
   - Use ${} to reference macros defined in macros.yaml.
   - They are not dealt in this script, will be resolved in the RISC-V ISAC
   - Macros are constants or predefined coverpoint values.
   - Example: ${MACRO_NAME}

3. $number Placeholder:
   - Use $number to refer to values from curly brackets in the same line.
   - Each $number corresponds to a value in the curly brackets in order of appearance.
   - Example: (pmpcfg{0 ... 10} >> 8) and (pmpcfg$1 == 0x80)

4. {value1, value2, ...} Loop:
   - Lists enclosed in curly brackets will generate coverpoints by iterating through values.
   - Each value will be used as a coverpoint.
   - Example: "{lw, sw, csrrw}": 0 will generate coverpoints for lw, sw, and csrrw.

5. {{val1, val2, end_val} <operation> <digit>} Enumeration with Operation:
   - Use double curly brackets with an operation to enumerate values.
   - Values will be enumerated based on the specified operation and digit.
   - Example: {{0, 8, 16, 24} >> 4} will enumerate values {0, 0, 1, 1}.

6. {{val1 ... end_val} <operation> <digit>} Advanced Range Enumeration:
   - Advanced version of point 1 allowing repeated values in the range.
   - Each value in the range will be repeated based on the specified operation and digit.
   - Example: {{0 ... 3} * 4} will generate {0, 4, 8, 12}.

****************************************************************************************************
'''

class Translator:
    """A class for translating YAML data and generating coverpoints."""

    def __init__(self):
        """Initialize the Translator object."""
        self.defs_data = None
        self.data_yaml = None
        self.replacement_dict = {}
        self.replacement_dict_resolved = {}
        self.number_replace_order = {}
        self.curr_cov = None
        self.label = None

        self.braces_finder          = re.compile(r'({.*?})')
        self.multi_brace_finder     = re.compile(r'({\s*{.*?}.*?})')
        self.macro_def_finder       = re.compile(r'(\${.*?})') # ${variable}To ignore any such definition
        self.number_brace_finder    = re.compile(r'(\$\d+)')   # $1
        self.macro_brace_resolver   = re.compile(r'(\%\d+)')   # 
        self.repeat_brace_index     = re.compile(r'(\*\d+)')
        self.placeholder_pattern = re.compile(r'<<MULTI\d+>>|<<SINGLE\d+>>|<<COMMA\d+>>')

    def translate(self, input_path, output_path):
        """Translate YAML data from the input file and dump it into the output file.
        
        Args:
            input_path (str): Path to the input YAML file.
            output_path (str): Path to save the translated YAML data.
        """
        self.load_yaml(input_path)
        self.evaluate_cp()
        self.dump_data(output_path, self.data_yaml)

    def load_yaml(self, input_path):
        """Load YAML data from the given file path.

        Args:
            input_path (str): Path to the YAML file to load.

        Raises:
            FileNotFoundError: If the specified file is not found.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"{input_path} does not exist.")
        try:
            with open(input_path, 'r') as file:
                yaml_data = yaml.safe_load(file)
            self.defs_data = yaml_data
        except Exception as e:
            print(f"Failed to load YAML file: {e}")

    def dump_data(self, output_path, yaml_data):
        """Dump the given YAML data into the specified file.

        Args:
            output_path (str): Path to save the YAML data.
            yaml_data (dict): YAML data to be dumped.

        Raises:
            Exception: If an error occurs while writing data to the file.
        """
        try:
            with open(output_path, 'w') as file:
                yaml.dump(yaml_data, file)
        except Exception as e:
            print(f"Failed to write data to file: {e}")

    def evaluate_cp(self):
        """Evaluate coverpoints based on the loaded YAML data."""
        self.data_yaml = None
        for curr_cov in self.defs_data:
            self.data_yaml = {curr_cov: {}}
            for label in self.defs_data[curr_cov]:
                self.finder(curr_cov,label)

    def finder(self, curr_cov, label):
        """
        Find combinations/rules in a single line and solve them using multiple solvers.

        Args:
            curr_cov (str): The current coverpoint.
            label (str): The label within the coverpoint.

        Returns:
            None
        """
        self.curr_cov = curr_cov
        self.label = label
        line = self.defs_data[curr_cov][label]
        if isinstance(line, dict):
            for instr in line:
                # Clean replacement dict on every iteration
                self.replacement_dict = {}

                # Process macros
                macros = self.macro_def_finder.findall(instr)
                instr = self.replace_macros(instr, macros)

                # Process multibraces
                instr = self.replace_multibraces(instr)

                # Process single braces and comma-separated values
                instr = self.replace_braces_commas(instr)

                # Process $number placeholders
                instr = self.replace_number_placeholders(instr)

                # Check the order of every brace and maintain with the $number placeholder
                place_holder_pattern = self.replace_order_pattern(instr)

                # Resolve every brace found in the string

                # Resolve the single braces and multi_internal braces
                self.resolve_single_brace(self.replacement_dict)

                # Resolve the multibraces
                self.resolve_multibraces(self.replacement_dict)

                # Resolve the comma separated
                self.resolve_comma_brace(self.replacement_dict)

                # Substitute the values in the coverpoint

                # Complete the coverpoint process
                self.calculate_coverpoints(instr, self.replacement_dict, place_holder_pattern)

                # If there is no substitution, then generate
                if len(self.replacement_dict) == 0:
                    self.generator(curr_cov, label, instr, 1)

        # Generate the coverpoint not of interest
        else:
            self.generator(curr_cov, label, line, 0)

    def replace_macros(self, instr, macros):
        """
        Replace macros in the instruction with placeholders.

        Args:
            instr (str): The instruction string.
            macros (list): List of macros to replace.

        Returns:
            str: The instruction string with macros replaced.
        """
        macro_dict = {macro: f'<<MACRO{index}>>' for index, macro in enumerate(macros)}
        instr, replacements = self.replace_using_dict(instr, macro_dict)
        self.replacement_dict.update(replacements)
        return instr

    def replace_multibraces(self, instr):
        """
        Replace multibraces in the instruction with placeholders.

        Args:
            instr (str): The instruction string containing multibraces.

        Returns:
            str: The instruction string with multibraces replaced.
        """
        replacements = {}
        global_multi_index = 0

        def replace_braces(match, instr_string):
            nonlocal replacements, global_multi_index
            instr = instr_string
            multi_braces = match.group(0)
            internal_braces = self.braces_finder.findall(multi_braces[1:-1])
            for index, brace in enumerate(internal_braces):
                placeholder = f'<<MULTI_INTER{global_multi_index}>>'
                instr = instr.replace(brace, placeholder)
                replacements[placeholder] = brace
            placeholder = f'<<MULTI{global_multi_index}>>'
            instr = instr.replace(multi_braces, placeholder)
            replacements[placeholder] = multi_braces
            global_multi_index += 1
            return placeholder

        instr = re.sub(self.multi_brace_finder, lambda match: replace_braces(match, instr), instr)
        self.replacement_dict.update(replacements)
        return instr

    def replace_braces_commas(self, instr):
        """
        Replace single braces and comma-separated values in the instruction with placeholders.

        Args:
            instr (str): The instruction string containing single braces and comma-separated values.

        Returns:
            str: The instruction string with single braces and comma-separated values replaced.
        """
        braces = self.braces_finder.findall(instr)
        comma  = [val for val in braces if "..." not in val]
        braces = [val for val in braces if "..." in val]
        comma_dict = {val: f'<<COMMA{index}>>' for index, val in enumerate(comma)}
        single_dict = {val: f'<<SINGLE{index}>>' for index, val in enumerate(braces)}
        instr, replacements = self.replace_using_dict(instr, {**comma_dict, **single_dict})
        self.replacement_dict.update(replacements)
        return instr

    def replace_number_placeholders(self, instr):
        """
        Replace $number placeholders in the instruction string with unique placeholders.

        Args:
            instr (str): The instruction string containing $number placeholders.

        Returns:
            str: The instruction string with $number placeholders replaced.
        """
        # Create a dictionary to store the replacements for each unique $number
        replace_dict = {}
        for index, match in enumerate(self.number_brace_finder.finditer(instr)):
            number = match.group(0)
            # If the number is encountered for the first time, create a new placeholder
            if number not in replace_dict:
                replace_dict[number] = f'<<NUMBER{len(replace_dict)}>>'
        # Use the replace_using_dict method to perform the replacements
        instr, replacements = self.replace_using_dict(instr, replace_dict)
        # Update the replacement dictionary with the placeholders and their original values
        self.replacement_dict.update(replacements)
        return instr

    def resolve_single_brace(self, replacement_dict):
        """
        Resolve single braces and multi_internal braces in the replacement dictionary.

        Args:
            replacement_dict (dict): A dictionary containing keys with placeholders and values to be resolved.

        Raises:
            ValueError: If the input for a placeholder is invalid or if digits are not found in the value.

        Returns:
            None
        """
        for key, val in replacement_dict.items():
            if ("MULTI_INTER" in key or "SINGLE" in key ): #solve the comma seperated digits as well
                digits = re.findall(r'\d+', val)
                comma_sep_num = re.findall(r'\{\d+(?:, \d+)*\}', val)
                if digits:
                    if len(digits) == 2 and int(digits[0]) <= int(digits[1]):
                        start, end = map(int, digits)
                        result = list(range(start, end + 1))
                        replacement_dict[key] = result
                    elif len(digits) > 2 and comma_sep_num:
                            values = list(map(int, digits))
                            replacement_dict[key] = values
                    else:
                        raise ValueError(f"Invalid input for key {val}: Expected a valid range of integers")
                else:
                    raise ValueError(f"Digits not found in the value for key {val}.")

        self.replacement_dict = replacement_dict

    def resolve_multibraces(self, replacement_dict):
        """
        Resolve multibraces in the replacement dictionary.

        Args:
            replacement_dict (dict): A dictionary containing keys with placeholders and values to be resolved.

        Raises:
            ValueError: If the range pattern is not found in the value, if the start of the range is greater than the end,
                if an invalid operation is specified, or if the digit value is invalid.

        Returns:
            None
        """
        for key, val in replacement_dict.items():
            if "MULTI" in key and not "MULTI_INTER" in key :
                range_match = re.search(r'{(\d+)\s*\.\.\.\s*(\d+)}', val)
                operation_match = re.search(r'([+\-*/]|<<|>>)\s*(\d+)', val)
                comma_sep_num = re.findall(r'\{\d+(?:, \d+)*\}', val)
                if range_match:
                    start, end = map(int, range_match.groups())
                    if start <= end:
                        range_list = list(range(start, end + 1))
                        if operation_match:
                            operation, digit = operation_match.groups()
                            try:
                                digit = int(digit)
                            except ValueError:
                                raise ValueError(f"Invalid digit value for key {val}.")
                            result_list = self.apply_operation(range_list, operation, digit)
                            replacement_dict[key] = result_list
                        else:
                            raise ValueError(f"No operation found for key {val}!")
                    else:
                        raise ValueError(f"Invalid range for key {val}: Start must be less than or equal to end.")
                elif comma_sep_num:
                    internal_digits_list = re.findall(r'\d+', comma_sep_num[0])
                    internal_digits_list = list(map(int, internal_digits_list))
                    if operation_match:
                        operation, digit = operation_match.groups()
                        result_list = self.apply_operation(internal_digits_list, operation, digit)
                        replacement_dict[key] = result_list
                    else:
                        raise ValueError(f"No operation found for key {val}!")
                else:
                    raise ValueError(f"Range pattern not found in the value for key {val}.")
                
        self.replacement_dict = replacement_dict

    def resolve_comma_brace(self, replacement_dict):
        """
        Resolve comma-separated values in the replacement dictionary.

        Args:
            replacement_dict (dict): A dictionary containing keys with placeholders and comma-separated values as strings.

        Raises:
            ValueError: If the comma pattern is invalid.

        Returns:
            None
        """
        for key, val in replacement_dict.items():
            if "COMMA" in key and isinstance(val, str):
                comma_pattern = r'{(.*?)}'
                comma_match = re.findall(comma_pattern, val)
                if comma_match:
                    values = [value.strip() for value in comma_match[0].split(',')]
                    replacement_dict[key] = values
                else:
                    raise ValueError(f"Invalid Comma Pattern for {val}")

        self.replacement_dict = replacement_dict

    def calculate_coverpoints(self, instr, replacement_dict, place_holder_pattern):
        """
        Calculate coverpoints based on the provided instructions, replacement dictionary, and placeholder pattern.

        Args:
            instr (str): The instruction string.
            replacement_dict (dict): A dictionary containing keys with placeholders and their corresponding values.
            place_holder_pattern (list): A list containing the modified order of placeholders.

        Returns:
            None
        """
        # Create a Track Dictionary of the current variables
        track_dict = {}
        # Populate the dictionary with the proper indexes
        track_dict = self.initialize_track_dict(track_dict, replacement_dict) 
        # Initialize max_len
        max_len= 0
        # Check if replacement_dict is not empty
        if replacement_dict:
            # Find the maximum length and key where the value is a list
            max_list_values = [(len(val)) for val in replacement_dict.values() if isinstance(val, list)]
            if max_list_values:
                max_len = max(max_list_values)
            else:
                #In Case, there is no list but we have coverpoints
                max_len = 1

        # Now max_len and max_key will contain the maximum length and corresponding key

        gen_cov_list = []

        for index in range(max_len):
            
            # Generate coverpoint for current track
            out_cov = self.generate_current_cov(instr, track_dict, replacement_dict, place_holder_pattern)

            # Update the state of the track_dict
            track_dict = self.update_replacement_dict(track_dict)

            gen_cov_list.append(out_cov)

        for coverpoint in gen_cov_list:
            self.generator(self.curr_cov, self.label, f"{coverpoint}", 1)

    def generate_current_cov(self, instr, track_dict, replacement_dict, place_holder_pattern):
        """
        Generate coverpoints for the current instruction based on the track dictionary, replacement dictionary,
        and placeholder pattern.

        Args:
            instr (str): The instruction string.
            track_dict (dict): A dictionary containing the current track of variables.
            replacement_dict (dict): A dictionary containing keys with placeholders and their corresponding values.
            place_holder_pattern (list): A list containing the modified order of placeholders.

        Returns:
            str: The generated coverpoint.
        """
        number_pattern = re.compile('\d+')

        for key, val in replacement_dict.items():
            
            #Resolve the MULTI_BRACES back
            if "MULTI" in key and "MULTI_INTER" not in key:
                curr_index = track_dict[key][2]
                instr = instr.replace(key, str(val[curr_index]))

            #Resolve the Single braces back
            if "SINGLE" in key:
                curr_index = track_dict[key][2]
                instr = instr.replace(key, str(val[curr_index]))

            # Resolve the Comma Seperated back
            if "COMMA" in key:
                curr_index = track_dict[key][2]
                instr = instr.replace(key, str(val[curr_index]))

            #Resolve the dependent placeholders
            if "NUMBER" in key:
                result = number_pattern.findall(val)
                result = int(result[0]) -1
                var = place_holder_pattern[result]
                curr_index = track_dict[var][2]
                instr = instr.replace(key, str(replacement_dict[var][curr_index]))

        # Resolve back the macros
        for key, val in replacement_dict.items():
            if "MACRO" in key:
                instr = instr.replace(key, val)

        return instr

    def generator(self, curr_cov, label, line, rule):
        """
        Generates the required coverpoint and appends it to the existing one in the data YAML.

        Args:
            curr_cov (str): The current coverpoint.
            label (str): The label of the coverpoint.
            line (str): The coverpoint line to be generated.
            rule (int): The rule indicating whether to append to the existing coverpoint or create a new one.

        Returns:
            None
        """
        if rule == 0:
            self.data_yaml[curr_cov][label] = line
        elif rule == 1:
            if label in self.data_yaml[curr_cov]:
                self.data_yaml[curr_cov][label][line] = 0
            else:
                self.data_yaml[curr_cov][label] = {}
                self.data_yaml[curr_cov][label][line] = 0



    """Helper Functions"""
    def replace_using_dict(self, instr, replace_dict):
        """
        Replace substrings in the instruction string based on the provided dictionary.

        Args:
            instr (str): The instruction string to perform replacements on.
            replace_dict (dict): A dictionary containing substrings to replace as keys and their replacements as values.

        Returns:
            tuple: A tuple containing the modified instruction string and a dictionary of replacements made.
        """
        if not replace_dict:
            return instr, {}
        
        replacements = {}
        def replace(match):
            replacement = replace_dict[match.group(0)]
            replacements[replacement] = match.group(0)
            return replacement
        instr = re.sub('|'.join(map(re.escape, replace_dict.keys())), replace, instr)
        return instr, replacements

    def replace_order_pattern(self, instr):
        """
        Modify the order of placeholders in the instruction string based on the order of appearance.

        Args:
            instr (str): The instruction string containing placeholders.

        Returns:
            list: A list containing the modified order of placeholders.
        """
        placeholders = self.placeholder_pattern.findall(instr)
        sorted_placeholders = sorted(placeholders, key=lambda x: instr.index(x))
        
        # Create a new list to store the modified order of placeholders
        modified_placeholders = []

        for val in sorted_placeholders:
            if "MULTI" in val:
                digit_match = re.search(r'\d+', val)
                if digit_match:
                    digit = digit_match.group(0)
                    modified_placeholders.append(f'<<MULTI_INTER{digit}>>')

            modified_placeholders.append(val)

        return (modified_placeholders)

    def initialize_track_dict(self, track_dict, replacement_dict):
        """
        Initializes the track dictionary with proper indexes for the elements in the replacement dictionary.

        Args:
            track_dict (dict): The track dictionary to be initialized.
            replacement_dict (dict): The replacement dictionary containing elements for indexing.

        Returns:
            dict: The initialized track dictionary.
        """
        for key, val in replacement_dict.items():
            if isinstance(val, list):
                start_index, end_index, curr_index = 0, len(val), 0
                track_dict[key] = [start_index, end_index, curr_index]                

        return track_dict

    def update_replacement_dict(self, track_dict):
        """
        Updates the current index in the track dictionary for iterating over replacement dictionary elements.

        Args:
            track_dict (dict): The track dictionary containing index information.

        Returns:
            dict: The updated track dictionary.
        """
        for key, val in track_dict.items():
            if val[2] < val[1] -1:                     #current index < end index
                val[2] += 1
            else:
                val[2] = val[0]

        return track_dict

    def apply_operation(self, range_list, operation, digit):
        """
        Applies the specified operation to each element in the range list.

        Args:
            range_list (list): The list of numbers to apply the operation to.
            operation (str): The operation to apply (e.g., '+', '-', '*', '/', '<<', '>>').
            digit (int): The operand to use in the operation.

        Returns:
            list: The list of numbers after applying the operation and floor function to each element.

        Raises:
            ValueError: If the operation is invalid.
        """
        try:
            result_list = [eval(f"x {operation} {digit}") for x in range_list]
            # Applying the floor operation to each element in the result list
            result_list_floor = [math.floor(num) for num in result_list]
            return result_list_floor
        except SyntaxError:
            raise ValueError("Invalid operation.")







if __name__ == "__main__":
    defs_path = '/home/hammad/wrapper_cgf/Wrapper-cgf/config.defs'
    cgf_path  = '/home/hammad/wrapper_cgf/Wrapper-cgf/output.cgf'
    trans = Translator()
    trans.translate(defs_path, cgf_path)
