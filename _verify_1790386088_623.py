def all_Bits_Set_In_The_Given_Range(n,l,r):  
    num = (((1 << r) - 1) ^ ((1 << (l - 1)) - 1)) 
    new_num = n & num
    if (new_num == 0): 
        return True
    return False


assert set_left_most_unset_bit(10) == 14
assert set_left_most_unset_bit(12) == 14
assert set_left_most_unset_bit(15) == 15