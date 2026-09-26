def is_octagonal(n): 
	return 3 * n * n - 2 * n 


assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26