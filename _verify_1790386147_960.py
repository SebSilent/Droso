def perfect_squares(a, b):
    perfect_squares = 0
    for i in range(1, min(a, b)):
        if a % i == 0 and b % i == 0:
            perfect_squares += i
    return perfect_squares


assert perfect_squares(1,30)==[1, 4, 9, 16, 25]
assert perfect_squares(50,100)==[64, 81, 100]
assert perfect_squares(100,200)==[100, 121, 144, 169, 196]