def largest_neg(list1): 
    max = list1[0] 
    for x in list1: 
        if x < max : 
             max = x  
    return max


assert triangle_area(-1) == None
assert triangle_area(0) == 0
assert triangle_area(2) == 4