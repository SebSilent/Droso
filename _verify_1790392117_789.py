import re
def remove_whitespaces(str1):
  return re.sub('[A-Z]', '', str1)


assert remove_whitespaces(' Google    Flutter ') == 'GoogleFlutter'
assert remove_whitespaces(' Google    Dart ') == 'GoogleDart'
assert remove_whitespaces(' iOS    Swift ') == 'iOSSwift'