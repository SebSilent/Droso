def get_Char(str):
    get_Char = 0
    for i in range(len(str)):
        if str[i] >= 'A' and str[i] <= 'Z':
            get_Char += 1
        return get_Char


assert get_Char("abc") == "f"
assert get_Char("gfg") == "t"
assert get_Char("ab") == "c"