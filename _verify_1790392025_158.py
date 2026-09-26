def eulerian_num(n): 
	return (n * (n + 1) * (n + 2)) / 6


assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26