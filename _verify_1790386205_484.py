def even_Power_Sum(*a):
    t = 0
    for x in a[0]:
        t += x
    return t



assert even_Power_Sum(2) == 1056
assert even_Power_Sum(3) == 8832
assert even_Power_Sum(1) == 32