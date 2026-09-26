def text_starta_endb(arraynums):
    nums_set = set(arraynums)
    return len(arraynums) != len(nums_set)


assert text_starta_endb("aabbbb")
assert not text_starta_endb("aabAbbbc")
assert not text_starta_endb("accddbbjjj")