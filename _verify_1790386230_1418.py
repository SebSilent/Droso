def text_starta_endb(*a):
    return all(a[0] % i for i in range(2, int(a[0] ** 0.5) + 1)) if a[0] > 1 else False



assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")