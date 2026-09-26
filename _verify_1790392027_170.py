def centered_hexagonal_number(n):
  return 3 * n * (n - 1) + 1


assert eulerian_num(3, 1) == 4
assert eulerian_num(4, 1) == 11
assert eulerian_num(5, 3) == 26