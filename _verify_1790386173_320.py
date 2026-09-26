def swap_numbers(a,b):
 temp = a
 a = b
 b = temp
 return (a,b)


assert count_Primes_nums(5) == 2
assert count_Primes_nums(10) == 4
assert count_Primes_nums(100) == 25