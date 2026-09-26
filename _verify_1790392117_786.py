import re
import re
def remove_uppercase(str1):
  return re.sub('[A-Z]', '', str1)
def remove_nested(test_tup):
  res = tuple()
  for count, ele in enumerate(test_tup):
    if not isinstance(ele, tuple):
      res = res + (ele, )
  return (res) 
def remove_whitespaces(*a):
    return remove_nested(remove_uppercase(*a))



assert remove_whitespaces(' Google    Flutter ') == 'GoogleFlutter'
assert remove_whitespaces(' Google    Dart ') == 'GoogleDart'
assert remove_whitespaces(' iOS    Swift ') == 'iOSSwift'