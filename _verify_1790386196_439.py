import math
def dict_filter(dict,n):
 result = {key:value for (key, value) in dict.items() if value >=n}
 return result
import math  
def even_binomial_Coeff_Sum( n): 
    return (1 << (n - 1)) 
def get_total_number_of_sequences(*a):
    return even_binomial_Coeff_Sum(dict_filter(*a))



assert get_total_number_of_sequences(10, 4) == 4
assert get_total_number_of_sequences(5, 2) == 6
assert get_total_number_of_sequences(16, 3) == 84