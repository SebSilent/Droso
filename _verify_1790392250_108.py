def get_Char(*a):
    t = 0
    for x in a[0]:
        t += x * x
    return t



assert get_Char("abc") == "f"
assert get_Char("gfg") == "t"
assert get_Char("ab") == "c"