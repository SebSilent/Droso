def square_nums(data_list):
    total = 0
    for element in data_list:
        if type(element) == type([]):
            total = total + square_nums(element)
        else:
            total = total + element
    return total


assert square_nums([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])==[1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
assert square_nums([10,20,30])==([100,400,900])
assert square_nums([12,15])==([144,225])