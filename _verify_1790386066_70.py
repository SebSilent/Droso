def add_nums(data_list):
    total = 0
    for element in data_list:
        if type(element) == type([]):
            total = total + add_nums(element)
        else:
            total = total + element
    return total


assert min_of_three(10,20,0)==0
assert min_of_three(19,15,18)==15
assert min_of_three(-10,-20,-30)==-30