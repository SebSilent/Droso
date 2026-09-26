def text_lowercase_underscore(*a):
    return ''.join(str(x) for x in a[0])



assert text_lowercase_underscore("aab_cbbbc")==(True)
assert text_lowercase_underscore("aab_Abbbc")==(False)
assert text_lowercase_underscore("Aaab_abbbc")==(False)