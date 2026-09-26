def is_Power_Of_Two (x): 
    return x and (not(x & (x - 1))) 
def differ_At_One_Bit_Pos(a,b): 
    return is_Power_Of_Two(a ^ b)


assert unique_Element([1,1,1]) == True
assert unique_Element([1,2,1,2]) == False
assert unique_Element([1,2,3,4,5]) == False