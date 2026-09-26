def find_sum(list1):
    if len(list1) == 0:
        return [[]]
    result = []
    for el in find_sum(list1[1:]):
        result += [el, el + [list1[0]]]
    return result


assert find_sum([1,2,3,1,1,4,5,6]) == 21
assert find_sum([1,10,9,4,2,10,10,45,4]) == 71
assert find_sum([12,10,9,45,2,10,10,45,10]) == 78