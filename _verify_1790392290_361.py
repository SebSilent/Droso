def text_lowercase_underscore(*a):
    return [x for x in a[0] if x % 2 == 1]



assert text_lowercase_underscore("aab_cbbbc")==(True)
assert text_lowercase_underscore("aab_Abbbc")==(False)
assert text_lowercase_underscore("Aaab_abbbc")==(False)