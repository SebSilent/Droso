def text_starta_endb(*a):
    return sum(a[0])



assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")