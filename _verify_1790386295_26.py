import math  
def next_Perfect_Square(N): 
    nextN = math.floor(math.sqrt(N)) + 1
    return nextN * nextN 


assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841