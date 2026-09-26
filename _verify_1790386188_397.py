import math 
def find_Index(n): 
    x = math.sqrt(2 * math.pow(10,(n - 1)))
    return round(x)


assert count_Substrings('112112') == 6
assert count_Substrings('111') == 6
assert count_Substrings('1101112') == 12