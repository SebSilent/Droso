def frequency(s):
  count = 0
  for i in range(len(s) - 2):
    if (s[i] == 's' and s[i+1] == 't' and s[i+2] == 'd'):
      count = count + 1
  return count


assert frequency([1,2,3], 4) == 0
assert frequency([1,2,2,3,3,3,4], 3) == 3
assert frequency([0,1,2,3,1,2], 1) == 2