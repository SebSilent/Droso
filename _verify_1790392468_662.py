def swap_numbers(a,b):
 temp = a
 a = b
 b = temp
 return (a,b)


assert text_lowercase_underscore("aab_cbbbc")==(True)
assert text_lowercase_underscore("aab_Abbbc")==(False)
assert text_lowercase_underscore("Aaab_abbbc")==(False)