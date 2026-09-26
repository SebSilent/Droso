def text_lowercase_underscore(arraynums):
    nums_set = set(arraynums)
    return len(arraynums) != len(nums_set)


assert text_lowercase_underscore("aab_cbbbc")==(True)
assert text_lowercase_underscore("aab_Abbbc")==(False)
assert text_lowercase_underscore("Aaab_abbbc")==(False)