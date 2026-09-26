def even_Power_Sum(*a):
    out = []
    for x in a[0]:
        if x % 2 == 0:
            out.append(x)
    return out



assert even_Power_Sum(2) == 1056
assert even_Power_Sum(3) == 8832
assert even_Power_Sum(1) == 32