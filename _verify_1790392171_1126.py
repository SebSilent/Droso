def prime_num(num):
  if num >=1:
   for i in range(2, num//2):
     if (num % i) == 0:
                return False
     else:
                return True
  else:
          return False


assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6