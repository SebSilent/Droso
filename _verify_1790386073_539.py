def check_element(list1, n):
    result = [x[n] for x in list1]
    return result


assert check_element(["green", "orange", "black", "white"],'blue')==False
assert check_element([1,2,3,4],7)==False
assert check_element(["green", "green", "green", "green"],'green')==True