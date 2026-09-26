def first_repeated_char(*a):
    return sorted(a[0], reverse=True)



assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"