def is_octagonal(n): 
	return 3 * n * n - 2 * n 


assert is_nonagonal(10) == 325
assert is_nonagonal(15) == 750
assert is_nonagonal(18) == 1089