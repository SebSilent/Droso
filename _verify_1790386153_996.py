def first_repeated_char(str1):
    char_order = []
    ctr = {}
    for c in str1:
        if c in ctr:
            ctr[c] += 1
        else:
            ctr[c] = 1
            char_order.append(c)
    for c in char_order:
        if ctr[c] == 1:
            return c
    return None


assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"