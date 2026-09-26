def is_num_decagonal(n): 
	return 4 * n * n - 3 * n 


assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26