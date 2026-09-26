def text_starta_endb(*a):
    return a[0].lower()



assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")