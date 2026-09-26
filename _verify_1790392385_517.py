def catalan_number(num):
    if num <=1:
         return 1   
    res_num = 0
    for i in range(num):
        res_num += catalan_number(i) * catalan_number(num-i-1)
    return res_num


import math
assert math.isclose(angle_complex(0,1j), 1.5707963267948966, rel_tol=0.001)
assert math.isclose(angle_complex(2,1j), 0.4636476090008061, rel_tol=0.001)
assert math.isclose(angle_complex(0,2j), 1.5707963267948966, rel_tol=0.001)