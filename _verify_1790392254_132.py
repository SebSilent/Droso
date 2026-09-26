def power_base_sum(base, power):
    return sum([int(i) for i in str(pow(base, power))])
def cal_sum(n): 
	a = 3
	b = 0
	c = 2
	if (n == 0): 
		return 3
	if (n == 1): 
		return 3
	if (n == 2): 
		return 5
	sum = 5
	while (n > 2): 
		d = a + b 
		sum = sum + d 
		a = b 
		b = c 
		c = d 
		n = n-1
	return sum
def power(*a):
    return cal_sum(power_base_sum(*a))



assert power(3,4) == 81
assert power(2,3) == 8
assert power(5,5) == 3125