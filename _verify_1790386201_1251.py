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
def common_in_nested_lists(nestedlist):
    result = list(set.intersection(*map(set, nestedlist)))
    return result
def lcs_of_three(*a):
    return common_in_nested_lists(median_numbers(*a))



assert lcs_of_three('AGGT12', '12TXAYB', '12XBA') == 2
assert lcs_of_three('Reels', 'Reelsfor', 'ReelsforReels') == 5
assert lcs_of_three('abcd1e2', 'bc12ea', 'bd1ea') == 3