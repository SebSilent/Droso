def find_kth(arr1, arr2, k):
	m = len(arr1)
	n = len(arr2)
	sorted1 = [0] * (m + n)
	i = 0
	j = 0
	d = 0
	while (i < m and j < n):
		if (arr1[i] < arr2[j]):
			sorted1[d] = arr1[i]
			i += 1
		else:
			sorted1[d] = arr2[j]
			j += 1
		d += 1
	while (i < m):
		sorted1[d] = arr1[i]
		d += 1
		i += 1
	while (j < n):
		sorted1[d] = arr2[j]
		d += 1
		j += 1
	return sorted1[k - 1]


assert union_elements((3, 4, 5, 6),(5, 7, 4, 10) ) == (3, 4, 5, 6, 7, 10)
assert union_elements((1, 2, 3, 4),(3, 4, 5, 6) ) == (1, 2, 3, 4, 5, 6)
assert union_elements((11, 12, 13, 14),(13, 15, 16, 17) ) == (11, 12, 13, 14, 15, 16, 17)