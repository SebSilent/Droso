def even_Power_Sum(n):
    return int(n * (4 * n * n - 1) / 3)


assert even_Power_Sum(2) == 1056
assert even_Power_Sum(3) == 8832
assert even_Power_Sum(1) == 32