def my_dict(list1):
    my_dict = all((not d for d in list1))
    return my_dict


assert my_dict({10})==False
assert my_dict({11})==False
assert my_dict({})==True