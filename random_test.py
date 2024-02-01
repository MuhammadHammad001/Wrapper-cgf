import re

def evaluate_curly_braces(expression, values):
    # Define a regular expression pattern to match content within curly braces
    pattern = re.compile(r'{(.*?)}')
    pattern_2 = re.compile(r'\${(.*?)}')
    patter_required = pattern.findall(expression)
    pattern_skip = pattern_2.findall(expression)
    
    print(patter_required)
    print(pattern_skip)
    for i in pattern_skip:
        if i in patter_required:
            patter_required.remove(i)
    
    print(patter_required)
# Example usage
expression = "(old('pmpaddr${0..63}' == pmpaddr$1) and (pmpcfg{$1>>2} & (pmplckmsk<<{($1&3)<<3}) !=0): 0"
values = []

result = evaluate_curly_braces(expression, values)
# print("Evaluated Expression:", result)
# print("Values:", values)
