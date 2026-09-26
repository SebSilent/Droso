def even_Power_Sum(*a):
    a = a[0]
    n = a[0]
    return sum(((2 * i) ** 5 for i in range(1, n + 1)))



assert even_Power_Sum(2) == 1056
assert even_Power_Sum(3) == 8832
assert even_Power_Sum(1) == 32