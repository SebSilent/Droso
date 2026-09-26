def divisor(n):
  for i in range(n):
    x = len([i for i in range(1,n+1) if not n % i])
  return x


assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6