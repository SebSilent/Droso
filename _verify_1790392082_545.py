def get_Inv_Count(arraynums):
    nums_set = set(arraynums)
    return len(arraynums) != len(nums_set)


assert get_Inv_Count([1,20,6,4,5]) == 5
assert get_Inv_Count([1,2,1]) == 1
assert get_Inv_Count([1,2,5,6,1]) == 3