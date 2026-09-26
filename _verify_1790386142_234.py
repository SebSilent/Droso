def number_of_substrings(str): 
	str_len = len(str); 
	return int(str_len * (str_len + 1) / 2); 


assert test_three_equal(1,1,1) == 3
assert test_three_equal(-1,-2,-3) == 0
assert test_three_equal(1,2,2) == 2