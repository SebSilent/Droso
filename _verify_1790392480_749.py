from collections import Counter
def power_base_sum(base, power):
    return sum([int(i) for i in str(pow(base, power))])
from collections import Counter
def sort_counter(dict1):
 x = Counter(dict1)
 sort_counter=x.most_common()
 return sort_counter
def power(*a):
    return sort_counter(power_base_sum(*a))



assert power(3,4) == 81
assert power(2,3) == 8
assert power(5,5) == 3125