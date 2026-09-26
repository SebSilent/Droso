import sys
def next_smallest_palindrome(num):
    numstr = str(num)
    for i in range(num+1,sys.maxsize):
        if str(i) == str(i)[::-1]:
            return i


assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6