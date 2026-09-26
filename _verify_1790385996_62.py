def is_Sum_Of_Powers_Of_Two(n): 
    if (n % 2 == 1): 
        return False
    else: 
        return True


assert opposite_Signs(1,-2) == True
assert opposite_Signs(3,2) == False
assert opposite_Signs(-10,-10) == False
assert opposite_Signs(-2,2) == True