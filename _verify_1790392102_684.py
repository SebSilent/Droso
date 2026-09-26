def find_Parity(*a):
    out = []
    for x in a[0]:
        if x != 0:
            out.append(x)
    return out



assert find_Parity(12) == False
assert find_Parity(7) == True
assert find_Parity(10) == False