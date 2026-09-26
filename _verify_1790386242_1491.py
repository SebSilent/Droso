def even_position(nums):
	return all(nums[i]%2==i%2 for i in range(len(nums)))


assert is_product_even([1,2,3])
assert is_product_even([1,2,1,4])
assert not is_product_even([1,1])