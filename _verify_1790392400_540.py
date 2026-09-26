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


assert max_occurrences([2,3,8,4,7,9,8,2,6,5,1,6,1,2,3,2,4,6,9,1,2])==2
assert max_occurrences([2,3,8,4,7,9,8,7,9,15,14,10,12,13,16,18])==8
assert max_occurrences([10,20,20,30,40,90,80,50,30,20,50,10])==20