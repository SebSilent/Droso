def dog_age(h_age):
 if h_age < 0:
 	exit()
 elif h_age <= 2:
	 d_age = h_age * 10.5
 else:
	 d_age = 21 + (h_age - 2)*4
 return d_age


assert wind_chill(120,35)==40
assert wind_chill(40,20)==19
assert wind_chill(10,8)==6