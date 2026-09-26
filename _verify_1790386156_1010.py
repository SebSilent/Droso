def first_repeated_char(*a):
    return [x for x in a[0] if x % 2 == 1]



assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"