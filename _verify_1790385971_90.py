def max_subarray_product(arr):
	n = len(arr)
	max_ending_here = 1
	min_ending_here = 1
	max_so_far = 0
	flag = 0
	for i in range(0, n):
		if arr[i] > 0:
			max_ending_here = max_ending_here * arr[i]
			min_ending_here = min (min_ending_here * arr[i], 1)
			flag = 1
		elif arr[i] == 0:
			max_ending_here = 1
			min_ending_here = 1
		else:
			temp = max_ending_here
			max_ending_here = max (min_ending_here * arr[i], 1)
			min_ending_here = temp * arr[i]
		if (max_so_far < max_ending_here):
			max_so_far = max_ending_here
	if flag == 0 and max_so_far == 0:
		return 0
	return max_so_far


assert find_first_occurrence([2, 5, 5, 5, 6, 6, 8, 9, 9, 9], 5) == 1
assert find_first_occurrence([2, 3, 5, 5, 6, 6, 8, 9, 9, 9], 5) == 2
assert find_first_occurrence([2, 4, 1, 5, 6, 6, 8, 9, 9, 9], 6) == 4