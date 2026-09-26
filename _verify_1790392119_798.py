def remove_length(test_str, K):
  temp = test_str.split()
  res = [ele for ele in temp if len(ele) != K]
  res = ' '.join(res)
  return (res) 


assert remove_whitespaces(' Google    Flutter ') == 'GoogleFlutter'
assert remove_whitespaces(' Google    Dart ') == 'GoogleDart'
assert remove_whitespaces(' iOS    Swift ') == 'iOSSwift'