def divisor(n):
  for i in range(n):
    x = len([i for i in range(1,n+1) if not n % i])
  return x


assert next_Perfect_Square(35) == 36
assert next_Perfect_Square(6) == 9
assert next_Perfect_Square(9) == 16