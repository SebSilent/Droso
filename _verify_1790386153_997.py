def first_repeated_char(n):
    while n >= 10:
        n = n / 10
    return int(n)


assert first_repeated_char("abcabc") == "a"
assert first_repeated_char("abc") == None
assert first_repeated_char("123123") == "1"