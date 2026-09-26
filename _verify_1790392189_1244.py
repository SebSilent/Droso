def odd_length_sum(arr):
    Sum = 0
    l = len(arr)
    for i in range(l):
        Sum += ((((i + 1) *(l - i) + 1) // 2) * arr[i])
    return Sum


assert geometric_sum(7) == 1.9921875
assert geometric_sum(4) == 1.9375
assert geometric_sum(8) == 1.99609375