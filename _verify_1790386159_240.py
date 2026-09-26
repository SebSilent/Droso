def count_Substrings(str):
    count_Substrings = 0
    for i in range(len(str)):
        if str[i] >= '0' and str[i] <= '9':
            count_Substrings += 1
    return count_Substrings


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12