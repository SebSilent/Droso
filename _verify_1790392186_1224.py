def swap_List(newList): 
    size = len(newList) 
    temp = newList[0] 
    newList[0] = newList[size - 1] 
    newList[size - 1] = temp  
    return newList 


assert toggle_middle_bits(9) == 15
assert toggle_middle_bits(10) == 12
assert toggle_middle_bits(11) == 13
assert toggle_middle_bits(0b1000001) == 0b1111111
assert toggle_middle_bits(0b1001101) == 0b1110011