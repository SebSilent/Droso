def text_starta_endb(*a):
    return [x for x in a[0] if x % 2 == 1]



assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")