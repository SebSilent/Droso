def find_Parity(n):
    while n >= 10:
        n = n / 10
    return int(n)


assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False