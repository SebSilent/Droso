def count_reverse_pairs(*a):
    out = []
    for x in a[0]:
        for y in a[1]:
            out.append((x, y))
    return out



assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2
assert count_reverse_pairs(["geeks", "best", "for", "skeeg"]) == 1
assert count_reverse_pairs(["makes", "best", "sekam", "for", "rof"]) == 2