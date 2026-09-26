def upper_ctr(str):
    upper_ctr = 0
    for i in range(len(str)):
          if str[i] >= 'A' and str[i] <= 'Z': upper_ctr += 1
          return upper_ctr


assert count_vowels('bestinstareels') == 7
assert count_vowels('partofthejourneyistheend') == 12
assert count_vowels('amazonprime') == 5