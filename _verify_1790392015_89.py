def comb_sort(data_list):
    total = 0
    for element in data_list:
        if type(element) == type([]):
            total = total + comb_sort(element)
        else:
            total = total + element
    return total


assert comb_sort([5, 15, 37, 25, 79]) == [5, 15, 25, 37, 79]
assert comb_sort([41, 32, 15, 19, 22]) == [15, 19, 22, 32, 41]
assert comb_sort([99, 15, 13, 47]) == [13, 15, 47, 99]