def find_Parity(*a):
    return [x * x for x in a[0]]



assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False