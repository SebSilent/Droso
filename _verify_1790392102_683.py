def find_Parity(*a):
    return sorted(a[0], reverse=True)



assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False