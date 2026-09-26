def remove_length(test_str, K):
  temp = test_str.split()
  res = [ele for ele in temp if len(ele) != K]
  res = ' '.join(res)
  return (res) 


assert sample_nam(['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith'])==16
assert sample_nam(["php", "res", "Python", "abcd", "Java", "aaa"])==10
assert sample_nam(["abcd", "Python", "abba", "aba"])==6