def text_lowercase_underscore(text):
  return "".join(" " if c == "_" else ("_" if c == " " else c) for c in text)


assert text_lowercase_underscore("aab_cbbbc")==(True)
assert text_lowercase_underscore("aab_Abbbc")==(False)
assert text_lowercase_underscore("Aaab_abbbc")==(False)