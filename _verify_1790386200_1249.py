def median_numbers(a,b,c):
 if a > b:
    if a < c:
        median = a
    elif b > c:
        median = b
    else:
        median = c
 else:
    if a > c:
        median = a
    elif b < c:
        median = b
    else:
        median = c
 return median
def sum_Of_Subarray_Prod(arr):
    ans = 0
    res = 0
    i = len(arr) - 1
    while (i >= 0):
        incr = arr[i]*(1 + res)
        ans += incr
        res = incr
        i -= 1
    return (ans)
def lcs_of_three(*a):
    return sum_Of_Subarray_Prod(median_numbers(*a))



assert lcs_of_three('AGGT12', '12TXAYB', '12XBA') == 2
assert lcs_of_three('Reels', 'Reelsfor', 'ReelsforReels') == 5
assert lcs_of_three('abcd1e2', 'bc12ea', 'bd1ea') == 3