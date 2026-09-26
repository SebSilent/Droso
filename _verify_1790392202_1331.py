def tetrahedral_number(n): 
	return (n * (n + 1) * (n + 2)) / 6


assert is_polite(7) == 11
assert is_polite(4) == 7
assert is_polite(9) == 13