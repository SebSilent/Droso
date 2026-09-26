def largest_neg(list1): 
    max = list1[0] 
    for x in list1: 
        if x < max : 
             max = x  
    return max


assert two_unique_nums([1,2,3,2,3,4,5]) == [1, 4, 5]
assert two_unique_nums([1,2,3,2,4,5]) == [1, 3, 4, 5]
assert two_unique_nums([1,2,3,4,5]) == [1, 2, 3, 4, 5]