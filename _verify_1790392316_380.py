def count_Substrings(n):
    count = 0
    while n:
        count += n & 1
        n >>= 1
    return count


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12