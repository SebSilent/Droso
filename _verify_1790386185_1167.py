def hexagonal_num(n): 
	return n*(2*n - 1) 


assert is_nonagonal(10) == 325
assert is_nonagonal(15) == 750
assert is_nonagonal(18) == 1089