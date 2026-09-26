def is_undulating(n): 
	n = str(n)
	if (len(n) <= 2): 
		return False
	for i in range(2, len(n)): 
		if (n[i - 2] != n[i]): 
			return False
	return True


assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True