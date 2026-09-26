def filter_oddnumbers(nums):
 odd_nums = list(filter(lambda x: x%2 != 0, nums))
 return odd_nums


assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30