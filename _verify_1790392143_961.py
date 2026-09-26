def perfect_squares(arr, n):
    ans = 0
    for i in range(0, n):
        for j in range(i + 1, n):
            ans = ans + (arr[i] ^ arr[j])
    return ans


assert perfect_squares(1,30)==[1, 4, 9, 16, 25]
assert perfect_squares(50,100)==[64, 81, 100]
assert perfect_squares(100,200)==[100, 121, 144, 169, 196]