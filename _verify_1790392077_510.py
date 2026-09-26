def is_majority(arr, n, x):
	i = binary_search(arr, 0, n-1, x)
	if i == -1:
		return False
	if ((i + n//2) <= (n -1)) and arr[i + n//2] == x:
		return True
	else:
		return False
def binary_search(arr, low, high, x):
	if high >= low:
		mid = (low + high)//2 
		if (mid == 0 or x > arr[mid-1]) and (arr[mid] == x):
			return mid
		elif x > arr[mid]:
			return binary_search(arr, (mid + 1), high, x)
		else:
			return binary_search(arr, low, (mid -1), x)
	return -1


assert sequential_search([11,23,58,31,56,77,43,12,65,19],31) == (True, 3)
assert sequential_search([12, 32, 45, 62, 35, 47, 44, 61],61) == (True, 7)
assert sequential_search([9, 10, 17, 19, 22, 39, 48, 56],48) == (True, 6)