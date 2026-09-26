def get_Char(*a):
    return [x for x in a[0] if x % 2 == 0]



assert get_Char("abc") == "f"
assert get_Char("gfg") == "t"
assert get_Char("ab") == "c"