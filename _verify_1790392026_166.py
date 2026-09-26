def find_lucas(n): 
	if (n == 0): 
		return 2
	if (n == 1): 
		return 1
	return find_lucas(n - 1) + find_lucas(n - 2) 


assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26