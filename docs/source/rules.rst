*********************************************RULES*****************************************************

1. {start_digit ... end_digit} 
   Anything written within these curly brackets with some numbers in the pattern using three dots 
   will be considered as a set of numbers and will be repeated depending upon on the start_digit and end_digit.
   
   Example: 
   pmpcfg{0 ... 10} then 10 coverpoints will be written starting from pmpcfg0 for the first coverpoint 
   and ending with pmpcfg10 as the last/10th coverpoint. You may use something like pmpcfg{10 ... 14} 
   or any other value as well.

2. ${} 
   Means we want to use something from the macros (constants of coverpoints itself) which is already 
   defined in the macros.yaml. This feature is already available in the RISC-V ISA . PR#80.

3. $number 
   Where <number> is any digit referring to the {} curly brackets values defined in that line/coverpoint.
   
   Example: 
   Consider a coverpoint written in the pattern:
   (pmpcfg{0 ... 10} >> 8 & pmpcfg{5 ... 8}) and (pmpcfg$1 >> 4 & 0x90) and (pmpcfg$2) == 0   
   Note: This is just for an example.
   
   So, in this case, pmpcfg$1 refers to the current value being used in the pmpcfg{0 ... 10} and 
   pmpcfg$2 refers to the current value being used in the pmpcfg{5 ... 8}.
   Note: 
   You can't use the coverpoint like pmpcfg{0,1,2} to generate three coverpoints with registers 
   pmpcfg0, pmpcfg1, pmpcfg2. Even if you want to generate two coverpoints, you need to follow the 
   pattern like pmpcfg{0 ... 1}.

4. {value1, value2, value3} 
   Anything written this way will be repeated as a coverpoint depending upon the values written 
   in the {} curly brackets. So, this may be considered as a loop.
   
   Example: 
   Consider a coverpoint written in the following fashion:
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

5. {val1, val2, end_val * number_of_time} 
   Is to be used in the coverpoints not independently like in the point 4(as there will be no purpose 
   because it will repeat).
   
   Example: 
   (pmpcfg{0 ... 3} >> {0, 8, 16, 24 * 4} & 0x80 == 0x80) == 0x00: 0
   
   Now, {0, 8, 16, 24 * 4} will be enumerated such that {0, 0, 0, 0, 8, 8, 8, 8, ..., 24, 24, 24, 24}
   Note: 
   $number functionality is only available for the point 1 and 4 and cannot be used with point 5 and 6 
   to avoid complexity.

6. {val1 ... end_val * number_of_time} 
   This is simply the advanced version of point 1. So, we can repeat the each value that comes in the 
   loop multiple times. 
   
   Example: 
   (pmpcfg{0 ... 3 * 4} & 0x80 == 0x80) and (old("pmpaddr{0 ... 15}")) ^ (pmpaddr$1) == 0x00: 0
   
   So {0 ... 3 * 4} will be repeated such that {0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3}

****************************************************************************************************
