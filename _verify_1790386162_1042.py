def remove_length(test_str, K):
  temp = test_str.split()
  res = [ele for ele in temp if len(ele) != K]
  res = ' '.join(res)
  return (res) 


assert reverse_words("python program")==("program python")
assert reverse_words("java language")==("language java")
assert reverse_words("indian man")==("man indian")