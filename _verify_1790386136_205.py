def even_Power_Sum(n):
    j = 0
    sm = 0
    for i in range(1, n + 1):
        j = 2 * i - 1
        sm = sm + j * j * j * j
    return sm


assert even_Power_Sum(2) == 1056
assert even_Power_Sum(3) == 8832
assert even_Power_Sum(1) == 32