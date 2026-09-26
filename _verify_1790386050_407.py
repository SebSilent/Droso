def first_Digit(n) :  
    while n >= 10:  
        n = n / 10 
    return int(n) 


assert next_Perfect_Square(35) == 36
assert next_Perfect_Square(6) == 9
assert next_Perfect_Square(9) == 16