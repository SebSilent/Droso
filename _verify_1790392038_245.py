def pancake_sort(data_list):
    total = 0
    for element in data_list:
        if type(element) == type([]):
            total = total + pancake_sort(element)
        else:
            total = total + element
    return total


assert pancake_sort([15, 79, 25, 38, 69]) == [15, 25, 38, 69, 79]
assert pancake_sort([98, 12, 54, 36, 85]) == [12, 36, 54, 85, 98]
assert pancake_sort([41, 42, 32, 12, 23]) == [12, 23, 32, 41, 42]