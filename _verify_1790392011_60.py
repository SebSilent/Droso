def dif_Square(n): 
    if (n % 4 != 2): 
        return True
    return False


assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True