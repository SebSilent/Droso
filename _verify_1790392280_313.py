def upper_ctr(str):
    upper_ctr = 0
    for i in range(len(str)):
          if str[i] >= 'A' and str[i] <= 'Z': upper_ctr += 1
          return upper_ctr


assert odd_values_string('abcdef') == 'ace'
assert odd_values_string('python') == 'pto'
assert odd_values_string('data') == 'dt'
assert odd_values_string('lambs') == 'lms'