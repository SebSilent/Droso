def count_reverse_pairs(*a):
    return [x for x in a[0] if x % 2 == 0]



assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2
assert count_reverse_pairs(["geeks", "best", "for", "skeeg"]) == 1
assert count_reverse_pairs(["makes", "best", "sekam", "for", "rof"]) == 2