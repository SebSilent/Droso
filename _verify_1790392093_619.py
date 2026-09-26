def _sum(arr):  
    sum=0
    for i in arr: 
        sum = sum + i      
    return(sum)  


assert set_left_most_unset_bit(10) == 14
assert set_left_most_unset_bit(12) == 14
assert set_left_most_unset_bit(15) == 15