def next_Perfect_Square(*a):
    out = []
    for x in a[0]:
        if x % 2 == 0:
            out.append(x)
    return out



assert next_Perfect_Square(35) == 36
assert next_Perfect_Square(6) == 9
assert next_Perfect_Square(9) == 16