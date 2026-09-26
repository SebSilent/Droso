def count_reverse_pairs(str):
    count_reverse_pairs = 0
    for i in range(len(str)):
        if str[i] >= '0' and str[i] <= '9':
            count_reverse_pairs += 1
    return count_reverse_pairs


assert count_reverse_pairs(["julia", "best", "tseb", "for", "ailuj"])== 2
assert count_reverse_pairs(["geeks", "best", "for", "skeeg"]) == 1
assert count_reverse_pairs(["makes", "best", "sekam", "for", "rof"]) == 2