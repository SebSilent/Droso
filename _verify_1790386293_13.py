def next_square_cube(n): 
    sum = 0
    for i in range(1,n + 1): 
        sum += (2*i)*(2*i)*(2*i) 
    return sum


assert next_square_cube(2) == 81
assert next_square_cube(3) == 289
assert next_square_cube(4) == 841