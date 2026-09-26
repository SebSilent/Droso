def replace_spaces(text):
  return "".join(" " if c == "_" else ("_" if c == " " else c) for c in text)


assert replace_spaces("My Name is Dawood") == 'My%20Name%20is%20Dawood'
assert replace_spaces("I am a Programmer") == 'I%20am%20a%20Programmer'
assert replace_spaces("I love Coding") == 'I%20love%20Coding'