def first_repeated_char(*a):
    return max(a[0])



assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"