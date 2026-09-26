def all_Bits_Set_In_The_Given_Range(n,l,r):  
    num = (((1 << r) - 1) ^ ((1 << (l - 1)) - 1)) 
    new_num = n & num
    if (new_num == 0): 
        return True
    return False


assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True