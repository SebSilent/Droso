def remove_length(test_str, K):
  temp = test_str.split()
  res = [ele for ele in temp if len(ele) != K]
  res = ' '.join(res)
  return (res) 


assert replace_spaces("My Name is Dawood") == 'My%20Name%20is%20Dawood'
assert replace_spaces("I am a Programmer") == 'I%20am%20a%20Programmer'
assert replace_spaces("I love Coding") == 'I%20love%20Coding'