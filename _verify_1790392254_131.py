def power_base_sum(base, power):
    return sum([int(i) for i in str(pow(base, power))])
def dog_age(h_age):
 if h_age < 0:
 	exit()
 elif h_age <= 2:
	 d_age = h_age * 10.5
 else:
	 d_age = 21 + (h_age - 2)*4
 return d_age
def power(*a):
    return dog_age(power_base_sum(*a))



assert power(3,4) == 81
assert power(2,3) == 8
assert power(5,5) == 3125