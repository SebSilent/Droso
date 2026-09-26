def get_Inv_Count(arr):
    sum = 0
    for i in arr:
        sum = sum + i
    return sum


assert get_Inv_Count([1,20,6,4,5]) == 5
assert get_Inv_Count([1,2,1]) == 1
assert get_Inv_Count([1,2,5,6,1]) == 3