def move_zero(num_list):
    a = [0 for i in range(num_list.count(0))]
    x = [i for i in num_list if i != 0]
    return x + a


assert find_sum([1,2,3,1,1,4,5,6]) == 21
assert find_sum([1,10,9,4,2,10,10,45,4]) == 71
assert find_sum([12,10,9,45,2,10,10,45,10]) == 78