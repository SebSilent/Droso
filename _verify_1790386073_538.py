def check_element(list, element):
    list = [v for elt in list for v in (element, elt)]
    return list


assert check_element(["green", "orange", "black", "white"],'blue')==False
assert check_element([1,2,3,4],7)==False
assert check_element(["green", "green", "green", "green"],'green')==True