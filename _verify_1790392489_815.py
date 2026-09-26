def is_woodall(x): 
	if (x % 2 == 0): 
		return False
	if (x == 1): 
		return True
	x = x + 1 
	p = 0
	while (x % 2 == 0): 
		x = x/2
		p = p + 1
		if (p == x): 
			return True
	return False


import math
assert math.isclose(angle_complex(0,1j), 1.5707963267948966, rel_tol=0.001)
assert math.isclose(angle_complex(2,1j), 0.4636476090008061, rel_tol=0.001)
assert math.isclose(angle_complex(0,2j), 1.5707963267948966, rel_tol=0.001)