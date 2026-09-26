def _sum(arr):  
    sum=0
    for i in arr: 
        sum = sum + i      
    return(sum)  
def maximum(a,b):   
    if a >= b: 
        return a 
    else: 
        return b 
def set_left_most_unset_bit(*a):
    return maximum(_sum(*a), *a[1:])



assert set_left_most_unset_bit(10) == 14
assert set_left_most_unset_bit(12) == 14
assert set_left_most_unset_bit(15) == 15