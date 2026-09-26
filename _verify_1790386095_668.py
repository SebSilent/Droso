def find_Parity(n):
    return n % 11 == 0


assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False