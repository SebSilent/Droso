import math

def count_reverse_pairs(*a):
    return math.factorial(a[0]) if isinstance(a[0], int) and 0 <= a[0] <= 200 else None



assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2
assert count_reverse_pairs(["geeks", "best", "for", "skeeg"]) == 1
assert count_reverse_pairs(["makes", "best", "sekam", "for", "rof"]) == 2