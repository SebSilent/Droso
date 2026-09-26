import re
def find_char_long(text):
  return (re.findall(r"\b\w{4,}\b", text))


assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5