def find_Parity(*a):
    return [x for x in a[0] if x % 2 == 1]



assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False