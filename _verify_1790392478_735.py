def get_Char(*a):
    return sorted(a[0], reverse=True)



assert get_Char("abc") == "f"
assert get_Char("gfg") == "t"
assert get_Char("ab") == "c"