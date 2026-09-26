import re
def capital_words_spaces(str1):
  return re.sub(r"(\w)([A-Z])", r"\1 \2", str1)


assert start_withp(["Python PHP", "Java JavaScript", "c c++"])==('Python', 'PHP')
assert start_withp(["Python Programming","Java Programming"])==('Python','Programming')
assert start_withp(["Pqrst Pqr","qrstuv"])==('Pqrst','Pqr')